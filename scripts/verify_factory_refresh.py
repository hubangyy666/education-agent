"""Exercise the real refresh API against an isolated PostgreSQL schema/Redis keys.

Copies the chosen active bank and reserve. No demonstration user, shared version,
running server or shared Redis factory status is changed. Optional model calls
use the production workflow's strict, bounded generation and review policy.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from backend import db,main,factory_workflow as workflow,factory_agent as agent


class NamespacedCache:
    def __init__(self,base,prefix):self.base=base;self.prefix=prefix;self.states=[]
    def key(self,key):return self.prefix+key
    def set(self,key,value,**kw):
        if key.startswith('factory:'):self.states.append(json.loads(value))
        return self.base.set(self.key(key),value,**kw)
    def get(self,key):return self.base.get(self.key(key))
    def exists(self,key):return self.base.exists(self.key(key))
    def expire(self,key,*args):return self.base.expire(self.key(key),*args)
    def delete(self,*keys):return self.base.delete(*(self.key(k) for k in keys))
    def eval(self,script,numkeys,*args):return self.base.eval(script,numkeys,*(self.key(k) for k in args[:numkeys]),*args[numkeys:])


def verify(aid,state_path,output):
    nonce=uuid.uuid4().hex[:16];schema='qa_factory_'+nonce
    base_engine=db.engine;base_cache=db.cache
    with Session(base_engine) as session:
        current=session.scalar(select(db.QuestionSet).where(db.QuestionSet.ability_id==aid,db.QuestionSet.active.is_(True)))
        baseline=dict(id=current.id,version=current.version,questions=copy.deepcopy(current.questions))
    assert schema.startswith('qa_factory_') and schema.replace('_','').isalnum()
    with base_engine.begin() as connection:connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated=base_engine.execution_options(schema_translate_map={None:schema})
    isolated_cache=NamespacedCache(base_cache,schema+':')
    username='qa_agent_'+nonce
    root=db.ROOT;target=Path(state_path) if state_path else root/'.runtime'/schema
    target.mkdir(parents=True,exist_ok=True)
    if not (target/f'{aid}.reserve.json').exists():shutil.copyfile(root/f'data/factory/{aid}.reserve.json',target/f'{aid}.reserve.json')
    evidence={'ability_id':aid,'isolation':schema,'model_policy':'production bounded generation and independent review','shared_media_collection_disabled':True}
    try:
        db.Base.metadata.create_all(isolated)
        with Session(isolated) as session:
            session.add(db.User(username=username,name='Factory独立验收',password='unused',onboarding=True))
            session.add(db.QuestionSet(id=baseline['id'],ability_id=aid,version=baseline['version'],questions=baseline['questions'],active=True))
            session.commit()
        workflow.engine=isolated;agent.engine=isolated;workflow.cache=isolated_cache;main.cache=isolated_cache
        def session_override():
            with Session(isolated) as session:yield session
        def user_override():
            with Session(isolated) as session:return session.get(db.User,username)
        main.app.dependency_overrides[db.get_db]=session_override
        main.app.dependency_overrides[main.current_user]=user_override
        main.refresh_questions=lambda module,job:workflow.refresh_questions(module,job,state_path=target,allow_collection=False)
        # Deliberately do not enter the TestClient context manager: lifespan
        # startup would initialize the shared database and launch monitor loops.
        client=TestClient(main.app)
        try:
            old_response=client.post('/api/runs/start',json={'level_id':f'{aid}-L1'})
            assert old_response.status_code==200,old_response.text
            old_run=old_response.json()['id']
            response=client.post(f'/api/abilities/{aid}/refresh')
            assert response.status_code==200,response.text
            status=client.get(f'/api/abilities/{aid}/refresh').json()
            evidence['refresh_status']=status
            evidence['progress']=isolated_cache.states
            assert status['status']=='completed',status
            new_response=client.post('/api/runs/start',json={'level_id':f'{aid}-L1'})
            assert new_response.status_code==200,new_response.text
            new_run=new_response.json()['id']
            assert old_run!=new_run
            with Session(isolated) as session:
                active=list(session.scalars(select(db.QuestionSet).where(db.QuestionSet.ability_id==aid,db.QuestionSet.active.is_(True))))
                assert len(active)==1 and active[0].version==baseline['version']+1
                previous={agent.content_hash(q) for qs in baseline['questions'].values() for q in qs}
                selected={agent.content_hash(q) for qs in active[0].questions.values() for q in qs}
                assert len(selected-previous)==status['new_question_count']>0
                assert session.get(db.Run,old_run).questions==baseline['questions'][f'{aid}-L1']
                assert session.get(db.Run,new_run).questions==active[0].questions[f'{aid}-L1']
                evidence.update(old_version=baseline['version'],new_version=active[0].version,
                    fresh_content_count=len(selected-previous),old_run_snapshot_preserved=True,
                    new_run_uses_published_content=True,exactly_one_active_version=True)
            assert client.post('/api/runs/start',json={'level_id':f'{aid}-L1'}).json()['id']==new_run
        finally:client.close()
    finally:
        main.app.dependency_overrides.clear()
        with base_engine.begin() as connection:connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        keys=list(base_cache.scan_iter(match=schema+':*'))
        if keys:base_cache.delete(*keys)
        with Session(base_engine) as session:
            current=session.scalar(select(db.QuestionSet).where(db.QuestionSet.ability_id==aid,db.QuestionSet.active.is_(True)))
            evidence['shared_question_set_unchanged']=current.id==baseline['id'] and current.questions==baseline['questions']
        evidence['isolated_schema_removed']=True
        evidence['isolated_redis_removed']=not list(base_cache.scan_iter(match=schema+':*'))
        Path(output).write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ability',default='A1');parser.add_argument('--state');parser.add_argument('--output',default='docs/factory-refresh-live-evidence.json')
    args=parser.parse_args()
    print(json.dumps(verify(args.ability,args.state,args.output),ensure_ascii=False,indent=2))
