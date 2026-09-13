"""Real HTTP/PostgreSQL checks for learner-requested annotation references."""
import copy
import uuid
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from backend.db import Mistake, Run, engine, now
from backend.factory import load_initial_sets
from conftest import correct_answer


@pytest.fixture
def annotation_run(account):
    def create(kind='box', mode='course'):
        aid='A4' if kind=='box' else 'A5'
        initial=load_initial_sets()[aid]['questions']
        question=copy.deepcopy(next(q for qs in initial.values() for q in qs if q['type']==kind))
        rid=str(uuid.uuid4())
        suffix={'course':'L1','job':'JOB','competition':'RACE'}[mode]
        with Session(engine) as db:
            db.add(Run(id=rid,username=account['username'],ability_id=aid,
                       level_id=f'{aid}-{suffix}',mode=mode,questions=[question],answers={},
                       deadline=now()+timedelta(minutes=5) if mode=='competition' else None))
            db.commit()
        return rid,question
    return create


def submit(client,rid,question,answer):
    response=client.post(f'/api/runs/{rid}/answer',json={'question_id':question['id'],'answer':answer})
    assert response.status_code==200,response.text
    return response.json()


@pytest.mark.parametrize('kind',['box','polygon'])
def test_annotation_reference_requires_correct_or_three_consecutive_errors(account,account_factory,annotation_run,kind):
    client=account['client'];rid,q=annotation_run(kind)
    path=f'/api/runs/{rid}/questions/{q["id"]}/standard-answer'
    initial=client.get(f'/api/runs/{rid}').json()
    assert initial['question_feedback']=={} and 'answer' not in initial['questions'][0]
    assert client.get(path).status_code==403
    for attempt in range(1,5):
        result=submit(client,rid,q,{})
        assert 'standard_answer' not in result['result']
        assert result['wrong_attempts']==attempt
        assert result['can_view_standard'] is (attempt>=3)
        resumed=client.get(f'/api/runs/{rid}').json()['question_feedback'][q['id']]
        assert resumed['wrong_attempts']==attempt and resumed['correct'] is False
        assert resumed['can_view_standard'] is (attempt>=3)
        assert 'standard_answer' not in resumed
        revealed=client.get(path)
        assert revealed.status_code==(200 if attempt>=3 else 403)
        if attempt>=3: assert revealed.json()=={'standard_answer':q['answer']}
    with Session(engine) as db:
        stored=db.get(Run,rid)
        before=(copy.deepcopy(stored.answers),copy.deepcopy(stored.hints),stored.status)
    assert client.get(path).status_code==200
    with Session(engine) as db:
        stored=db.get(Run,rid)
        assert (stored.answers,stored.hints,stored.status)==before
    assert account_factory()['client'].get(path).status_code==404
    assert client.get(f'/api/runs/{rid}/questions/not-in-run/standard-answer').status_code==404


@pytest.mark.parametrize('kind',['box','polygon'])
def test_correct_annotation_unlocks_reference_and_resets_error_streak(account,annotation_run,kind):
    client=account['client'];rid,q=annotation_run(kind)
    path=f'/api/runs/{rid}/questions/{q["id"]}/standard-answer'
    for _ in range(2): submit(client,rid,q,{})
    correct=submit(client,rid,q,correct_answer(q))
    assert correct['result']['correct'] and correct['wrong_attempts']==0
    assert correct['can_view_standard'] and 'standard_answer' not in correct['result']
    assert client.get(path).json()['standard_answer']==q['answer']
    resumed=client.get(f'/api/runs/{rid}').json()['question_feedback'][q['id']]
    assert resumed['correct'] and resumed['can_view_standard'] and resumed['wrong_attempts']==0
    retried=submit(client,rid,q,{})
    assert retried['wrong_attempts']==1 and retried['can_view_standard'] is False
    assert client.get(path).status_code==403


@pytest.mark.parametrize('mode',['job','competition'])
def test_active_batch_never_reveals_annotation_result_or_reference(account,annotation_run,mode):
    client=account['client'];rid,q=annotation_run(mode=mode)
    path=f'/api/runs/{rid}/questions/{q["id"]}/standard-answer'
    for answer in ({},{},{},correct_answer(q)):
        saved=submit(client,rid,q,answer)
        assert not {'result','can_view_standard','wrong_attempts'}.intersection(saved)
        state=client.get(f'/api/runs/{rid}').json()
        assert state['question_feedback']=={} and state['question_status']=={}
        assert state['report'] is None and client.get(path).status_code==403
    completed=client.post(f'/api/runs/{rid}/finish').json()
    assert completed['report']['results'][0]['standard_answer']==q['answer']
    assert completed['report']['correct_count']==1
    assert client.get(path).json()['standard_answer']==q['answer']


@pytest.mark.parametrize('mode,level',[('onboarding','ONBOARDING'),('course','JT-vision-detection')])
def test_guided_annotation_reference_streak_does_not_add_formal_score_counters(account,annotation_run,mode,level):
    client=account['client'];rid,q=annotation_run()
    with Session(engine) as db:
        run=db.get(Run,rid);run.mode=mode;run.level_id=level
        db.commit()
    for _ in range(3): result=submit(client,rid,q,{})
    assert result['can_view_standard'] and result['wrong_attempts']==3
    assert client.get(f'/api/runs/{rid}/questions/{q["id"]}/standard-answer').status_code==200
    state=client.get(f'/api/runs/{rid}').json()
    assert state['question_feedback'][q['id']]['wrong_attempts']==3
    assert state['hints']=={f'course-wrong-attempts:{q["id"]}':3}
    assert client.get('/api/mistakes').json()==[]


def test_annotation_attempts_belong_to_each_question(account,annotation_run):
    client=account['client'];rid,first=annotation_run()
    second=copy.deepcopy(first);second['id']+='-second'
    with Session(engine) as db:
        db.get(Run,rid).questions=[first,second];db.commit()
    for _ in range(2): submit(client,rid,first,{})
    submit(client,rid,second,correct_answer(second))
    assert client.get(f'/api/runs/{rid}/questions/{first["id"]}/standard-answer').status_code==403
    third=submit(client,rid,first,{})
    assert third['wrong_attempts']==3 and third['can_view_standard']
    feedback=client.get(f'/api/runs/{rid}').json()['question_feedback']
    assert feedback[first['id']]['wrong_attempts']==3
    assert feedback[second['id']]['wrong_attempts']==0 and feedback[second['id']]['correct']


@pytest.mark.parametrize('kind',['box','polygon'])
def test_mistake_reference_uses_independent_persisted_review_streak(account,account_factory,annotation_run,kind):
    client=account['client'];rid,q=annotation_run(kind)
    for _ in range(3): submit(client,rid,q,{})
    item=client.get('/api/mistakes').json()[0];mid=item['id']
    path=f'/api/mistakes/{mid}/standard-answer'
    assert item['wrong_count']==3 and item['wrong_attempts']==0
    assert item['feedback'] is None and item['latest_review_answer'] is None
    assert item['can_view_standard'] is False and client.get(path).status_code==403
    score_before=client.get(f'/api/abilities/{q["skill_id"].split("-")[0]}').json()['skill_score']
    for attempt in range(1,4):
        response=client.post(f'/api/mistakes/{mid}/answer',json={'answer':{}})
        assert response.status_code==200,response.text
        reviewed=response.json()
        assert reviewed['wrong_attempts']==attempt and reviewed['affects_skill_score'] is False
        assert reviewed['can_view_standard'] is (attempt>=3)
        assert 'standard_answer' not in reviewed['result']
        resumed=client.get(f'/api/mistakes/{mid}').json()
        assert resumed['wrong_attempts']==attempt and resumed['latest_review_answer']=={}
        assert resumed['feedback']['correct'] is False and 'standard_answer' not in resumed['feedback']
        assert client.get(path).status_code==(200 if attempt>=3 else 403)
    assert client.get(path).json()['standard_answer']==q['answer']
    with Session(engine) as db:
        item=db.get(Mistake,mid)
        assert item.review_attempts==3 and item.review_wrong_attempts==3
    assert client.get(path).status_code==200
    with Session(engine) as db: assert db.get(Mistake,mid).review_attempts==3
    other=account_factory()['client']
    assert other.get(path).status_code==404
    assert other.post(f'/api/mistakes/{mid}/answer',json={'answer':{}}).status_code==404
    correct=client.post(f'/api/mistakes/{mid}/answer',json={'answer':correct_answer(q)}).json()
    assert correct['wrong_attempts']==0 and correct['can_view_standard']
    resumed=client.get(f'/api/mistakes/{mid}').json()
    assert resumed['feedback']['correct'] and resumed['can_view_standard']
    assert resumed['latest_review_answer']==correct_answer(q)
    assert client.get(path).status_code==200
    retried=client.post(f'/api/mistakes/{mid}/answer',json={'answer':{}}).json()
    assert retried['wrong_attempts']==1 and retried['can_view_standard'] is False
    assert client.get(path).status_code==403
    assert client.get(f'/api/abilities/{q["skill_id"].split("-")[0]}').json()['skill_score']==score_before
    assert client.delete(f'/api/mistakes/{mid}').status_code==200
    assert client.get(path).status_code==404
