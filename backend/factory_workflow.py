"""Reserve -> validation -> atomic publication -> monitoring -> replacement."""
import json
import uuid
import subprocess
import sys
from collections import Counter
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from .db import ROOT,engine,cache,QuestionSet
from .catalog import ability
from .factory_agent import Store,content_hash,generate_candidates,monitor_quality,reserve_index
from .visual_reserve import combined_pool,visual_questions

def prepare_pool(aid,version,store,progress):
    visuals=visual_questions(aid)
    # Sources are fetched only when a requested visual skill lacks a reserve.
    required_visual={'A4':(1,2,3,4,5),'A5':(1,4),'A7':(1,2,3,4,5)}
    if aid in required_visual and any(sum(q['skill_id']==f'{aid}-S{s}' for q in visuals)<12 for s in required_visual[aid]):
        from .factory import samples,upload_media
        count=len(samples());target=min(400,count+80)
        if target>count:
            progress(15,'补充该技能所需的公开训练样本')
            result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/collect_samples.py'),str(target)],cwd=ROOT,capture_output=True,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode:raise ValueError('公开样本补充失败，保留原版本')
            upload_media();visuals=visual_questions(aid)
    for attempt in range(4):
        try:return combined_pool(aid,version,store)
        except ValueError as error:
            if not str(error).startswith('技能储备不足：'):raise
            sid=str(error).split('：')[-1]
            progress(25+attempt*12,f'补充并独立审核 {sid} 的训练情境')
            generate_candidates(aid,sid,6,store.questions(aid),store)
    return combined_pool(aid,version,store)

def refresh_questions(aid,job_id):
    store=Store(ROOT/'data/factory');token=uuid.uuid4().hex;worker=f'factory-worker:{aid}'
    if not cache.set(worker,token,nx=True,ex=1800):return
    def update(progress,stage,**extra):
        cache.expire(worker,1800);cache.expire(f'factory-lock:{aid}',1800)
        cache.set(f'factory:{aid}',json.dumps({'id':job_id,'progress':progress,'stage':stage,'status':'running',**extra},ensure_ascii=False),ex=3600)
    try:
        if not ability(aid):raise ValueError('无效能力编号')
        update(5,'统计题目质量，复核有疑问的候选')
        monitor_quality(aid,store)
        with Session(engine) as db:
            old=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active.is_(True)))
            version=old.version+1 if old else 1;baseline=old.id if old else None
            previous={content_hash(q) for qs in old.questions.values() for q in qs} if old else set()
        update(10,'按五项技能均衡规划课程、岗位与比赛')
        pool=prepare_pool(aid,version,store,update)
        if {content_hash(q) for qs in pool.values() for q in qs}==previous:
            # Reuse reserve first; replenish only when no new version can be formed.
            generate_candidates(aid,f'{aid}-S1',6,store.questions(aid),store)
            pool=prepare_pool(aid,version,store,update)
            if {content_hash(q) for qs in pool.values() for q in qs}==previous:raise ValueError('储备尚不能形成有变化的新题集')
        update(75,'验证标准答案、技能覆盖和内容重复')
        from .factory import validate
        validate(pool,aid)
        update(90,'原子发布新题集，保留历史训练快照')
        with Session(engine) as db:
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':92000+int(aid[1:])})
            current=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active.is_(True)).with_for_update())
            if (current.id if current else None)!=baseline:raise ValueError('版本已变化，请重试')
            if current:current.active=False
            db.add(QuestionSet(id=str(uuid.uuid4()),ability_id=aid,version=version,questions=pool));db.commit()
        store.audit(aid,'published',{'version':version,'count':55,'skill_counts':dict(Counter(q['skill_id'] for qs in pool.values() for q in qs))})
        reserve_index(store)
        update(100,'新题集已就绪',status='completed',version=version)
    except Exception as error:
        stage=str(error) if isinstance(error,ValueError) and not str(error).startswith('sk-') else '生成或审核暂未通过，原题集继续保留'
        cache.set(f'factory:{aid}',json.dumps({'id':job_id,'status':'failed','progress':0,'stage':stage},ensure_ascii=False),ex=3600)
        store.audit(aid,'failed',{'error_type':type(error).__name__})
    finally:
        cache.eval("if redis.call('get',KEYS[1]) == ARGV[1] then redis.call('del',KEYS[1]); redis.call('del',KEYS[2]); return 1 else return 0 end",2,worker,f'factory-lock:{aid}',token)

def monitor_pending():
    store=Store(ROOT/'data/factory')
    for key in cache.scan_iter(match='quality-dirty:A*'):
        aid=key.split(':')[-1]
        if not ability(aid) or cache.exists(f'factory-lock:{aid}'):continue
        token=uuid.uuid4().hex
        if not cache.set(f'factory-worker:{aid}',token,nx=True,ex=600):continue
        try:
            monitor_quality(aid,store)
            retired={q['content_hash'] for q in store.questions(aid) if q.get('status')=='retired'}
            with Session(engine) as db:
                active=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active.is_(True)))
                needs_replacement=bool(active and any(content_hash(q) in retired for qs in active.questions.values() for q in qs))
            cache.delete(key)
        finally:
            cache.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",1,f'factory-worker:{aid}',token)
        if needs_replacement and cache.set(f'factory-lock:{aid}',token,nx=True,ex=1800):refresh_questions(aid,str(uuid.uuid4()))
