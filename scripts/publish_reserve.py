"""Publish only complete, fully validated local reserve combinations; no AI calls."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,uuid
from collections import Counter
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from backend.db import ROOT,engine,cache,QuestionSet
from backend.factory_agent import Store,content_hash,reserve_index
from backend.visual_reserve import combined_pool
from backend.factory import upload_media

store=Store(ROOT/'data/factory');results={}
for aid in sys.argv[1:] or [f'A{i}' for i in range(1,11)]:
    if aid not in [f'A{i}' for i in range(1,11)]:raise ValueError('无效能力')
    token=str(uuid.uuid4())
    if not cache.set(f'factory-lock:{aid}',token,nx=True,ex=300):
        results[aid]={'status':'busy'};continue
    try:
        with Session(engine) as db:
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':92000+int(aid[1:])})
            current=db.scalar(select(QuestionSet).where(QuestionSet.ability_id==aid,QuestionSet.active.is_(True)).with_for_update())
            version=current.version+1 if current else 1
            pool=combined_pool(aid,version,store)
            if current:current.active=False
            db.add(QuestionSet(id=token,ability_id=aid,version=version,questions=pool));db.commit()
        counts=Counter(q['skill_id'] for qs in pool.values() for q in qs)
        results[aid]={'status':'published','version':version,'count':sum(counts.values()),'skills':dict(counts),'unique_content':len({content_hash(q) for qs in pool.values() for q in qs}),'types':dict(Counter(q['type'] for qs in pool.values() for q in qs))}
        store.audit(aid,'offline_validated_publish',results[aid])
    except ValueError as error:results[aid]={'status':'not_ready','reason':str(error)}
    finally:cache.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",1,f'factory-lock:{aid}',token)
upload_media();reserve_index(store)
(ROOT/'docs/reserve-publication.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
