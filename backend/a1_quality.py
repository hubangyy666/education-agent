"""Content checks scoped to the A1 curriculum correction."""
import json
from functools import lru_cache

from .db import ROOT


@lru_cache(maxsize=1)
def rejected_hashes():
    review = json.loads((ROOT / 'data/a1-question-review.json').read_text(encoding='utf-8'))
    return {row['content_hash'] for row in review['rejected']}


@lru_cache(maxsize=2048)
def _text_profile(kind, title, body, rule, sample_hash):
    from .factory_agent import content_hash, normalize
    fingerprint = content_hash({'type': kind, 'title': title, 'text': body,
                                'project_rule': rule, 'sample_sha256': sample_hash})
    text = normalize((title or '') + (body or ''))
    grams = frozenset(text[i:i + 3] for i in range(max(0, len(text) - 2)))
    return fingerprint, grams


def _profile(question):
    return _text_profile(*(question.get(key) for key in
                          ('type', 'title', 'text', 'project_rule', 'sample_sha256')))


def duplicates_candidate(question, selected):
    from .factory_agent import content_hash
    visual = question['type'] in ('box', 'polygon')
    fingerprint, grams = (content_hash(question), None) if visual else _profile(question)
    for existing in selected:
        # Even different targets on the same picture feel repetitive here.
        if question.get('image') and question.get('image') == existing.get('image'):
            return True
        if question['type'] != existing['type']:
            continue
        other, other_grams = (content_hash(existing), None) if visual else _profile(existing)
        if fingerprint == other:
            return True
        if grams and other_grams and len(grams & other_grams) / len(grams | other_grams) >= .82:
            return True
    return False


def validate_a1_content(pool):
    from .catalog import levels
    from .factory_agent import content_hash
    selected = []
    for level in levels('A1'):
        for question in pool.get(level['id'], []):
            if level['mode'] == 'course' and question['skill_id'] != level['skill_id']:
                raise ValueError(f'{level["id"]} 题目与课关技能不符')
            if content_hash(question) in rejected_hashes():
                raise ValueError('A1 题目已因技能错配或内容重复被排除')
            if duplicates_candidate(question, selected):
                raise ValueError('A1 关卡题目或图片重复')
            selected.append(question)


def needs_repair(pool):
    try:
        validate_a1_content(pool)
    except ValueError:
        return True
    return False
