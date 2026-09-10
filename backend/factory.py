import json
import hashlib
import random
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from .catalog import ABILITIES, FACTS, ability, levels
from .db import ROOT, QuestionSet, engine, cache, storage
from .grading import grade, valid_box

def samples(include_industrial=False):
    path=ROOT/'data/samples/manifest.json'
    rows=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    industrial=ROOT/'data/industrial/manifest.json'
    if include_industrial and industrial.exists(): rows+=json.loads(industrial.read_text(encoding='utf-8'))
    return rows
def choice(aid,skill,i,version,rng):
    fact=FACTS[aid][i%len(FACTS[aid])];title,correct,wrong,explanation=fact;options=[correct,*wrong];rng.shuffle(options)
    return {'id':f'{aid}-{skill}-V{version}-C{i}','type':'choice','title':title,'options':options,'answer':correct,'skill_id':f'{aid}-S{skill}','explanation':explanation,'hint':['先读清任务要判断的对象，区分概念与操作。','把选项逐一对照当前任务规范，排除没有依据的推断。','优先考虑可追溯、有明确规则且不凭空猜测的处理方式。'],'source':'智基原创教学题 · 基于公开标注规范','source_url':'https://docs.cvat.ai/docs/annotation/annotation-workflow/'}
def image_question(aid,skill,i,version,sample,kind='box'):
    target=max(sample['targets'],key=lambda t:t['box'][2]*t['box'][3]);labels=list(dict.fromkeys([target['label'],'猫','狗','行人','汽车','椅子']))[:6]
    title=f'请找到画面中最大的{target["label"]}，'+('沿轮廓完成多边形标注。' if kind=='polygon' else '框出目标并选择标签。')
    expected={'label':target['label'],'polygon':target['polygon']} if kind=='polygon' else [target]
    return {'id':f'{aid}-{skill}-V{version}-I{i}','type':kind,'title':title,'labels':labels,'image':f'/media/{sample["file"]}','width':sample['width'],'height':sample['height'],'answer':expected,'skill_id':f'{aid}-S{skill}','threshold':.65,'explanation':'对照标准区域检查边界是否贴合，并确认类别。官方标注仅作为此公开样本练习的参考。','hint':['先从左到右观察画面，找出任务要求的对象。','关注目标上下左右的可见边界，避免纳入太多背景。','试着先定位最上、最下、最左和最右的边界，再完成标注。'],'source':'COCO 2017 公开样本 · 官方 Ground Truth','source_url':sample['source_url'],'license':sample['license'],'sample_id':sample['id']}
def entity_question(aid,skill,i,version):
    cases=[('小王在北京工作。','北京','地点'),('张华加入了星河科技。','星河科技','机构'),('李明正在学习数据标注。','李明','人名'),('这家企业位于上海。','上海','地点'),('陈晨负责项目的质量审核。','陈晨','人名')]
    sentence,value,label=cases[i%len(cases)];start=sentence.index(value)
    return {'id':f'{aid}-{skill}-V{version}-E{i}','type':'entity','title':f'选中这句话中的{label}实体，并指定类型。','text':sentence,'labels':['人名','地点','机构'],'answer':{'start':start,'end':start+len(value),'label':label},'skill_id':f'{aid}-S{skill}','explanation':'实体范围应完整覆盖名称本身，不包含无关动词、助词或标点。','hint':['先找句子中有独立含义的专有名称。','实体可以是人物、地理位置或机构，请结合语境。','选择完整的名称，检查两端是否多选了助词或标点。'],'source':'智基原创脱敏教学文本','source_url':'https://spacy.io/usage/linguistic-features#named-entities'}
def generate_initial_set(aid,version=1):
    """Build the authored V1 curriculum without network or model calls.

    This is kept as the reproducible source for the committed cold-start seed.
    Runtime initialization loads the frozen artifact instead of regenerating it.
    """
    rng=random.Random(f'{aid}:{version}');reserve=samples();rng.shuffle(reserve);pool={}
    for lv in levels(aid):
        si=int(lv['skill_id'].split('S')[1]);questions=[]
        for i in range(lv['count']):
            question_skill=si if lv['mode']=='course' else i%5+1
            # Course scaffolding introduces concepts then meaningful manipulation.
            if reserve and aid in ('A4','A5','A7') and (lv['mode']!='course' or i>=2):
                q=image_question(aid,question_skill,i,version,reserve[(i+question_skill*3)%len(reserve)],'polygon' if aid=='A5' else 'box')
            elif aid=='A8' and (i%2==0): q=entity_question(aid,question_skill,i,version)
            elif reserve and aid in ('A1','A2','A3','A9') and lv['mode']=='job':
                q=image_question(aid,question_skill,i,version,reserve[(i+question_skill)%len(reserve)])
            else: q=choice(aid,question_skill,(question_skill-1)*2+i+version-1,version,rng)
            q['id']=f'{lv["id"]}-V{version}-Q{i+1}';q['instruction']='先观察，再判断。需要帮助时可以向小基要一点提示。';questions.append(q)
        pool[lv['id']]=questions
    validate(pool,aid)
    return pool

def generate_set(aid,version):
    reserve_path=ROOT/'data/factory'/f'{aid}.reserve.json'
    if reserve_path.exists():
        from .factory_agent import Store
        from .visual_reserve import combined_pool
        try:
            return combined_pool(aid,version,Store(ROOT/'data/factory'))
        except ValueError as error:
            if not str(error).startswith('技能储备不足：'): raise
    return generate_initial_set(aid,version)

def load_initial_sets():
    path=ROOT/'data/initial-question-sets.json'
    if not path.exists(): raise RuntimeError('缺少随仓库发布的初始题库 data/initial-question-sets.json')
    payload=json.loads(path.read_text(encoding='utf-8'))
    if payload.get('schema_version')!='1.0' or set(payload.get('abilities',{}))!={a['id'] for a in ABILITIES}:
        raise RuntimeError('初始题库结构无效')
    expected=hashlib.sha256(json.dumps(payload['abilities'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if payload.get('question_hash')!=expected: raise RuntimeError('初始题库内容校验失败')
    result={}
    for a in ABILITIES:
        item=payload['abilities'][a['id']]
        if item.get('version')!=1: raise RuntimeError(f'{a["id"]} 初始题库版本必须为 1')
        validate(item.get('questions',{}),a['id'])
        result[a['id']]=item
    return result
def validate(pool,aid):
    identifiers=set()
    for lv in levels(aid):
        qs=pool.get(lv['id'],[])
        if len(qs)!=lv['count'] or not 5<=len(qs)<=20: raise ValueError('关卡题量不符合要求')
        for q in qs:
            if q['id'] in identifiers: raise ValueError('题目ID重复')
            identifiers.add(q['id'])
            if not q.get('title') or not q.get('explanation') or not q.get('source_url'): raise ValueError('题目教学或来源信息缺失')
            if not q['skill_id'].startswith(aid+'-S'): raise ValueError('技能映射错误')
            if q['type']=='box':
                if not all(valid_box(t['box']) for t in q['answer']): raise ValueError('无效标准框')
                golden={'boxes':q['answer']}
            elif q['type']=='polygon': golden={'points':q['answer']['polygon'],'label':q['answer']['label']}
            elif q['type']=='entity': golden=q['answer']
            else:
                if q['answer'] not in q['options'] or len(set(q['options']))!=len(q['options']): raise ValueError('选项或答案无效')
                golden={'value':q['answer']}
            if not grade(q,golden)['correct']: raise ValueError('标准答案无法被判分器正确执行')
def initialize_sets():
    initial=load_initial_sets()
    with Session(engine) as db:
        for a in ABILITIES:
            if not db.scalar(select(QuestionSet).where(QuestionSet.ability_id==a['id'],QuestionSet.active==True)):
                item=initial[a['id']]
                db.add(QuestionSet(id=str(uuid.uuid4()),ability_id=a['id'],version=item['version'],questions=item['questions']))
        db.commit()
    upload_media()

def upload_media():
    for s in samples(True):
        file=ROOT/'data/samples'/s['file']
        storage.fput_object('zhiji-training',s['file'],str(file),content_type='image/jpeg')
def refresh_questions(aid,job_id):
    key=f'factory:{aid}'
    def update(progress,stage,**extra): cache.set(key,json.dumps({'id':job_id,'progress':progress,'stage':stage,'status':'running',**extra},ensure_ascii=False),ex=3600)
    try:
        update(10,'检查训练素材储备')
        if aid in ('A4','A5','A7') and not samples(): raise ValueError('图像储备不足，请先运行素材采集脚本')
        with Session(engine) as db:
            current=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active==True));version=current.version+1 if current else 1
            update(30,'均衡规划技能覆盖')
            pool=generate_set(aid,version)
            update(65,'校验标准答案与可执行判分')
            validate(pool,aid)
            update(85,'检查重复与来源，发布新版本')
            if current: current.active=False
            db.add(QuestionSet(id=str(uuid.uuid4()),ability_id=aid,version=version,questions=pool));db.commit()
            cache.set(key,json.dumps({'id':job_id,'progress':100,'stage':'新题集已就绪','status':'completed','version':version}),ex=3600)
    except Exception as e:
        cache.set(key,json.dumps({'id':job_id,'progress':0,'stage':str(e),'status':'failed'}),ex=3600)
    finally: cache.delete(f'factory-lock:{aid}')
def public_question(q,show_answer=False):
    fields={'id','type','title','options','labels','image','width','height','text','skill_id','instruction','source','source_url','license','ai_generated','project_rule','guide_box','guide_label','preannotation'}
    if show_answer: fields.update({'answer','hint','explanation','threshold'})
    return {k:v for k,v in q.items() if k in fields}
