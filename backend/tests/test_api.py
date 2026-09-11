import copy
import json
import uuid
from datetime import timedelta
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.db import engine, cache, Run, Progress, TaskCard, now
from conftest import BASE_URL, SECRET, correct_answer

def post_answer(client, rid, q, answer):
    return client.post(f'/api/runs/{rid}/answer', json={'question_id':q['id'], 'answer':answer})

def assert_redacted(run):
    for q in run['questions']:
        assert not {'answer','hint','explanation','threshold','standard_answer'}.intersection(q)
    if run['status'] == 'active': assert run['report'] is None

@pytest.mark.parametrize('path', ['/api/auth/me','/api/abilities','/api/dashboard','/api/tasks','/api/knowledge','/api/abilities/A1/refresh'])
def test_anonymous_denied(path):
    assert httpx.get(BASE_URL + path).status_code == 401

def test_account_login_logout_profile_and_origin(account):
    c = account['client']
    response = c.get('/api/auth/me')
    assert response.status_code == 200
    assert response.json()['username'] == account['username']
    assert 'password' not in response.json()
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert c.post('/api/profile', json={'name':'外部QA','goal':'课程补强','daily_goal':20,'voice':False}, headers={'Origin':'https://untrusted.example'}).status_code == 403
    assert c.post('/api/profile', json={'name':'外部QA','goal':'课程补强','daily_goal':20,'voice':False}).status_code == 200
    assert c.get('/api/auth/me').json()['daily_goal'] == 20
    assert c.post('/api/profile', json={'name':'外部QA','goal':'bogus','daily_goal':20,'voice':False}).status_code == 422
    assert c.post('/api/auth/login', json={'username':account['username'],'password':'wrong'}).status_code == 401
    assert c.post('/api/auth/logout').status_code == 200
    assert c.get('/api/auth/me').status_code == 401

def test_run_owner_isolation(account, account_factory, seeded_run):
    other = account_factory()['client']
    rid, qs = seeded_run(account)
    assert other.get(f'/api/runs/{rid}').status_code == 404
    assert post_answer(other, rid, qs[0], correct_answer(qs[0])).status_code == 404
    assert other.post(f'/api/runs/{rid}/finish').status_code == 404
    assert other.post(f'/api/runs/{rid}/repair').status_code == 404
    response = other.post('/api/ai/chat', json={'mode':'QUESTION_TUTOR','message':'今天天气','run_id':rid,'question_id':qs[0]['id']})
    assert response.status_code == 404

def test_level_locks_and_resuming(account):
    c=account['client']
    states=c.get('/api/abilities').json()
    a1=next(a for a in states if a['id']=='A1')
    assert a1['levels'][0]['unlocked'] and not a1['levels'][1]['unlocked']
    for level in ('A1-L2','A1-JOB','A1-RACE'):
        assert c.post('/api/runs/start',json={'level_id':level}).status_code==403
    assert c.post('/api/runs/start',json={'level_id':'A99-L1'}).status_code==404
    first=c.post('/api/runs/start',json={'level_id':'A1-L1'}).json()
    assert_redacted(first)
    second=c.post('/api/runs/start',json={'level_id':'A1-L1'}).json()
    assert first['id']==second['id']
    assert c.get('/api/abilities/A99').status_code==404

def test_course_latest_answer_persistence_finish_idempotent(account, seeded_run):
    c=account['client'];rid,qs=seeded_run(account)
    assert c.post(f'/api/runs/{rid}/finish').status_code==400
    assert post_answer(c,rid,dict(qs[0],id='foreign-question'),{}).status_code==404
    assert post_answer(c,rid,qs[0],{'value':'错误'}).json()['result']['correct'] is False
    for q in qs:
        assert post_answer(c,rid,q,correct_answer(q)).json()['result']['correct']
    resumed=c.get(f'/api/runs/{rid}').json()
    assert resumed['answers'][qs[0]['id']]==correct_answer(qs[0])
    assert_redacted(resumed)
    finished=c.post(f'/api/runs/{rid}/finish').json()
    assert finished['status']=='completed' and finished['report']['score']==100
    assert c.post(f'/api/runs/{rid}/finish').json()['report']==finished['report']
    assert post_answer(c,rid,qs[0],{}).status_code==409
    with Session(engine) as db:
        p=db.get(Progress,f'{account["username"]}:A1-L1')
        assert p.score==100 and p.attempts==1
        assert db.get(Run,rid).finished_at is not None
    module=c.get('/api/abilities/A1').json()
    assert module['levels'][0]['completed'] and module['levels'][1]['unlocked']
    dashboard=c.get('/api/dashboard').json()
    assert dashboard['total_count']==len(qs) and dashboard['completed_levels']==1

@pytest.mark.parametrize('level,mode', [('A4-JOB','job'),('A4-RACE','competition')])
def test_package_answers_hidden_until_finished(account, seeded_run, level, mode):
    c=account['client'];rid,qs=seeded_run(account,level,mode,deadline=now()+timedelta(minutes=10) if mode=='competition' else None)
    assert_redacted(c.get(f'/api/runs/{rid}').json())
    for q in qs:
        response=post_answer(c,rid,q,correct_answer(q))
        assert response.status_code==200
        assert set(response.json())=={'saved','answered','count'}
    read=c.get(f'/api/runs/{rid}').json()
    assert_redacted(read)
    assert read['report'] is None
    done=c.post(f'/api/runs/{rid}/finish').json()
    assert done['report']['score']==100
    assert all('standard_answer' in r for r in done['report']['results'])

def test_deadline_server_enforced_and_report_persisted(account, seeded_run):
    c=account['client'];rid,qs=seeded_run(account,'A1-RACE','competition',deadline=now()-timedelta(seconds=2))
    response=post_answer(c,rid,qs[0],correct_answer(qs[0]))
    assert response.status_code==409
    state=c.get(f'/api/runs/{rid}').json()
    assert state['status']=='completed' and state['report']['score']==0
    assert state['report']['missed_rate']==100
    with Session(engine) as db:
        assert db.get(Run,rid).status=='completed'
        assert db.get(Progress,f'{account["username"]}:A1-RACE').attempts==1

def test_competition_no_tutor_while_active(account, seeded_run):
    c=account['client'];rid,qs=seeded_run(account,'A1-RACE','competition',deadline=now()+timedelta(minutes=5))
    response=c.post('/api/ai/chat',json={'message':'今天天气','mode':'QUESTION_TUTOR','run_id':rid,'question_id':qs[0]['id']})
    assert response.status_code==403

def test_job_partial_finish_and_repair(account, seeded_run):
    c=account['client'];rid,qs=seeded_run(account,'A1-JOB','job')
    assert c.post(f'/api/runs/{rid}/finish').status_code==400
    assert c.post(f'/api/runs/{rid}/repair').status_code==400
    for i,q in enumerate(qs):
        assert post_answer(c,rid,q,correct_answer(q) if i else {}).status_code==200
    finished=c.post(f'/api/runs/{rid}/finish').json()
    assert finished['report']['correct_count']==len(qs)-1
    repaired=c.post(f'/api/runs/{rid}/repair').json()
    assert repaired['revision_of']==rid and len(repaired['answers'])==len(qs)-1
    assert qs[0]['id'] not in repaired['answers']
    assert_redacted(repaired)
    assert post_answer(c,repaired['id'],qs[0],correct_answer(qs[0])).status_code==200
    assert c.post(f'/api/runs/{repaired["id"]}/finish').json()['report']['score']==100
    with Session(engine) as db:
        p=db.get(Progress,f'{account["username"]}:A1-JOB')
        assert p.attempts==2 and p.score==100

def test_homepage_tutor_sse_has_no_fixed_scope_guard(account):
    c=account['client']
    assert c.post('/api/ai/chat',json={'message':'今天天气','mode':'UNKNOWN'}).status_code==422
    assert c.post('/api/ai/chat',json={'message':'今天天气','mode':'QUESTION_TUTOR'}).status_code==422
    response=c.post('/api/ai/chat',json={'message':'今天天气怎么样？'})
    assert response.status_code==200 and response.headers['content-type'].startswith('text/event-stream')
    assert 'scope_guard' not in response.text
    assert 'event: done' in response.text and '"sources": []' in response.text

def test_task_list_owner_filter(account, account_factory):
    second=account_factory(); identifiers=[]
    with Session(engine) as db:
        for a in (account,second):
            tid=str(uuid.uuid4()); identifiers.append(tid)
            db.add(TaskCard(id=tid,username=a['username'],content={'name':'QA临时任务'}))
        db.commit()
    assert [t['id'] for t in account['client'].get('/api/tasks').json()]==identifiers[:1]
    assert [t['id'] for t in second['client'].get('/api/tasks').json()]==identifiers[1:]

def test_answer_payload_limits(account, seeded_run):
    c=account['client'];rid,qs=seeded_run(account)
    assert c.post(f'/api/runs/{rid}/answer',json={'question_id':qs[0]['id'],'answer':None}).status_code==422
    assert post_answer(c,rid,qs[0],{'value':'a'*50001}).status_code==422

def test_race_unlock_after_all_six_prior_levels_done(account):
    c=account['client'];name=account['username']
    with Session(engine) as db:
        for level in ['A1-L1','A1-L2','A1-L3','A1-L4','A1-L5','A1-JOB']:
            db.add(Progress(id=f'{name}:{level}',username=name,ability_id='A1',level_id=level,score=0))
        db.commit()
    # Spec unlocks after DONE; passing is not a prerequisite.
    module=c.get('/api/abilities/A1').json()
    assert module['levels'][-1]['unlocked']
    response=c.post('/api/runs/start',json={'level_id':'A1-RACE'})
    assert response.status_code==200
    run=response.json()
    assert run['mode']=='competition' and len(run['questions'])==10 and run['deadline']

def test_question_page_does_not_pre_reject_short_or_offtopic_wording(account, seeded_run):
    c=account['client'];rid,qs=seeded_run(account,'A4-JOB','job')
    response=c.post('/api/ai/chat',json={'message':'今天天气怎么样','mode':'QUESTION_TUTOR','run_id':rid,'question_id':qs[0]['id']})
    assert response.status_code==200 and 'scope_guard' not in response.text
    assert 'standard_answer' not in response.text and '"box"' not in response.text

def test_only_explicit_hint_requests_advance_dialogue_hint_level(account, seeded_run):
    c=account['client'];rid,qs=seeded_run(account,'A4-L1','course');qid=qs[0]['id']
    response=c.post('/api/ai/chat',json={'message':'怎么判断目标大小','mode':'QUESTION_TUTOR','run_id':rid,'question_id':qid})
    assert response.status_code==200
    with Session(engine) as db: assert (db.get(Run,rid).hints or {}).get(qid,0)==0
    response=c.post('/api/ai/chat',json={'message':'给我一点提示','mode':'QUESTION_TUTOR','run_id':rid,'question_id':qid,'hint_request':True})
    assert response.status_code==200
    with Session(engine) as db: assert db.get(Run,rid).hints[qid]==1

def test_post_submit_wrong_instance_dialogue_uses_candidate_evidence(account, seeded_run):
    from backend.tutor import candidate_targets
    c=account['client'];rid,qs=seeded_run(account,'A4-L1','course')
    q=next(item for item in qs if str(item.get('sample_id'))=='86956')
    left=next(item for item in candidate_targets(q) if item.get('annotation_id')==508729)
    graded=post_answer(c,rid,q,{'boxes':[{'label':left['label'],'box':left['box']}]}).json()['result']
    assert graded['error_type']=='MISSED_TARGET'  # the dialogue layer must not mutate scoring
    response=c.post('/api/ai/chat',json={'message':'为什么错了','mode':'QUESTION_TUTOR','run_id':rid,'question_id':q['id']})
    assert response.status_code==200 and 'WRONG_TARGET_INSTANCE' in response.text
    token_text=''.join(json.loads(line[6:])['text'] for line in response.text.splitlines()
                       if line.startswith('data: ') and '"text"' in line)
    assert '右侧' in token_text and ('左侧' in token_text or '另一' in token_text)
    assert all(text not in token_text for text in (
        '边界没有贴合','边界没贴合','漏标了其他','漏选了其他'))

def test_onboarding_requires_independent_annotation_and_persists(account):
    c=account['client']
    response=c.post('/api/onboarding/start')
    assert response.status_code==200
    run=response.json();rid=run['id']
    assert len(run['questions'])==5
    assert 'guide_box' in run['questions'][0] and 'guide_box' not in run['questions'][1]
    assert c.post('/api/onboarding/start').json()['id']==rid
    body={'run_id':rid,'goal':'岗位入门','daily_goal':15}
    assert c.post('/api/onboarding/complete',json=body).status_code==400
    with Session(engine) as db: qs=copy.deepcopy(db.get(Run,rid).questions)
    for i,q in enumerate(qs):
        assert post_answer(c,rid,q,{} if i==1 else correct_answer(q)).status_code==200
    assert c.post('/api/onboarding/complete',json=body).status_code==400
    assert post_answer(c,rid,qs[1],correct_answer(qs[1])).status_code==200
    result=c.post('/api/onboarding/complete',json=body)
    assert result.status_code==200 and result.json()['onboarding'] is True
    assert c.get('/api/auth/me').json()['daily_goal']==15
    with Session(engine) as db:
        assert db.get(Run,rid).status=='completed'
        assert db.get(Progress,f'{account["username"]}:ONBOARDING') is None
    dashboard=c.get('/api/dashboard').json()
    assert dashboard['diagnostic']['score']==100 and len(dashboard['diagnostic']['skills'])==3
