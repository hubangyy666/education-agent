"""Bounded browser QA fixtures, exclusively for the disposable QA account."""
import sys,json,uuid,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.db import User,Run,QuestionSet,engine,now
from backend.factory_agent import golden_answer

username='qa_browser_primary'
mode=sys.argv[1] if len(sys.argv)>1 else 'job'
if mode not in ('job','competition'):raise ValueError('Only bounded job/race fixtures')
with Session(engine) as db:
    user=db.get(User,username)
    if not user:raise ValueError('Run ui_test_account.py first')
    qs=db.scalar(select(QuestionSet).where(QuestionSet.ability_id=='A4',QuestionSet.active.is_(True)))
    level='A4-JOB' if mode=='job' else 'A4-RACE'
    questions=copy.deepcopy(qs.questions[level])
    if mode=='job':
        # Finish with a single visible target; include one intentional category
        # error earlier so the report has a real repair action to inspect.
        target=next(q for q in questions if q['type']=='box' and len(q['answer'])==1 and q['answer'][0]['box'][2]*q['answer'][0]['box'][3]>.1)
        questions=[q for q in questions if q['id']!=target['id']]+[target]
    answers={q['id']:golden_answer(q) for q in questions[:-1]} if mode=='job' else {}
    if mode=='job':
        bad=questions[0];answers[bad['id']]={}
    run=Run(id=str(uuid.uuid4()),username=username,ability_id='A4',level_id=level,mode=mode,questions=questions,answers=answers,deadline=now()+timedelta(seconds=20) if mode=='competition' else None)
    db.add(run);db.commit()
    print(json.dumps({'url':'http://127.0.0.1:5173/train/'+run.id,'mode':mode,'deadline':run.deadline.isoformat() if run.deadline else None,'saved':len(answers),'count':len(questions)},ensure_ascii=False))
