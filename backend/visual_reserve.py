"""Executable exercises derived from source annotations; no AI-created geometry."""
import copy
import hashlib
import json
from collections import Counter
from functools import lru_cache
from .db import ROOT
from .grading import grade, iou

@lru_cache(maxsize=2000)
def sample_hash(filename):
    return hashlib.sha256((ROOT/'data/samples'/filename).read_bytes()).hexdigest()

def make_question(sample,aid,skill,selection='largest',kind='box'):
    targets=sample['targets'];largest=max(targets,key=lambda t:t['box'][2]*t['box'][3]) if targets else None
    chosen=([min(targets,key=lambda t:t['box'][2]*t['box'][3])] if selection=='smallest' else
            [t for t in targets if t['label']==largest['label']] if selection=='all' else [largest])
    industrial=sample.get('dataset')=='KolektorSDD'
    q={'id':'VIS-'+sample['id']+'-'+selection+'-'+kind,'type':kind,'skill_id':f'{aid}-S{skill}',
       'image':'/media/'+sample['file'],'width':sample['width'],'height':sample['height'],
       'sample_id':sample['id'],'sample_sha256':sample_hash(sample['file']),
       'source':'KolektorSDD · Kolektor Group / ViCoS Lab' if industrial else 'COCO 2017 · 官方标注练习',
       'source_url':sample.get('dataset_url') if industrial else sample['source_url'],
       'license':sample['license'],'gt_origin':'source_annotation','ai_generated':False,'threshold':.65,
       'hint':['先读清指定类别和范围，再从左到右观察。','放大检查目标的四周边缘，区分目标与背景。','按目标逐一复核边界和标签；多目标任务别把不同对象合并。']}
    q['labels']=list(dict.fromkeys([t['label'] for t in targets]+(['正常区域'] if industrial else ['猫','狗','行人','汽车','椅子'])))
    if kind=='choice':
        q['options']=['存在表面缺陷','无可见缺陷'] if industrial else list(dict.fromkeys([largest['label'],'猫','狗','行人','汽车','椅子']))[:6]
        q['answer']=('存在表面缺陷' if targets else '无可见缺陷') if industrial else largest['label']
        q['title']='判断这件工业表面样本是否存在可见缺陷。' if industrial else '观察图片，为画面中面积最大的目标选择类别。'
        q['project_rule']='本练习按官方二元缺陷标注判断，不区分裂纹和划痕子类别。' if industrial else '只判断指定的最大目标的类别，不需要画框。'
    elif kind=='polygon':
        q['answer']={'label':largest['label'],'polygon':largest['polygon']}
        q['title']=f'沿画面中最大的{largest["label"]}的可见轮廓，完成多边形标注。'
        q['project_rule']='只描绘目标最大的连续可见区域，不补画被遮挡部分；本练习不含孔洞或多区域掩码。'
    else:
        q['answer']=[{'box':t['box'],'label':t['label']} for t in chosen]
        label=chosen[0]['label']
        if selection=='all':
            q['title']=f'多目标检查：分别框出图中所有符合范围的{label}，并指定标签。'
            q['project_rule']=f'只标{label}类别，逐个画框；本图纳入官方标注面积占图像0.2%以上的非群组目标，其余类别与更小目标忽略。'
        elif selection=='smallest':
            q['title']=f'放大并查找画面中最小的{label}，框出它的边界。'
            q['project_rule']=f'本练习只标该类别最小的可辨识对象；小于图像面积0.2%的微小对象不纳入参考范围。'
        else:
            q['title']='定位这张工业图中的表面缺陷，紧贴缺陷范围画框。' if industrial else f'框出画面中最大的{label}，尽量贴合目标四周。'
            q['project_rule']='工业缺陷按官方掩码派生的紧致包围框判定；标签为表面缺陷，不推断缺陷原因。' if industrial else '仅标任务指定的最大目标；使用公开样本参考边界，不合并相邻对象。'
    q['title']+=' '+q['project_rule']
    q['explanation']='参考区域来自官方像素掩码的外轮廓与包围框。请检查缺陷边缘、遗漏和标签。' if industrial else '参考答案来自该图的官方标注。请按本题指定范围检查目标、边界和类别。'
    golden={'value':q['answer']} if kind=='choice' else {'points':q['answer']['polygon'],'label':q['answer']['label']} if kind=='polygon' else {'boxes':q['answer']}
    if not grade(q,golden)['correct']:return None
    q['grader_validation']={'golden_pass':True,'ground_truth_source':q['source_url']}
    return q

def visual_questions(aid):
    from .factory import samples
    result=[]
    for s in samples():
        targets=s['targets'];largest=max(targets,key=lambda t:t['box'][2]*t['box'][3]);smallest=min(targets,key=lambda t:t['box'][2]*t['box'][3])
        configs=[]
        if aid=='A4':
            configs=[(1,'largest','box'),(2,'largest','box'),(3,'largest','box')]
            if len([t for t in targets if t['label']==largest['label']])>=2:configs.append((4,'all','box'))
            if .002<=smallest.get('area_ratio',1)<.01:configs.append((5,'smallest','box'))
        elif aid=='A5' and largest.get('polygon_valid',False):
            configs=[(1,'largest','polygon'),(4,'largest','polygon')]
            if len(targets)>1 and any(t is not largest and iou(t['box'],largest['box'])>.05 for t in targets):configs.append((5,'largest','polygon'))
        elif aid=='A7':
            if len(targets)>1 and any(t is not largest and iou(t['box'],largest['box'])>.05 for t in targets):configs.append((1,'largest','box'))
            if len([t for t in targets if t['label']==largest['label']])>=3:configs.append((2,'all','box'))
            if .002<=smallest.get('area_ratio',1)<.01:configs.extend([(3,'smallest','box'),(5,'smallest','box')])
            if any(min(t['box'][0],t['box'][1],1-t['box'][0]-t['box'][2],1-t['box'][1]-t['box'][3])<.004 for t in [largest]):configs.append((4,'largest','box'))
        elif aid=='A3':configs=[(1,'largest','choice')]
        elif aid=='A9':configs=[(5,'largest','box')]
        elif aid=='A10':configs=[(2,'largest','box'),(3,'largest','box')]
        for skill,selection,kind in configs:
            q=make_question(s,aid,skill,selection,kind)
            if q:result.append(q)
    if aid=='A6':
        for s in samples(True):
            if s.get('dataset')!='KolektorSDD':continue
            if s['targets']:
                q=make_question(s,aid,1,'largest','box')
                if q:result.append(q)
            q=make_question(s,aid,4,kind='choice')
            if q:result.append(q)
    if aid=='A8':
        places=['北京','上海','杭州','成都','武汉','南京','合肥','深圳','重庆','青岛','长沙','西安']
        people=['林晓','王宁','陈安','李欣','周航','吴晨','赵月','郑雨','许明','杨可','宋哲','何佳']
        organizations=['星河科技','清远实验室','云川制造','远山学院','蓝海数据','新程中心']
        cases=[(f'{p}负责在{places[i]}开展数据质检。',places[i],'地点') for i,p in enumerate(people)]
        cases += [(f'{p}将试标报告交给项目负责人。',p,'人名') for p in people]
        cases += [(f'本次标注任务由{o}组织实施。',o,'机构') for o in organizations]
        for skill in (1,2):
            for i,(sentence,value,label) in enumerate(cases):
                result.append({'id':f'NER-S{skill}-{i}','type':'entity','skill_id':f'A8-S{skill}','title':f'选择句子中完整的{label}实体，并指定类型。','text':sentence,'labels':['地点','人名','机构'],'answer':{'start':sentence.index(value),'end':sentence.index(value)+len(value),'label':label},'project_rule':'实体包含名称本身，不包含动作、助词与标点；所有人名与机构均为虚构教学文本。','explanation':'结合语境选择完整名称，避免把介词、动词或标点包含在实体内。','hint':['先找到句子中有独立含义的名称。','结合语境判断名称表示人物、地点还是机构。','从名称第一个字到最后一个字选中，检查两端不要多选。'],'source':'智基原创虚构教学语料','source_url':'https://spacy.io/usage/linguistic-features#named-entities','ai_generated':False,'gt_origin':'authored_entity_span'})
    # The curriculum requires every skill and every level to have executable
    # image annotation. Reuse only source annotations already shipped with the
    # repository; do not invent boxes, polygons or image labels.
    if aid=='A6':
        for s in samples(True):
            if s.get('dataset')!='KolektorSDD' or not s['targets']:continue
            for skill in range(1,6):
                for kind in ('box','polygon'):
                    if kind=='polygon' and not max(s['targets'],key=lambda t:t['box'][2]*t['box'][3]).get('polygon_valid',False):continue
                    q=make_question(s,aid,skill,'largest',kind)
                    if q:q['curriculum_fallback']=True;result.append(q)
    for s in samples():
        largest=max(s['targets'],key=lambda t:t['box'][2]*t['box'][3])
        kind='polygon' if aid=='A5' else 'box'
        if kind=='polygon' and not largest.get('polygon_valid',False):continue
        for skill in range(1,6):
            q=make_question(s,aid,skill,'largest',kind)
            if q:q['curriculum_fallback']=True;result.append(q)
    return result

def combined_pool(aid,version,store,previous=(),visual=None,published=None):
    from .factory_agent import content_hash,balanced_plan,approve_review,validate_question
    visual=list(visual_questions(aid) if visual is None else visual)
    rows=store.questions(aid)
    retired={content_hash(q) for q in rows if q.get('status')=='retired'}
    visual=[q for q in visual if content_hash(q) not in retired]
    scenarios=[q for q in rows if q.get('status')=='approved']
    published=published or {}
    old_questions=[q for qs in published.values() for q in qs if content_hash(q) not in retired]
    old_limits=Counter(content_hash(q) for q in old_questions)
    previous=set(previous)
    rank=lambda q:(aid=='A6' and q.get('source','').startswith('COCO'),content_hash(q) in previous,hashlib.sha256(f'{version}:'.encode()+content_hash(q).encode()).hexdigest())
    visual.sort(key=rank);scenarios.sort(key=rank)
    enforce_visual_layout=bool(visual)
    pool={};used=set();usage=Counter();old_ids=set()
    for lid,skills in balanced_plan(aid).items():
        course='-L' in lid;visual_count=(2 if course else 10) if enforce_visual_layout else 0;pool[lid]=[]
        for index,sid in enumerate(skills):
            visual_slot=index<visual_count
            # Image annotation always comes first. Later slots keep the
            # existing choice/entity practice without interleaving another
            # box or polygon after it.
            options=([q for q in visual if q.get('image') and q['type'] in ('box','polygon')]
                     if visual_slot else [q for q in visual if not (q.get('image') and q['type'] in ('box','polygon'))]+scenarios)
            eligible=[q for q in options if q['skill_id']==sid and content_hash(q) not in used]
            # New content wins across both kinds of reserve. If this skill has
            # no fresh content, keep using its validated reserve; never relabel
            # another skill or alter IDs alone to claim a changed question.
            candidate=next((q for q in eligible if content_hash(q) not in previous),eligible[0] if eligible else None)
            retained=False
            if candidate is None:
                # A published question is an already validated fallback, not a
                # generated candidate. Preserve its original ID and content.
                # Existing V1 duplicates may be retained, never multiplied.
                backups=published.get(lid,[])+old_questions
                candidate=next((q for q in backups if q['skill_id']==sid and q['id'] not in old_ids
                    and bool(q.get('image') and q['type'] in ('box','polygon'))==visual_slot
                    and content_hash(q) not in retired and usage[content_hash(q)]<old_limits[content_hash(q)]),None)
                retained=candidate is not None
            if not candidate:raise ValueError(f'技能储备不足：{sid}')
            q=copy.deepcopy(candidate)
            if q.get('ai_generated'):
                validate_question(q,sid,q['evidence'])
                if not approve_review(q,q['ai_review']):raise ValueError('候选审核不通过')
            fingerprint=content_hash(q);used.add(fingerprint);usage[fingerprint]+=1
            if retained:old_ids.add(q['id'])
            else:q['content_hash']=fingerprint;q['id']=f'{lid}-V{version}-Q{index+1}'
            pool[lid].append(q)
    from .factory import validate
    validate(pool,aid)
    if enforce_visual_layout:
        from .factory import validate_visual_layout
        validate_visual_layout(pool,aid)
    if any(count>max(1,old_limits[fingerprint]) for fingerprint,count in usage.items()):raise ValueError('整套题目内容重复')
    return pool
