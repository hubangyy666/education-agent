"""Refresh contract tests: content, publication, failure and old run snapshots."""
import copy
import json
from types import SimpleNamespace

import pytest

from backend import factory_agent as agent, factory_workflow as workflow, visual_reserve


class Cache:
    def __init__(self):
        self.values={};self.states=[]
    def set(self,key,value,nx=False,**kwargs):
        if nx and key in self.values:return False
        self.values[key]=value
        if key.startswith('factory:'):self.states.append(json.loads(value))
        return True
    def get(self,key):return self.values.get(key)
    def exists(self,key):return key in self.values
    def expire(self,*args):return True
    def eval(self,script,count,*args):
        keys=args[:count];values=args[count:]
        if 'factory-status-cas' in script:
            payload,job,token=values
            if self.get(keys[1])!=token:return 0
            if self.get(keys[2]) not in (None,job):return 0
            old=self.get(keys[0])
            if old and json.loads(old).get('id')!=job:return 0
            self.set(keys[0],payload)
            return 1
        if self.get(keys[0])!=values[0]:return 0
        self.values.pop(keys[0],None)
        if count==2 and self.get(keys[1])==values[1]:self.values.pop(keys[1],None)
        return 1


class Database:
    def __init__(self,current):self.current=current;self.added=[];self.committed=False
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def scalar(self,*args):return self.current
    def execute(self,*args):pass
    def add(self,item):self.added.append(item)
    def commit(self):self.committed=True


def reserve(tmp_path,per_skill=12):
    store=agent.Store(tmp_path);rows=[]
    for skill in range(1,6):
        for index in range(per_skill):
            q=dict(type='choice',skill_id=f'A1-S{skill}',title=f'技能 {skill} 操作条件 {index} 的判断',
                   project_rule=f'条件 {skill} / {index}',options=['合规','违规','信息不足'],answer='合规',
                   hint=['观察','比较','复核'],explanation='按明示条件判断',source_url='https://example.org/training',
                   evidence=[{'source_url':'https://example.org/training'}],status='approved',ai_generated=True)
            q.update(content_hash=agent.content_hash(q),ai_review=dict(decision='approved',duplicate=False,
                     independent_answer=q['answer'],**{name:1 for name in agent.QUALITY_MIN}))
            rows.append(q)
    store.merge('A1',rows)
    return store


def test_existing_reserve_produces_fresh_content_without_model_or_download(tmp_path,monkeypatch):
    store=reserve(tmp_path)
    monkeypatch.setattr(workflow,'visual_questions',lambda aid:[])
    old=visual_reserve.combined_pool('A1',1,store,visual=[])
    hashes={agent.content_hash(q) for qs in old.values() for q in qs}
    monkeypatch.setattr(workflow,'generate_candidates',lambda *a,**k:pytest.fail('full reserve must not call model'))
    monkeypatch.setattr(workflow.subprocess,'run',lambda *a,**k:pytest.fail('full reserve must not download'))
    new=workflow.prepare_pool('A1',2,store,lambda *a,**k:None,previous=hashes)
    fresh={agent.content_hash(q) for qs in new.values() for q in qs}-hashes
    assert len(fresh)==5
    assert all(any(agent.content_hash(q) in fresh for q in new[f'A1-L{i}']) for i in range(1,6))


def test_no_approval_progress_has_bounded_model_budget(tmp_path,monkeypatch):
    store=reserve(tmp_path,per_skill=1);calls=[]
    monkeypatch.setattr(workflow,'visual_questions',lambda aid:[])
    monkeypatch.setattr(workflow,'generate_candidates',lambda *args:calls.append(args[1]))
    with pytest.raises(ValueError,match='尚未通过足量审核'):
        workflow.prepare_pool('A1',2,store,lambda *a,**k:None)
    assert len(calls)==workflow.MAX_BATCHES_PER_SKILL
    assert len(calls)<=workflow.MAX_GENERATION_BATCHES


def test_rejected_review_is_never_published(tmp_path):
    store=reserve(tmp_path)
    rows=store.questions('A1')
    for q in rows:q['ai_review']['ground_truth']=.94
    store.write('A1.reserve.json',rows)
    with pytest.raises(ValueError,match='审核不通过'):
        visual_reserve.combined_pool('A1',2,store,visual=[])


def test_reviewer_receives_only_review_inputs_not_generation_directives(tmp_path,monkeypatch):
    store=reserve(tmp_path)
    candidate=copy.deepcopy(store.questions('A1')[0])
    candidate.update(title='验证一次全新的授权操作条件',source_id='evidence')
    monkeypatch.setattr(agent,'evidence',lambda *args:[dict(id='evidence',source_url=candidate['source_url'])])
    payloads=[]
    class Model:
        def json(self,system,payload):
            payloads.append((system,payload))
            if system==agent.GENERATE:return {'questions':[candidate]},'generation-id'
            return {'reviews':[dict(index=0,**candidate['ai_review'])]},'independent-review-id'
    previous=[dict(candidate,title='另一个能力的旧题',skill_id='A9-S1')]
    accepted=agent.generate_candidates('A1','A1-S1',1,previous,store,Model())
    assert len(accepted)==1 and len(payloads)==2
    assert payloads[0][1]['previous_questions']==[]
    review=payloads[1][1]
    assert not {'final_instruction','design_note','count','scenario_blueprints'}.intersection(review)
    assert accepted[0]['generation_request_id']!=accepted[0]['ai_review']['request_id']


def setup_workflow(tmp_path,monkeypatch):
    store=reserve(tmp_path)
    pool=visual_reserve.combined_pool('A1',1,store,visual=[])
    db=Database(SimpleNamespace(id='old',version=1,active=True,questions=copy.deepcopy(pool)))
    cache=Cache();cache.set('factory-lock:A1','job')
    monkeypatch.setattr(workflow,'cache',cache)
    monkeypatch.setattr(workflow,'Session',lambda engine:db)
    monkeypatch.setattr(workflow,'monitor_quality',lambda *args:None)
    monkeypatch.setattr(workflow,'reserve_index',lambda *args:None)
    monkeypatch.setattr(workflow,'visual_questions',lambda aid:[])
    return store,db,cache,pool


def test_real_pool_atomic_publication_reports_actual_new_count(tmp_path,monkeypatch):
    store,db,cache,old=setup_workflow(tmp_path,monkeypatch)
    workflow.refresh_questions('A1','job',state_path=store.path)
    status=json.loads(cache.get('factory:A1'))
    assert status['status']=='completed' and status['version']==2
    assert status['new_question_count']==5 and status['reused_question_count']==50
    assert status['question_count']==55
    assert db.committed and len(db.added)==1 and not db.current.active
    assert db.current.questions==old
    assert not cache.exists('factory-lock:A1') and not cache.exists('factory-worker:A1')
    progress=[s['progress'] for s in cache.states]
    assert progress==sorted(progress)


def test_unchanged_content_failure_does_not_publish(tmp_path,monkeypatch):
    store,db,cache,old=setup_workflow(tmp_path,monkeypatch)
    monkeypatch.setattr(workflow,'prepare_pool',lambda *args,**kwargs:copy.deepcopy(old))
    workflow.refresh_questions('A1','job',state_path=store.path)
    assert json.loads(cache.get('factory:A1'))['status']=='failed'
    assert not db.committed and not db.added and db.current.active


def test_index_failure_after_commit_still_reports_publication(tmp_path,monkeypatch):
    store,db,cache,old=setup_workflow(tmp_path,monkeypatch)
    def fail(*args):raise OSError('disk unavailable')
    monkeypatch.setattr(workflow,'reserve_index',fail)
    workflow.refresh_questions('A1','job',state_path=store.path)
    assert db.committed and json.loads(cache.get('factory:A1'))['status']=='completed'


def test_old_worker_cannot_overwrite_a_new_job(tmp_path,monkeypatch):
    store,db,cache,old=setup_workflow(tmp_path,monkeypatch)
    def takeover(*args,**kwargs):
        cache.set('factory-worker:A1','new-worker');cache.set('factory-lock:A1','new-job')
        cache.set('factory:A1',json.dumps(dict(id='new-job',status='running',progress=25)))
        return old
    monkeypatch.setattr(workflow,'prepare_pool',takeover)
    workflow.refresh_questions('A1','job',state_path=store.path)
    assert json.loads(cache.get('factory:A1'))==dict(id='new-job',status='running',progress=25)
    assert cache.get('factory-worker:A1')=='new-worker' and cache.get('factory-lock:A1')=='new-job'
    assert not db.committed


def test_published_questions_fill_shortages_without_fake_new_content(tmp_path,monkeypatch):
    store=reserve(tmp_path,per_skill=12)
    old=visual_reserve.combined_pool('A1',1,store,visual=[])
    previous={agent.content_hash(q) for qs in old.values() for q in qs}
    candidates=[q for q in store.questions('A1') if agent.content_hash(q) not in previous]
    store.write('A1.reserve.json',candidates[:1])
    monkeypatch.setattr(workflow,'visual_questions',lambda aid:[])
    monkeypatch.setattr(workflow,'generate_candidates',lambda *a,**k:pytest.fail('published fallback must avoid model calls'))
    new=workflow.prepare_pool('A1',2,store,lambda *a,**k:None,previous=previous,published=old)
    fresh=[q for qs in new.values() for q in qs if agent.content_hash(q) not in previous]
    retained=[q for qs in new.values() for q in qs if agent.content_hash(q) in previous]
    assert len(fresh)==1 and len(retained)==54
    original={q['id']:q for qs in old.values() for q in qs}
    assert all(q==original[q['id']] for q in retained)


def test_visual_v1_metadata_and_rule_rewording_are_not_new_content(tmp_path,monkeypatch):
    media=tmp_path/'data/samples';media.mkdir(parents=True)
    (media/'test.jpg').write_bytes(b'same actual source pixels')
    monkeypatch.setattr(agent,'ROOT',tmp_path);agent._local_sample_hash.cache_clear()
    old=dict(type='box',image='/media/test.jpg',sample_id='old-id',title='框出猫',answer=[dict(label='猫',box=[.1,.1,.3,.3])])
    new={**old,'sample_sha256':'different provenance representation','project_rule':'仅标任务指定的最大目标','title':'请紧贴猫四周画框'}
    assert agent.content_hash(old)==agent.content_hash(new)
    new['answer']=[dict(label='猫',box=[.2,.2,.3,.3])]
    assert agent.content_hash(old)!=agent.content_hash(new)
    agent._local_sample_hash.cache_clear()


def test_quality_review_is_bounded_and_renews_ownership(tmp_path,monkeypatch):
    store=reserve(tmp_path);rows=store.questions('A1')[:5]
    store.write('A1.reserve.json',rows)
    class EmptySession:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def scalars(self,*args):return []
    monkeypatch.setattr(agent,'Session',lambda engine:EmptySession())
    monkeypatch.setattr(agent,'question_statistics',lambda runs:{q['content_hash']:dict(suspect=True,sample_count=10,error_rate=.9) for q in rows})
    calls=[];leases=[]
    class Model:
        def json(self,system,payload):
            calls.append(payload)
            return {'reviews':[dict(index=0,decision='approved',duplicate=False,independent_answer='合规',**{name:1 for name in agent.QUALITY_MIN})]},'quality-review'
    agent.monitor_quality('A1',store,Model(),max_reviews=3,heartbeat=lambda:leases.append(True))
    assert len(calls)==3 and len(leases)>=7
    saved=store.questions('A1')
    assert sum(q.get('quality_review_sample_count')==10 for q in saved)==3
    assert sum(not q.get('quality_review_sample_count') for q in saved)==2


def test_worker_collision_and_interrupted_state_allow_retry(monkeypatch,tmp_path):
    cache=Cache();monkeypatch.setattr(workflow,'cache',cache)
    cache.set('factory:A1',json.dumps(dict(id='job',status='running',progress=0)))
    cache.set('factory-lock:A1','job');cache.set('factory-worker:A1','quality-worker')
    workflow.refresh_questions('A1','job',state_path=tmp_path)
    assert json.loads(cache.get('factory:A1'))['status']=='failed'
    assert not cache.exists('factory-lock:A1')
    assert cache.get('factory-worker:A1')=='quality-worker'
    cache.values.pop('factory-worker:A1')
    cache.set('factory:A1',json.dumps(dict(id='next',status='running',progress=45)))
    assert workflow.refresh_status('A1')['status']=='failed'


def test_module_start_uses_new_questions_and_keeps_old_run_snapshot(account,seeded_run):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from backend import main
    from backend.db import engine,Run,QuestionSet,User
    rid,old=seeded_run(account)
    # Only the QA run is changed. The shared published bank is not modified.
    with Session(engine) as db:
        run=db.get(Run,rid)
        changed=copy.deepcopy(run.questions);changed[0]['title']='旧版本保存的题目快照'
        run.questions=changed;db.commit()
        user=db.get(User,account['username'])
        published=db.scalar(select(QuestionSet).where(QuestionSet.ability_id=='A1',QuestionSet.active.is_(True)))
        started=main.start(main.StartBody(level_id='A1-L1'),user,db)
        assert started['id']!=rid
        new=db.get(Run,started['id'])
        assert new.questions==published.questions['A1-L1']
        assert db.get(Run,rid).questions==changed
        assert main.start(main.StartBody(level_id='A1-L1'),user,db)['id']==started['id']
