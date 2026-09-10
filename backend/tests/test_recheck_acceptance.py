"""Live fixed-version acceptance. No shared dataset mutations or model calls."""
import copy
import json
import time
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.db import engine, ROOT, Run, Progress, QuestionSet, Knowledge, now
from backend.grading import grade
from conftest import correct_answer


def active_snapshots():
    with Session(engine) as db:
        return [
            {'ability_id': row.ability_id, 'version': row.version, 'questions': copy.deepcopy(row.questions)}
            for row in db.scalars(select(QuestionSet).where(QuestionSet.active.is_(True)))
        ]


SNAPSHOTS = active_snapshots()
QUESTIONS = [q for snapshot in SNAPSHOTS for questions in snapshot['questions'].values() for q in questions]


def test_background_competition_expiration_without_run_api(account, seeded_run):
    # The account's HTTP login has already happened before this Run exists.
    deadline = now() + timedelta(milliseconds=250)
    rid, questions = seeded_run(account, 'A1-RACE', 'competition', deadline=deadline)
    # Intentionally no HTTP calls to GET/finish/answer/dashboard after seeding.
    # Only the already-running server background loop may settle this Run.
    before_wait = time.monotonic()
    time.sleep(3)
    waited = time.monotonic() - before_wait
    with Session(engine) as db:
        run = db.get(Run, rid)
        progress = db.get(Progress, f'{account["username"]}:A1-RACE')
        evidence = {
            'test': 'background_competition_expiration_without_run_api',
            'run_id': rid,
            'waited_seconds': round(waited, 3),
            'deadline': deadline.isoformat(),
            'observed_at': now().isoformat(),
            'status': run.status,
            'finished_at': run.finished_at.isoformat() if run.finished_at else None,
            'report_score': run.report['score'] if run.report else None,
            'report_missed_rate': run.report['missed_rate'] if run.report else None,
            'report_count': run.report['count'] if run.report else None,
            'progress_attempts': progress.attempts if progress else None,
            'run_api_calls_after_creation': 0,
        }
        Path(__file__).with_name('background-expiration-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        assert waited >= 3
        assert run.status == 'completed', evidence
        assert run.finished_at is not None and run.finished_at >= deadline
        assert run.report['score'] == 0 and run.report['missed_rate'] == 100
        assert run.report['count'] == len(questions) == 10
        assert progress is not None and progress.attempts == 1


def test_knowledge_matches_reviewed_records(account):
    with Session(engine) as db:
        rows = list(db.scalars(select(Knowledge)))
        reviewed = json.loads((ROOT / 'data/knowledge/knowledge.reviewed.json').read_text(encoding='utf-8'))
        assert len(rows) == len(reviewed) >= 50
        assert len({row.id for row in rows}) == len(reviewed)
        scopes = Counter('GENERAL' if row.scope == 'GENERAL' else row.ability_id for row in rows)
        # Independent review deliberately moved the SQuAD item from GENERAL to A8.
        # Validate against that reviewed source instead of the draft 5-per-scope plan.
        reviewed = json.loads((ROOT / 'data/knowledge/knowledge.reviewed.json').read_text(encoding='utf-8'))
        reviewed_scopes = Counter('GENERAL' if row['scope']=='GENERAL' else row.get('ability_id') for row in reviewed)
        assert scopes == reviewed_scopes
        assert scopes['GENERAL'] >= 1 and all(scopes[f'A{i}'] >= 5 for i in range(1,11))
        assert all(row.title.strip() and row.content.strip() for row in rows)
        assert all(len(row.embedding) == 1024 for row in rows)
        assert all(row.meta.get('ai_review',{}).get('decision')=='approved' for row in rows)
        evidence = {
            'knowledge_count':len(rows),
            'scope_counts':dict(scopes),
            'embedding_dimensions':sorted({len(row.embedding) for row in rows}),
            'review_metadata_count':sum(bool(row.meta.get('ai_review')) for row in rows),
        }
    response = account['client'].get('/api/knowledge')
    assert response.status_code == 200 and len(response.json()) == len(reviewed)
    assert all(row['source_url'].startswith('https://') for row in response.json())
    Path(__file__).with_name('knowledge-acceptance-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')


def test_active_question_sets_cover_550_unique_questions():
    assert len(SNAPSHOTS) == 10
    assert {s['ability_id'] for s in SNAPSHOTS} == {f'A{i}' for i in range(1,11)}
    assert len(QUESTIONS) == 550 and len({q['id'] for q in QUESTIONS}) == 550
    for snapshot in SNAPSHOTS:
        assert len(snapshot['questions']) == 7
        assert sorted(len(questions) for questions in snapshot['questions'].values()) == [5,5,5,5,5,10,20]
    evidence = {
        'active_set_count':len(SNAPSHOTS),
        'question_count':len(QUESTIONS),
        'unique_question_id_count':len({q['id'] for q in QUESTIONS}),
        'versions':{s['ability_id']:s['version'] for s in SNAPSHOTS},
        'question_type_counts':dict(Counter(q['type'] for q in QUESTIONS)),
        'golden_correct_count':sum(grade(q,correct_answer(q))['correct'] for q in QUESTIONS),
        'golden_full_score_count':sum(grade(q,correct_answer(q))['score']==100 for q in QUESTIONS),
    }
    Path(__file__).with_name('golden-grading-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')


@pytest.mark.parametrize('question', QUESTIONS, ids=[q['id'] for q in QUESTIONS])
def test_each_persisted_question_accepts_golden_answer(question):
    result = grade(question, correct_answer(question))
    assert result['correct'] is True, {'question_id':question['id'],'result':result}
    assert result['score'] == 100
    assert result['missed'] == 0 and result['false_positive'] == 0
