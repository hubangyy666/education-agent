"""Persisted mistake notebook records, kept separate from scored training runs."""
import copy
import uuid

from sqlalchemy import select

from .db import Mistake, Run, now
from .grading import grade


def record_wrong(db, run, question, answer):
    item = db.scalar(select(Mistake).where(
        Mistake.username == run.username,
        Mistake.question_id == question['id'],
    ).with_for_update())
    if item is None:
        item = Mistake(
            id=str(uuid.uuid4()),
            username=run.username,
            question_id=question['id'],
            ability_id=run.ability_id,
            skill_id=question.get('skill_id'),
            level_id=run.level_id,
            mode=run.mode,
            question=copy.deepcopy(question),
            latest_wrong_answer=copy.deepcopy(answer),
        )
        db.add(item)
        return item
    item.ability_id = run.ability_id
    item.skill_id = question.get('skill_id')
    item.level_id = run.level_id
    item.mode = run.mode
    # A replacement snapshot must not inherit answer access from an older task.
    if item.question != question:
        item.latest_review_answer = None
        item.review_correct = None
        item.review_wrong_attempts = 0
        item.last_reviewed_at = None
    item.question = copy.deepcopy(question)
    item.latest_wrong_answer = copy.deepcopy(answer)
    item.wrong_count += 1
    item.last_wrong_at = now()
    item.removed_at = None
    return item


def record_report_mistakes(db, run):
    results = {result['question_id']: result for result in (run.report or {}).get('results', [])}
    for question in run.questions or []:
        result = results.get(question['id'])
        if result and question['id'] in (run.answers or {}) and not result.get('correct'):
            record_wrong(db, run, question, (run.answers or {}).get(question['id'], {}))


def backfill_mistakes(db):
    """Import reconstructable historical misses once without reviving removals."""
    existing = {(item.username, item.question_id) for item in db.scalars(select(Mistake))}
    pending = {}
    runs = db.scalars(select(Run).where(Run.mode != 'onboarding').order_by(Run.started_at)).all()
    for run in runs:
        if run.mode in ('job', 'competition') and run.status != 'completed':
            continue
        results = {result['question_id']: result for result in (run.report or {}).get('results', [])}
        for question in run.questions or []:
            qid = question['id']
            if qid not in (run.answers or {}) or (run.username, qid) in existing:
                continue
            result = results.get(qid) or grade(question, run.answers[qid])
            if result.get('correct'):
                continue
            key = (run.username, qid)
            count = 1
            if run.mode == 'course' and not run.level_id.startswith('JT-'):
                count = max(1, int((run.hints or {}).get(f'course-wrong-attempts:{qid}', 0)))
            if key not in pending:
                item = Mistake(id=str(uuid.uuid4()), username=run.username,
                               question_id=qid, ability_id=run.ability_id,
                               skill_id=question.get('skill_id'), level_id=run.level_id,
                               mode=run.mode, question=copy.deepcopy(question),
                               latest_wrong_answer=copy.deepcopy(run.answers[qid]),
                               wrong_count=count, last_wrong_at=run.finished_at or run.started_at)
                pending[key] = item
                db.add(item)
            else:
                item = pending[key]
                item.wrong_count += count
                item.ability_id=run.ability_id;item.skill_id=question.get('skill_id')
                item.level_id=run.level_id;item.mode=run.mode
                item.question=copy.deepcopy(question)
                item.latest_wrong_answer=copy.deepcopy(run.answers[qid])
                item.last_wrong_at=run.finished_at or run.started_at
    return len(pending)
