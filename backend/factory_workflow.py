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
from .factory_agent import Store,content_hash,generate_candidates,monitor_quality,reserve_index,balanced_plan
from .visual_reserve import combined_pool,visual_questions

MAX_GENERATION_BATCHES = 8
MAX_BATCHES_PER_SKILL = 3


def refresh_status(aid):
    """A stopped worker must not leave the page permanently showing running."""
    key=f'factory:{aid}'
    result=json.loads(cache.get(key) or '{"status":"idle","progress":0}')
    if result.get('status')=='running' and not cache.exists(f'factory-lock:{aid}') and not cache.exists(f'factory-worker:{aid}'):
        result={**result,'status':'failed','stage':'更新任务已中断，原题集保留，请重新更新。'}
        # A concurrent new request owns a different id; do not replace its state.
        raw=cache.get(key)
        if raw and json.loads(raw).get('id')==result.get('id'):
            cache.set(key,json.dumps(result,ensure_ascii=False),ex=3600)
    return result


def prepare_pool(aid,version,store,progress,previous=(),published=None,allow_collection=True):
    visuals=visual_questions(aid)
    previous=set(previous)
    def build():return combined_pool(aid,version,store,previous=previous,visual=visuals,published=published)
    # A full usable reserve should cause zero generation or collection calls.
    try:
        pool=build()
        if not previous or any(content_hash(q) not in previous for qs in pool.values() for q in qs):return pool
    except ValueError as error:
        if not str(error).startswith('技能储备不足：'):raise
    # Sources are fetched only after an actual shortage, never on each refresh.
    required_visual={'A4':(1,2,3,4,5),'A5':(1,4),'A7':(1,2,3,4,5)}
    if allow_collection and aid in required_visual and any(sum(q['skill_id']==f'{aid}-S{s}' for q in visuals)<12 for s in required_visual[aid]):
        from .factory import samples,upload_media
        count=len(samples());target=min(400,count+80)
        if target>count and (ROOT/'data/downloads/annotations_trainval2017.zip').exists():
            progress(15,'补充该技能所需的公开训练样本')
            result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/collect_samples.py'),str(target)],cwd=ROOT,capture_output=True,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode:raise ValueError('公开样本补充失败，保留原版本')
            upload_media();visuals=visual_questions(aid)
    attempts=Counter()
    for attempt in range(MAX_GENERATION_BATCHES):
        try:
            pool=build()
            if not previous or any(content_hash(q) not in previous for qs in pool.values() for q in qs):return pool
            # The pool has enough questions but contains no fresh content. Pick
            # the skill with the fewest prior attempts, not always S1.
            sid=min((f'{aid}-S{i}' for i in range(1,6)),key=lambda s:attempts[s])
            shortage=1
        except ValueError as error:
            if not str(error).startswith('技能储备不足：'):raise
            sid=str(error).split('：')[-1]
            available={content_hash(q) for q in visuals+store.questions(aid) if q.get('skill_id')==sid and q.get('status','approved')=='approved'}
            required=sum(s==sid for skills in balanced_plan(aid).values() for s in skills)
            shortage=max(1,required-len(available))
        if attempts[sid]>=MAX_BATCHES_PER_SKILL:
            raise ValueError(f'{sid} 的新题尚未通过足量审核，已保留原题集；本轮补充已保存，可稍后重试。')
        attempts[sid]+=1
        progress(25+attempt*5,f'补充并独立审核 {sid} 的训练情境（第 {attempt+1} 批）',generation_batches=attempt+1)
        generate_candidates(aid,sid,min(6,max(3,shortage)),store.questions(aid),store)
    pool=build()
    if previous and not any(content_hash(q) not in previous for qs in pool.values() for q in qs):
        raise ValueError('本轮没有新增内容通过审核，原题集保留，请稍后重试。')
    return pool

def refresh_questions(aid,job_id,state_path=None,allow_collection=True):
    store=Store(state_path or ROOT/'data/factory');token=uuid.uuid4().hex;worker=f'factory-worker:{aid}'
    last_progress=0;published=None
    if not cache.set(worker,token,nx=True,ex=1800):
        current=json.loads(cache.get(f'factory:{aid}') or '{}')
        if current.get('id')==job_id:
            cache.set(f'factory:{aid}',json.dumps({'id':job_id,'progress':0,'status':'failed','stage':'当前模块正在校验题目，请稍后重新更新。'},ensure_ascii=False),ex=3600)
            cache.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",1,f'factory-lock:{aid}',job_id)
        return
    def save_status(payload):
        # State and lease updates share one ownership check. A late worker must
        # neither overwrite a newer job nor renew that newer job's gate.
        script="""-- factory-status-cas
        if redis.call('get',KEYS[2]) ~= ARGV[3] then return 0 end
        local gate=redis.call('get',KEYS[3])
        if gate and gate ~= ARGV[2] then return 0 end
        local old=redis.call('get',KEYS[1])
        if old and cjson.decode(old).id ~= ARGV[2] then return 0 end
        redis.call('expire',KEYS[2],1800)
        if gate == ARGV[2] then redis.call('expire',KEYS[3],1800) end
        redis.call('set',KEYS[1],ARGV[1],'EX',3600)
        return 1"""
        return cache.eval(script,3,f'factory:{aid}',worker,f'factory-lock:{aid}',json.dumps(payload,ensure_ascii=False),job_id,token)
    def update(progress,stage,**extra):
        nonlocal last_progress
        if cache.get(worker)!=token:raise ValueError('更新任务已中断，原题集保留，请重新更新。')
        last_progress=max(last_progress,progress)
        if not save_status({'id':job_id,'progress':last_progress,'stage':stage,'status':'running',**extra}):
            raise ValueError('更新任务已被后续任务接管。')
    try:
        if not ability(aid):raise ValueError('无效能力编号')
        # Quality review runs in monitor_pending, with its own worker lease.
        # Interactive refresh reads the resulting approved/retired state only.
        update(5,'读取已审核储备与题集版本')
        with Session(engine) as db:
            old=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active.is_(True)))
            version=old.version+1 if old else 1;baseline=old.id if old else None
            previous={content_hash(q) for qs in old.questions.values() for q in qs} if old else set()
            previous_pool=old.questions if old else {}
        update(10,'按五项技能均衡规划课程、岗位与比赛')
        pool=prepare_pool(aid,version,store,update,previous=previous,published=previous_pool,allow_collection=allow_collection)
        selected={content_hash(q) for qs in pool.values() for q in qs}
        fresh=selected-previous
        if not fresh:raise ValueError('储备尚不能形成有变化的新题集')
        changed_levels=[lid for lid,qs in pool.items() if any(content_hash(q) in fresh for q in qs)]
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
        published={'version':version,'question_count':sum(map(len,pool.values())),
                   'new_question_count':len(fresh),'reused_question_count':sum(map(len,pool.values()))-len(fresh),'changed_levels':changed_levels}
        # Report success immediately after the transaction commits. A failed
        # local audit/index write cannot undo PostgreSQL or mean "old retained".
        update(100,f'新题集已就绪，新增 {len(fresh)} 道内容',status='completed',**published)
        try:
            store.audit(aid,'published',{**published,'count':published['question_count'],'skill_counts':dict(Counter(q['skill_id'] for qs in pool.values() for q in qs))})
            reserve_index(store)
        except OSError:pass
    except Exception as error:
        if published:
            save_status({'id':job_id,'status':'completed','progress':100,'stage':'新题集已发布',**published})
        else:
            stage=str(error) if isinstance(error,ValueError) and 'sk-' not in str(error) else '生成或审核暂未通过，原题集继续保留，请稍后重试。'
            save_status({'id':job_id,'status':'failed','progress':last_progress,'stage':stage})
            store.audit(aid,'failed',{'error_type':type(error).__name__,'progress':last_progress})
    finally:
        cache.eval("if redis.call('get',KEYS[1]) == ARGV[1] then redis.call('del',KEYS[1]); if redis.call('get',KEYS[2]) == ARGV[2] then redis.call('del',KEYS[2]); end; return 1 else return 0 end",2,worker,f'factory-lock:{aid}',token,job_id)

def monitor_pending():
    store=Store(ROOT/'data/factory')
    for key in cache.scan_iter(match='quality-dirty:A*'):
        aid=key.split(':')[-1]
        if not ability(aid) or cache.exists(f'factory-lock:{aid}'):continue
        token=uuid.uuid4().hex
        if not cache.set(f'factory-worker:{aid}',token,nx=True,ex=600):continue
        try:
            def heartbeat():
                owned=cache.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('expire',KEYS[1],600) else return 0 end",1,f'factory-worker:{aid}',token)
                if not owned:raise ValueError('质量审核任务的处理权已变更')
            stats=monitor_quality(aid,store,max_reviews=3,heartbeat=heartbeat)
            heartbeat()
            retired={q['content_hash'] for q in store.questions(aid) if q.get('status')=='retired'}
            with Session(engine) as db:
                active=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active.is_(True)))
                needs_replacement=bool(active and any(content_hash(q) in retired for qs in active.questions.values() for q in qs))
            pending=any(stats.get(q['content_hash'],{}).get('suspect') and q.get('status')!='retired'
                and q.get('quality_review_sample_count',0)<stats[q['content_hash']]['sample_count'] for q in store.questions(aid))
            if pending:cache.expire(key,3600)
            else:cache.delete(key)
        finally:
            cache.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",1,f'factory-worker:{aid}',token)
        job_id=str(uuid.uuid4())
        if needs_replacement and cache.set(f'factory-lock:{aid}',job_id,nx=True,ex=1800):refresh_questions(aid,job_id)
