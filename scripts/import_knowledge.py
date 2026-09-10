"""Only reviewed knowledge is imported. Duplicate checks precede database writes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
from difflib import SequenceMatcher
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.db import Knowledge,engine,init_db,ROOT
from backend.tutor import embed,tokens

def import_file(path):
    entries=json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(entries,dict): entries=entries.get('knowledge',entries.get('items',entries.get('units',[])))
    added=0;updated=0;skipped=[]
    with Session(engine) as db:
        existing=list(db.scalars(select(Knowledge)))
        for index,k in enumerate(entries):
            review=k.get('ai_review') or {}
            minimum={'source_reliability':.85,'factual_consistency':.90,'scope_relevance':.85,'clarity':.80,'final_score':.86}
            approved=(review.get('decision')=='approved' and review.get('independent_from_candidate_generation') is True and review.get('conflict_detected') is False and all(isinstance(review.get(key),(int,float)) and review[key]>=value for key,value in minimum.items()))
            if not approved: skipped.append({'id':k.get('id',index),'reason':'未通过独立审核或评分/一致性门槛'});continue
            if not all(k.get(key) for key in ['title','content','scope']): raise ValueError('必需知识字段缺失')
            if not 100<=len(k['content'])<=400: raise ValueError('知识正文须为100至400字')
            if k['scope'] not in ('GENERAL','ABILITY'): raise ValueError('知识分类不正确')
            if k['scope']=='ABILITY' and k.get('ability_id') not in [f'A{i}' for i in range(1,11)]: raise ValueError('能力知识缺少有效板块')
            source=k.get('source',k)
            if not source.get('source_url','').startswith('https://'): raise ValueError('缺少可信来源URL')
            if k['scope']=='GENERAL' and (k.get('ability_id') or k.get('skill_id')): raise ValueError('通用知识不得污染能力范围')
            kid=str(k.get('id') or f'K{index+1:03}')
            saved=db.get(Knowledge,kid)
            if saved:
                if saved.meta!=k:
                    saved.title=k['title'];saved.content=k['content'];saved.scope=k['scope'];saved.ability_id=k.get('ability_id');saved.skill_id=k.get('skill_id');saved.meta=k;saved.embedding=embed(k['title']+' '+k['content']);updated+=1
                continue
            vec=embed(k['title']+' '+k['content']);duplicate=False
            for old in existing:
                a=set(tokens(k['content']));b=set(tokens(old.content))
                if max(SequenceMatcher(None,k['title'],old.title).ratio(),len(a&b)/max(1,len(a|b)),sum(x*y for x,y in zip(vec,old.embedding)))>=.92:
                    duplicate=True;break
            if duplicate: skipped.append({'id':k.get('id',index),'reason':'重复度超过阈值'});continue
            kid=str(k.get('id') or f'K{index+1:03}')
            if db.get(Knowledge,kid): continue
            item=Knowledge(id=kid,title=k['title'],content=k['content'],scope=k['scope'],ability_id=k.get('ability_id'),skill_id=k.get('skill_id'),meta=k,embedding=vec)
            db.add(item);existing.append(item);added+=1
        db.commit()
    output={'added':added,'updated':updated,'skipped':skipped,'embedding_backend':'词法哈希1024维' if __import__('os').getenv('EMBEDDING_BACKEND')!='bge' else 'BGE-M3'}
    (ROOT/'data/knowledge/import-report.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False))
if __name__=='__main__':
    init_db();import_file(sys.argv[1] if len(sys.argv)>1 else ROOT/'data/knowledge/knowledge.reviewed.json')
