import os
import json
import secrets
import uuid
import asyncio
from datetime import timedelta, timezone
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, Depends, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import init_db, get_db, engine, cache, storage, ROOT, User, Run, Progress, QuestionSet, Knowledge, TaskCard, now, password_valid
from .catalog import ABILITIES, ability, levels
from .factory import initialize_sets, public_question, samples, image_question, choice
from .grading import grade, report
from . import tutor
from .factory_workflow import refresh_questions,monitor_pending

@asynccontextmanager
async def lifespan(app):
    init_db();initialize_sets()
    task=asyncio.create_task(expiration_loop())
    quality_task=asyncio.create_task(quality_loop())
    yield
    quality_task.cancel()
    with suppress(asyncio.CancelledError): await quality_task
    task.cancel()
    with suppress(asyncio.CancelledError): await task
app=FastAPI(title='智基学习平台',version='1.0.0',lifespan=lifespan)

@app.middleware('http')
async def browser_security(request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin not in ('http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:4173','http://127.0.0.1:8000',os.getenv('PUBLIC_ORIGIN','')):
            return Response('来源校验失败',status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    if request.url.path.startswith('/api'): response.headers['Cache-Control']='no-store'
    return response

def current_user(request:Request,db:Session=Depends(get_db)):
    token=request.cookies.get('zhiji_session','')
    username=cache.get(f'session:{token}') if token else None
    user=db.get(User,username) if username else None
    if not user: raise HTTPException(401,'请先登录你的学习账号。')
    return user
def user_dict(user): return {k:getattr(user,k) for k in ('username','name','onboarding','goal','daily_goal','voice')}
def user_progress(db,username): return list(db.scalars(select(Progress).where(Progress.username==username)))
from .adaptive import ability_state, recommendation, learner_context

def get_run(run_id,user,db,lock=False):
    stmt=select(Run).where(Run.id==run_id,Run.username==user.username)
    if lock: stmt=stmt.with_for_update()
    run=db.scalar(stmt)
    if not run: raise HTTPException(404,'没有找到这个训练任务。')
    if run.status=='active' and run.deadline and now()>=run.deadline: finish(run,db)
    return run
def finish(run,db):
    if run.status!='active': return
    run.report=report(run.questions,run.answers);run.status='completed';run.finished_at=now()
    key=f'{run.username}:{run.level_id}'
    if run.mode!='onboarding':
        p=db.get(Progress,key)
        if p: p.score=max(p.score,run.report['score']);p.attempts+=1;p.completed_at=now()
        else: db.add(Progress(id=key,username=run.username,ability_id=run.ability_id,level_id=run.level_id,score=run.report['score']))
    db.commit()
    if run.mode!='onboarding': cache.set(f'quality-dirty:{run.ability_id}',1,ex=86400)

async def quality_loop():
    while True:
        await asyncio.sleep(30)
        try: await asyncio.to_thread(monitor_pending)
        except Exception:
            import logging
            logging.getLogger('zhiji').exception('题目质量监测失败，将重试')

def expire_due_runs():
    with Session(engine) as db:
        due=list(db.scalars(select(Run).where(Run.status=='active',Run.deadline!=None,Run.deadline<=now()).with_for_update(skip_locked=True)))
        for run in due: finish(run,db)
async def expiration_loop():
    while True:
        try: await asyncio.to_thread(expire_due_runs)
        except Exception:
            import logging
            logging.getLogger('zhiji').exception('到期任务结算失败，将重试')
        await asyncio.sleep(1)
def run_dict(run):
    return {'id':run.id,'ability_id':run.ability_id,'level_id':run.level_id,'mode':run.mode,'status':run.status,'questions':[public_question(q) for q in run.questions],'answers':run.answers,'deadline':run.deadline,'server_time':now(),'report':run.report,'started_at':run.started_at,'hints':run.hints,'revision_of':run.revision_of}

class LoginBody(BaseModel):
    username:str=Field(min_length=1,max_length=40)
    password:str=Field(min_length=1,max_length=128)
@app.post('/api/auth/login')
def login(body:LoginBody,request:Request,response:Response,db:Session=Depends(get_db)):
    ip=request.client.host if request.client else 'local';key=f'login_attempt:{ip}:{body.username}'
    if int(cache.get(key) or 0)>=12: raise HTTPException(429,'尝试次数较多，请两分钟后再试。')
    user=db.get(User,body.username)
    if not user or not password_valid(body.password,user.password):
        cache.incr(key);cache.expire(key,120);raise HTTPException(401,'用户名或密码不正确，请再检查一下。')
    cache.delete(key)
    old=request.cookies.get('zhiji_session')
    if old: cache.delete(f'session:{old}')
    token=secrets.token_urlsafe(40);cache.set(f'session:{token}',user.username,ex=86400*7)
    response.set_cookie('zhiji_session',token,httponly=True,samesite='lax',secure=os.getenv('COOKIE_SECURE')=='true',max_age=86400*7)
    return user_dict(user)
@app.get('/api/auth/me')
def me(user:User=Depends(current_user)): return user_dict(user)
@app.post('/api/auth/logout')
def logout(request:Request,response:Response):
    token=request.cookies.get('zhiji_session')
    if token: cache.delete(f'session:{token}')
    response.delete_cookie('zhiji_session');return {'ok':True}
@app.get('/api/health')
def health(db:Session=Depends(get_db)):
    db.execute(select(1));cache.ping()
    if not storage.bucket_exists('zhiji-training'): raise HTTPException(503,'训练素材存储尚未就绪')
    return {'status':'ok','database':'PostgreSQL + pgvector','cache':'Redis','storage':'MinIO','knowledge_count':db.scalar(select(func.count()).select_from(Knowledge)),'sample_count':len(samples(True)),'embedding':os.getenv('EMBEDDING_BACKEND','hash'),'general_model':os.getenv('GENERAL_MODEL'),'question_model':os.getenv('QUESTION_MODEL')}
@app.get('/api/abilities')
def abilities(user:User=Depends(current_user),db:Session=Depends(get_db)): return ability_state(db,user)
@app.get('/api/abilities/{aid}')
def module(aid:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=next((a for a in ability_state(db,user) if a['id']==aid),None)
    if not item: raise HTTPException(404,'没有找到这个能力模块。')
    qs=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active==True));item['version']=qs.version if qs else 0
    item['update']=json.loads(cache.get(f'factory:{aid}') or 'null')
    return item
@app.get('/api/dashboard')
def dashboard(user:User=Depends(current_user),db:Session=Depends(get_db)):
    states=ability_state(db,user);runs=list(db.scalars(select(Run).where(Run.username==user.username,Run.status=='completed').order_by(Run.finished_at.desc())))
    china=timezone(timedelta(hours=8));today=now().astimezone(china).date();activities={}
    for r in runs:
        if not r.report: continue
        day=r.finished_at.astimezone(china).date().isoformat();activities[day]=activities.get(day,0)+r.report['count']
    today_runs=[r for r in runs if r.finished_at.astimezone(china).date()==today];today_count=sum(r.report['count'] for r in today_runs);today_correct=sum(r.report['correct_count'] for r in today_runs)
    streak=0;date=today if activities.get(today.isoformat()) else today-timedelta(days=1)
    while activities.get(date.isoformat()): streak+=1;date-=timedelta(days=1)
    count=sum(r.report['count'] for r in runs if r.report);completed=sum(a['completed'] for a in states)
    badges=[{'id':'first','name':'第一枚标注','description':'完成新手入门体验','icon':'ScanLine','earned':user.onboarding},{'id':'ten','name':'小步不停','description':'累计完成 10 道题目','icon':'Zap','earned':count>=10},{'id':'course','name':'学有所成','description':'完成 5 个技能关卡','icon':'GraduationCap','earned':completed>=5},{'id':'quality','name':'质量守护者','description':'岗位任务达到试标要求','icon':'ShieldCheck','earned':any(r.mode=='job' and r.report['passed'] for r in runs)},{'id':'race','name':'迎接挑战','description':'完成一次限时比赛','icon':'Trophy','earned':any(r.mode=='competition' for r in runs)}]
    active=db.scalar(select(Run).where(Run.username==user.username,Run.status=='active',Run.mode!='onboarding').order_by(Run.started_at.desc()))
    return {'user':user_dict(user),'abilities':states,'recommendation':recommendation(states,user.goal),'today_count':today_count,'today_rate':round(sum(r.report['score']*r.report['count'] for r in today_runs)/today_count,1) if today_count else 0,'total_count':count,'completed_levels':completed,'streak':streak,'activities':activities,'badges':badges,'diagnostic':user.diagnostic,'active_run':{'id':active.id,'ability_id':active.ability_id,'answered':len(active.answers),'count':len(active.questions)} if active else None,'recent_runs':[{'id':r.id,'ability_id':r.ability_id,'level_id':r.level_id,'mode':r.mode,'score':r.report['score'],'date':r.finished_at,'passed':r.report['passed']} for r in runs[:8]]}
class SettingsBody(BaseModel):
    name:str=Field(min_length=1,max_length=20)
    goal:str
    daily_goal:int=Field(ge=5,le=60)
    voice:bool
@app.post('/api/profile')
def profile(body:SettingsBody,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if body.goal not in ('岗位入门','课程补强','竞赛备战'): raise HTTPException(422,'请选择有效的学习目标。')
    for k,v in body.model_dump().items(): setattr(user,k,v)
    db.commit();return user_dict(user)

@app.post('/api/onboarding/start')
def start_onboarding(user:User=Depends(current_user),db:Session=Depends(get_db)):
    existing=db.scalar(select(Run).where(Run.username==user.username,Run.mode=='onboarding',Run.status=='active'))
    if existing: return run_dict(existing)
    reserve=samples()
    if len(reserve)<2: raise HTTPException(503,'教学图片尚未就绪，请稍后再试。')
    import random
    qs=[image_question('A4',2,0,1,reserve[0]),image_question('A4',2,1,1,reserve[1])]
    qs[0]['guide_box']=qs[0]['answer'][0]['box'];qs[0]['guide_label']=qs[0]['answer'][0]['label']
    qs += [choice(a,1,i,1,random.Random(i)) for i,a in enumerate(['A1','A2','A4'])]
    run=Run(id=str(uuid.uuid4()),username=user.username,ability_id='A1',level_id='ONBOARDING',mode='onboarding',questions=qs)
    db.add(run);db.commit();return run_dict(run)
class OnboardingBody(BaseModel): goal:str='岗位入门';daily_goal:int=Field(default=10,ge=5,le=60);run_id:str
@app.post('/api/onboarding/complete')
def complete_onboarding(body:OnboardingBody,user:User=Depends(current_user),db:Session=Depends(get_db)):
    run=get_run(body.run_id,user,db,True)
    if run.mode!='onboarding': raise HTTPException(400,'训练类型不正确。')
    if body.goal not in ('岗位入门','课程补强','竞赛备战'): raise HTTPException(422,'学习目标不正确。')
    if len(run.answers)<5 or not grade(run.questions[1],run.answers.get(run.questions[1]['id'],{}))['correct']: raise HTTPException(400,'请先完成独立标注和三道学情诊断题。')
    finish(run,db);user.onboarding=True;user.goal=body.goal;user.daily_goal=body.daily_goal
    user.diagnostic={'score':run.report['score'],'skills':[{'ability_id':q['skill_id'].split('-')[0],'skill_id':q['skill_id'],'correct':grade(q,run.answers.get(q['id'],{}))['correct']} for q in run.questions[2:]],'completed_at':now().isoformat()}
    db.commit();return user_dict(user)
class StartBody(BaseModel): level_id:str
@app.post('/api/runs/start')
def start(body:StartBody,user:User=Depends(current_user),db:Session=Depends(get_db)):
    aid=body.level_id.split('-')[0];a=next((a for a in ability_state(db,user) if a['id']==aid),None)
    if not a: raise HTTPException(404,'没有找到这个模块。')
    lv=next((l for l in a['levels'] if l['id']==body.level_id),None)
    if not lv or not lv['unlocked']: raise HTTPException(403,'先完成前面的关卡，再来开启这一关。')
    if cache.exists(f'factory-lock:{aid}'): raise HTTPException(409,'题目正在更新，请等待新题集发布。')
    existing=db.scalar(select(Run).where(Run.username==user.username,Run.level_id==body.level_id,Run.status=='active').order_by(Run.started_at.desc()))
    if existing:
        existing=get_run(existing.id,user,db)
        if existing.status=='active': return run_dict(existing)
    qs=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active==True))
    run=Run(id=str(uuid.uuid4()),username=user.username,ability_id=aid,level_id=body.level_id,mode=lv['mode'],questions=qs.questions[body.level_id],deadline=now()+timedelta(minutes=lv['minutes']) if lv['mode']=='competition' else None)
    db.add(run);db.commit();return run_dict(run)
@app.get('/api/runs/{run_id}')
def read_run(run_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return run_dict(get_run(run_id,user,db,True))
class AnswerBody(BaseModel): question_id:str;answer:dict
@app.post('/api/runs/{run_id}/answer')
def submit_answer(run_id:str,body:AnswerBody,user:User=Depends(current_user),db:Session=Depends(get_db)):
    run=get_run(run_id,user,db,True)
    if run.status!='active': raise HTTPException(409,'本次训练已结束，请查看结果。')
    q=next((q for q in run.questions if q['id']==body.question_id),None)
    if not q: raise HTTPException(404,'题目不属于本次训练。')
    if len(json.dumps(body.answer))>50000: raise HTTPException(422,'标注数据过大。')
    result=grade(q,body.answer);run.answers={**run.answers,body.question_id:body.answer}
    # Retrying is allowed; only the latest committed answer is scored.
    db.commit()
    if run.mode in ('course','onboarding'): return {'saved':True,'result':result}
    return {'saved':True,'answered':len(run.answers),'count':len(run.questions)}
@app.post('/api/runs/{run_id}/finish')
def finish_run(run_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    run=get_run(run_id,user,db,True)
    if run.mode=='course' and len(run.answers)<len(run.questions): raise HTTPException(400,'请先完成本关的全部题目。')
    if run.mode=='job' and len(run.answers)<len(run.questions): raise HTTPException(400,'任务包还有未处理的样本，请全部处理后提交。')
    finish(run,db);return run_dict(run)
@app.post('/api/runs/{run_id}/repair')
def repair_run(run_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    old=get_run(run_id,user,db)
    if old.status!='completed' or old.mode!='job': raise HTTPException(400,'只有已质检的岗位任务可以返修。')
    bad={r['question_id'] for r in old.report['results'] if not r['correct']}
    if not bad: raise HTTPException(400,'这次任务没有需要返修的样本。')
    run=Run(id=str(uuid.uuid4()),username=user.username,ability_id=old.ability_id,level_id=old.level_id,mode='job',questions=old.questions,answers={k:v for k,v in old.answers.items() if k not in bad},revision_of=old.id)
    db.add(run);db.commit();return run_dict(run)
@app.post('/api/abilities/{aid}/refresh')
def refresh(aid:str,background:BackgroundTasks,user:User=Depends(current_user)):
    if not ability(aid): raise HTTPException(404,'没有找到这个模块。')
    if not cache.set(f'factory-lock:{aid}',user.username,nx=True,ex=1800): raise HTTPException(409,'当前模块正在更新题目。')
    jid=str(uuid.uuid4());cache.set(f'factory:{aid}',json.dumps({'id':jid,'progress':0,'stage':'准备更新','status':'running'}),ex=3600)
    background.add_task(refresh_questions,aid,jid);return {'id':jid,'progress':0,'stage':'准备更新','status':'running'}
@app.get('/api/abilities/{aid}/refresh')
def refresh_status(aid:str,user:User=Depends(current_user)): return json.loads(cache.get(f'factory:{aid}') or '{"status":"idle","progress":0}')

class ChatBody(BaseModel):
    message:str=Field(min_length=1,max_length=1500)
    mode:str='GENERAL_TUTOR'
    run_id:str|None=None
    question_id:str|None=None
    history:list[dict]=Field(default_factory=list,max_length=10)
@app.post('/api/ai/chat')
async def chat(body:ChatBody,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if body.mode not in ('GENERAL_TUTOR','QUESTION_TUTOR'): raise HTTPException(422,'辅导模式不正确。')
    question=None;run=None;submitted=False;hint_count=0;result=None;aid=None;skill=None
    if body.mode=='QUESTION_TUTOR':
        if not body.run_id or not body.question_id: raise HTTPException(422,'请从当前题目打开小基。')
        run=get_run(body.run_id,user,db,True)
        question=next((q for q in run.questions if q['id']==body.question_id),None)
        if not question: raise HTTPException(404,'没有找到当前题目。')
        aid=run.ability_id;skill=question['skill_id'];hint_count=(run.hints or {}).get(question['id'],0)
        # No mid-package answer explanations during jobs or competitions.
        submitted=question['id'] in run.answers and (run.mode in ('course','onboarding') or run.status=='completed')
        if run.mode=='competition' and run.status=='active': raise HTTPException(403,'比赛进行中暂停导师提示，提交后可以复盘。')
        if submitted: result=grade(question,run.answers[question['id']])
        run.hints={**(run.hints or {}),question['id']:hint_count+1};db.commit()
    states=ability_state(db,user);rec=recommendation(states,user.goal);aid=aid or rec['ability_id']
    learner=learner_context(user,states,aid,skill)
    sources=tutor.retrieve(db,body.message,aid,skill,project_id=question.get('project_id') if question else None,context=learner,question=question,history=body.history) if tutor.in_scope(body.message,question is not None,body.history) else []
    async def stream():
        yield 'event: status\ndata: '+json.dumps({'text':'正在结合你的学习情况查找资料…'},ensure_ascii=False)+'\n\n'
        task=asyncio.create_task(tutor.answer(body.message,body.mode,learner,sources,question,hint_count,submitted,result,body.history,run.answers.get(question['id']) if run and submitted else None))
        while not task.done():
            done,_=await asyncio.wait({task},timeout=5)
            if not done: yield ': keepalive\n\n'
        output=await task
        for i in range(0,len(output['text']),22):
            yield 'event: token\ndata: '+json.dumps({'text':output['text'][i:i+22]},ensure_ascii=False)+'\n\n'
            await asyncio.sleep(.01)
        yield 'event: done\ndata: '+json.dumps({k:v for k,v in output.items() if k!='text'},ensure_ascii=False)+'\n\n'
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

class TaskBody(BaseModel): text:str=Field(min_length=10,max_length=4000);goal:str='岗位入门'
@app.post('/api/tasks/convert')
async def convert(body:TaskBody,user:User=Depends(current_user),db:Session=Depends(get_db)):
    mapping=[('A6',['工业','缺陷','裂纹','划痕']),('A8',['文本','实体','情感','语义']),('A5',['分割','轮廓','像素']),('A7',['自动驾驶','遮挡','道路']),('A9',['质检','审核','返修']),('A4',['检测','框','图像','图片'])]
    aid=next((a for a,words in mapping if any(w in body.text for w in words)),'A10');a=ability(aid)
    content={'name':a['short']+' · 岗位学习任务','description':body.text,'scenario':body.text,'ability_id':aid,'goal':body.goal,'knowledge':[a['skills'][0],a['skills'][2],a['skills'][4]],'skills':a['skills'],'steps':[{'title':'读懂任务','description':'确认项目目标、数据范围、标签定义与验收标准。','output':'一份任务规范核对清单'},{'title':'完成小批量试标','description':'选择代表性样本，按规范操作并记录不确定项。','output':'试标样本及疑难问题记录'},{'title':'复核并完善规则','description':'对照参考答案与质检意见，分析边界、类别及遗漏。','output':'修订后的操作规范和错误案例'},{'title':'执行训练任务包','description':'连续处理样本，提交前完成自检。','output':'完整标注任务包'},{'title':'复盘与返修','description':'阅读质量报告，对薄弱技能安排强化练习。','output':'质量报告、返修记录与学习计划'}],'safety':['只使用获授权、已脱敏的训练数据。','项目规则不明确时记录并澄清，不擅自推测。','本平台训练阈值仅用于教学，企业验收以实际协议为准。'],'resources':[{'title':a['name']+'互动训练','url':f'/skills/{aid}'},{'title':'CVAT 官方标注工作流','url':'https://docs.cvat.ai/docs/annotation/annotation-workflow/'}],'provider':'rules','ai_generated':False}
    content['clarifications']=['当前项目的标签定义与特殊情况处理规则','输出格式、交付清单和质检验收口径']
    if aid in ('A4','A5','A6','A7'): content['clarifications'].insert(0,'按可见区域还是完整目标标注，以及最小目标尺寸要求')
    sources=tutor.retrieve(db,body.text,aid)
    try:
        from openai import AsyncOpenAI
        client=AsyncOpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'),base_url=os.getenv('DEEPSEEK_BASE_URL'),timeout=35,max_retries=0)
        response=await client.chat.completions.create(model=os.getenv('GENERAL_MODEL'),messages=[{'role':'system','content':tutor.SYSTEM+'\n将企业任务转换成教学任务卡。仅输出JSON，键为name（名称）、scenario（情境）、steps（3-6步，每项title/description/output）、knowledge（知识点字符串列表）、safety（3条数据安全或项目规范提醒）。不编造企业验收阈值或不存在的校内资源。特别注意：用户未指定可见框/完整框、遮挡边界或最小尺寸时，必须在步骤中要求先确认项目规范，禁止自己默认只标可见部分或补全遮挡目标。'},{'role':'user','content':json.dumps({'task':body.text,'goal':body.goal,'ability':a,'sources':sources},ensure_ascii=False)}],response_format={'type':'json_object'},max_tokens=1600,extra_body={'thinking':{'type':'disabled'}})
        generated=json.loads(response.choices[0].message.content)
        if isinstance(generated.get('steps'),list) and 3<=len(generated['steps'])<=6 and all(isinstance(s,dict) and all(isinstance(s.get(k),str) for k in ('title','description','output')) for s in generated['steps']):
            for key in ('name','scenario'):
                if isinstance(generated.get(key),str): content[key]=generated[key][:4000]
            for key in ('knowledge','safety'):
                if isinstance(generated.get(key),list) and all(isinstance(v,str) for v in generated[key]): content[key]=generated[key][:8]
            content['steps']=generated['steps'];content['provider']='deepseek';content['ai_generated']=True
    except Exception: content['notice']='模型暂不可用，已按岗位教学规则生成任务卡。'
    content['sources']=sources;record=TaskCard(id=str(uuid.uuid4()),username=user.username,content=content);db.add(record);db.commit()
    return {'id':record.id,**content}
@app.get('/api/tasks')
def tasks(user:User=Depends(current_user),db:Session=Depends(get_db)): return [{'id':t.id,**t.content} for t in db.scalars(select(TaskCard).where(TaskCard.username==user.username).order_by(TaskCard.created_at.desc()))]
@app.get('/api/knowledge')
def knowledge(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [{'id':k.id,'title':k.title,'ability_id':k.ability_id,'scope':k.scope,'content':k.content,'source_url':k.meta.get('source_url',k.meta.get('source',{}).get('source_url',''))} for k in db.scalars(select(Knowledge))]
@app.get('/media/{filename}')
def media(filename:str):
    allowed={s['file'] for s in samples(True)}
    if filename not in allowed: raise HTTPException(404,'没有找到训练素材。')
    obj=storage.get_object('zhiji-training',filename)
    def chunks():
        try:
            yield from obj.stream(1024*64)
        finally: obj.close();obj.release_conn()
    return StreamingResponse(chunks(),media_type='image/jpeg',headers={'Cache-Control':'public, max-age=86400'})

# Built production frontend can be served by the same FastAPI origin.
if (ROOT/'dist').exists():
    from fastapi.staticfiles import StaticFiles
    app.mount('/assets',StaticFiles(directory=ROOT/'dist/assets'),name='assets')
    @app.get('/{path:path}')
    def frontend(path:str):
        if path.startswith(('api/','media/')): raise HTTPException(404)
        file=(ROOT/'dist'/path).resolve()
        if file.is_relative_to((ROOT/'dist').resolve()) and file.is_file(): return FileResponse(file)
        return FileResponse(ROOT/'dist/index.html')
