"""Deterministic grading only. The language model cannot mutate these results."""
import math
from PIL import Image, ImageDraw, ImageFilter, ImageChops

def valid_box(box):
    return isinstance(box,list) and len(box)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in box) and box[0]>=0 and box[1]>=0 and box[2]>0 and box[3]>0 and box[0]+box[2]<=1.002 and box[1]+box[3]<=1.002
def iou(a,b):
    if not valid_box(a) or not valid_box(b): return 0.0
    left=max(a[0],b[0]);top=max(a[1],b[1]);right=min(a[0]+a[2],b[0]+b[2]);bottom=min(a[1]+a[3],b[1]+b[3])
    intersection=max(0,right-left)*max(0,bottom-top)
    return intersection/(a[2]*a[3]+b[2]*b[3]-intersection) if intersection else 0.0
def polygon_metrics(user,truth):
    if not isinstance(user,list) or len(user)<3 or len(user)>500: return (0.,0.,1.,0.)
    if any(not isinstance(p,list) or len(p)!=2 or any(type(v) not in (float,int) or not math.isfinite(v) or v<0 or v>1 for v in p) for p in user): return (0.,0.,1.,0.)
    if user[0]==user[-1]: user=user[:-1]
    if len(user)<3: return (0.,0.,1.,0.)
    def orient(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    for i in range(len(user)):
        for j in range(i+2,len(user)):
            if i==0 and j==len(user)-1: continue
            a,b=user[i],user[(i+1)%len(user)];c,d=user[j],user[(j+1)%len(user)]
            if orient(a,b,c)*orient(a,b,d)<0 and orient(c,d,a)*orient(c,d,b)<0: return (0.,0.,1.,0.)
    def mask(points):
        im=Image.new('L',(384,384),0);ImageDraw.Draw(im).polygon([(round(x*383),round(y*383)) for x,y in points],fill=255);return im
    u,t=mask(user),mask(truth)
    def area(im): return sum(im.histogram()[1:])
    inter=area(ImageChops.darker(u,t));union=area(ImageChops.lighter(u,t))
    ub=ImageChops.subtract(u,u.filter(ImageFilter.MinFilter(5)));tb=ImageChops.subtract(t,t.filter(ImageFilter.MinFilter(5)))
    boundary_union=area(ImageChops.lighter(ub,tb))
    return inter/max(1,union),area(ImageChops.darker(ub,tb))/max(1,boundary_union),area(ImageChops.subtract(t,u))/max(1,area(t)),area(ImageChops.subtract(u,t))/max(1,area(u))
def grade(q,answer):
    answer=answer if isinstance(answer,dict) else {}
    kind=q['type']; expected=q['answer']; feedback=q.get('explanation','请对照本任务规范再检查一次。')
    result={'correct':False,'score':0.,'iou':None,'label_correct':0,'expected_count':1,'submitted_count':0,'missed':1,'false_positive':0,'feedback':feedback,'error_type':'UNANSWERED'}
    if kind in ('choice','text'):
        value=answer.get('value','');correct=value==expected
        result.update(correct=correct,score=100. if correct else 0.,label_correct=int(correct),submitted_count=int(bool(value)),missed=int(not value),false_positive=int(bool(value) and not correct),error_type='' if correct else 'LABEL_CONFUSION')
    elif kind=='entity':
        start,end=answer.get('start'),answer.get('end');label=answer.get('label')
        correct=type(start) is int and type(end) is int and start==expected['start'] and end==expected['end'] and label==expected['label']
        result.update(correct=correct,score=100. if correct else 0.,label_correct=int(label==expected['label']),submitted_count=int(start is not None),missed=int(start is None),false_positive=int(start is not None and not correct),error_type='' if correct else 'ENTITY_BOUNDARY')
    elif kind=='polygon':
        overlap,boundary,missing,extra=polygon_metrics(answer.get('points',[]),expected['polygon']);label_ok=answer.get('label')==expected['label'];correct=overlap>=.65 and label_ok
        result.update(correct=correct,score=round(100*overlap*int(label_ok),1),iou=overlap,boundary_iou=boundary,missing_area=missing,extra_area=extra,label_correct=int(label_ok),submitted_count=int(bool(answer.get('points'))),missed=int(overlap<.1),false_positive=int(bool(answer.get('points')) and overlap<.1),error_type='' if correct else 'POLYGON_BOUNDARY')
    elif kind=='box':
        boxes=answer.get('boxes',[])
        if not isinstance(boxes,list) or len(boxes)>50: boxes=[]
        gt=expected if isinstance(expected,list) else [expected]
        matches=[];used=set();labels=0
        weights=[]
        for target in gt:
            row=[]
            for b in boxes:
                overlap=iou(b.get('box',[]),target['box']) if isinstance(b,dict) else 0.
                same=isinstance(b,dict) and b.get('label')==target['label']
                row.append(overlap+(2 if same and overlap>=.1 else 0)+(4 if same and overlap>=q.get('threshold',.65) else 0))
            weights.append(row)
        assignment=optimal_assignment(weights)
        for k,target in enumerate(gt):
            j=assignment[k]
            best=iou(boxes[j].get('box',[]),target['box']) if 0<=j<len(boxes) and isinstance(boxes[j],dict) else 0.
            if best>=.1:
                used.add(j);labels+=int(boxes[j].get('label')==target['label'])
            matches.append(best)
        mean=sum(matches)/max(1,len(gt));missed=sum(x<.1 for x in matches);false=max(0,len(boxes)-len(used));correct=all(v>=q.get('threshold',.65) for v in matches) and labels==len(gt) and false==0
        result.update(correct=correct,score=round(100*mean*(labels/max(1,len(gt)))*(len(gt)/max(len(gt),len(boxes))),1),iou=mean,label_correct=labels,expected_count=len(gt),submitted_count=len(boxes),missed=missed,false_positive=false,error_type='' if correct else ('MISSED_TARGET' if missed else 'LABEL_CONFUSION' if labels<len(gt) else 'BOUNDING_BOX_BOUNDARY'))
    result['standard_answer']=expected
    return result

def optimal_assignment(weights):
    """Hungarian assignment: globally maximize label-aware one-to-one matching."""
    n=len(weights);m=max(n,max((len(r) for r in weights),default=0))
    if not n: return []
    costs=[[-x for x in row]+[0.]*(m-len(row)) for row in weights]
    u=[0.]*(n+1);v=[0.]*(m+1);p=[0]*(m+1);way=[0]*(m+1)
    for i in range(1,n+1):
        p[0]=i;j0=0;minimum=[float('inf')]*(m+1);used=[False]*(m+1)
        while True:
            used[j0]=True;i0=p[j0];delta=float('inf');j1=0
            for j in range(1,m+1):
                if not used[j]:
                    cur=costs[i0-1][j-1]-u[i0]-v[j]
                    if cur<minimum[j]: minimum[j]=cur;way[j]=j0
                    if minimum[j]<delta: delta=minimum[j];j1=j
            for j in range(m+1):
                if used[j]: u[p[j]]+=delta;v[j]-=delta
                else: minimum[j]-=delta
            j0=j1
            if p[j0]==0: break
        while True:
            j1=way[j0];p[j0]=p[j1];j0=j1
            if j0==0: break
    result=[-1]*n
    for j in range(1,m+1):
        if p[j]: result[p[j]-1]=j-1
    return result
def report(questions,answers):
    results=[dict(question_id=q['id'],title=q['title'],**grade(q,answers.get(q['id'],{}))) for q in questions]
    count=len(results);expected=sum(r['expected_count'] for r in results);submitted=sum(r['submitted_count'] for r in results)
    overlaps=[r['iou'] for r in results if r['iou'] is not None]
    score=round(sum(r['score'] for r in results)/max(1,count),1)
    accuracy=round(sum(r['label_correct'] for r in results)/max(1,expected)*100,1)
    missed=round(sum(r['missed'] for r in results)/max(1,expected)*100,1)
    extra=round(sum(r['false_positive'] for r in results)/max(1,submitted)*100,1)
    avg=round(sum(overlaps)/len(overlaps)*100,1) if overlaps else None
    return {'score':score,'label_accuracy':accuracy,'average_iou':avg,'missed_rate':missed,'false_positive_rate':extra,'correct_count':sum(r['correct'] for r in results),'count':count,'passed':score>=70 and missed<=10,'results':results,'criteria':'本训练试标要求：综合得分 ≥ 70 分，漏标率 ≤ 10%。此阈值仅用于本训练项目。','definitions':{'label_accuracy':'正确类别数 / 应标对象数','average_iou':'所有需定位题目的平均区域交并比，未标记对象按0计','missed_rate':'未匹配的应标对象数 / 应标对象数','false_positive_rate':'多余或错误标注数 / 已提交标注数'}}
