"""Rebuild the committed, offline V1 question-set seed for maintainers."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from backend.catalog import ABILITIES
from backend.factory import generate_initial_set,validate

abilities={}
for ability in ABILITIES:
    aid=ability['id']
    questions=generate_initial_set(aid,1)
    validate(questions,aid)
    abilities[aid]={'version':1,'questions':questions}

payload={
    'schema_version':'1.0',
    'description':'智基随仓库发布的离线初始题库。克隆后首次启动直接导入，不调用网络或模型。',
    'abilities':abilities,
}
payload['question_hash']=hashlib.sha256(json.dumps(abilities,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
destination=ROOT/'data/initial-question-sets.json'
destination.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'已生成 {destination}：{sum(sum(len(qs) for qs in item["questions"].values()) for item in abilities.values())} 道题')
