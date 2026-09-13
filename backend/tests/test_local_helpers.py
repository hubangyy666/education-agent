import asyncio
import copy
import json
from types import SimpleNamespace
import pytest
from backend import factory, tutor
from backend.factory import generate_set, public_question

class FakeCache:
    def __init__(self): self.values={};self.updates=[];self.deleted=[]
    def set(self,key,value,**kw): self.values[key]=value;self.updates.append((key,json.loads(value)));return True
    def delete(self,key): self.deleted.append(key);self.values.pop(key,None)

class FakeSession:
    def __init__(self,current): self.current=current;self.added=[];self.committed=False
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def scalar(self,statement): return self.current
    def add(self,item): self.added.append(item)
    def commit(self): self.committed=True

def test_refresh_version_publishes_once_using_isolated_storage(monkeypatch):
    current=SimpleNamespace(version=7,active=True,questions={'old':'snapshot'})
    fake_db=FakeSession(current);fake_cache=FakeCache()
    monkeypatch.setattr(factory,'Session',lambda engine:fake_db)
    monkeypatch.setattr(factory,'cache',fake_cache)
    factory.refresh_questions('A1','qa-local-refresh')
    status=json.loads(fake_cache.values['factory:A1'])
    assert status['status']=='completed' and status['version']==8 and status['progress']==100
    assert fake_db.committed and len(fake_db.added)==1 and current.active is False
    assert current.questions=={'old':'snapshot'}
    assert fake_db.added[0].version==8
    assert all('-V8-' in q['id'] for qs in fake_db.added[0].questions.values() for q in qs)
    assert 'factory-lock:A1' in fake_cache.deleted
    assert [update['progress'] for _,update in fake_cache.updates]==[10,30,65,85,100]

def test_refresh_failed_generation_preserves_previous_release(monkeypatch):
    current=SimpleNamespace(version=7,active=True)
    fake_db=FakeSession(current);fake_cache=FakeCache()
    monkeypatch.setattr(factory,'Session',lambda engine:fake_db)
    monkeypatch.setattr(factory,'cache',fake_cache)
    def fail(*args): raise ValueError('QA deliberate validation failure')
    monkeypatch.setattr(factory,'generate_set',fail)
    factory.refresh_questions('A1','qa-local-refresh')
    status=json.loads(fake_cache.values['factory:A1'])
    assert status['status']=='failed' and current.active is True
    assert not fake_db.committed and not fake_db.added
    assert 'factory-lock:A1' in fake_cache.deleted

@pytest.mark.parametrize('aid', [f'A{i}' for i in range(1,11)])
def test_generated_pool_shape_and_sanitization(aid):
    pool=generate_set(aid,41)
    assert len(pool)==7 and sum(len(qs) for qs in pool.values())==65
    for qs in pool.values():
        for q in qs:
            assert not {'answer','hint','explanation','threshold'}.intersection(public_question(q))

def test_local_hint_levels_and_post_submit():
    q={'hint':['观察','特征','步骤'],'answer':'不可提前给出'}
    assert [tutor.safe_hint(q,i,False) for i in range(5)]==['观察','特征','步骤','步骤','步骤']
    result={'correct':False,'feedback':'边界包含过多背景','iou':.5}
    assert '50.0%' in tutor.safe_hint(q,0,True,result)
    assert q['answer'] not in tutor.safe_hint(q,0,False)

def test_local_tutor_fallback_never_calls_model(monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    q={'hint':['观察目标','查看特征','检查边界'],'type':'box','answer':[]}
    output=asyncio.run(tutor.answer('请给我标注提示','QUESTION_TUTOR',{},[],q,1))
    assert output['provider']=='knowledge' and output['text']=='查看特征'
    output=asyncio.run(tutor.answer('天气怎么样','GENERAL_TUTOR',{},[]))
    assert output['provider']=='platform' and output['sources']==[]
    assert '模型尚未配置' in output['text']

def test_start_blocked_by_refresh_lock_without_changing_shared_redis(account, monkeypatch):
    from backend import main
    from backend.db import engine,User
    from sqlalchemy.orm import Session
    from fastapi import HTTPException
    monkeypatch.setattr(main,'cache',SimpleNamespace(exists=lambda key:key=='factory-lock:A1'))
    with Session(engine) as db:
        user=db.get(User,account['username'])
        with pytest.raises(HTTPException) as error:
            main.start(main.StartBody(level_id='A1-L1'),user,db)
        assert error.value.status_code==409
