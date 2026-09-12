"""Skill scores use persisted answers; these tests use an isolated SQLite database."""
from copy import deepcopy

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.adaptive import ability_state, learner_context, recommendation
from backend.db import Progress, Run, User, now
from backend.grading import grade, report


@pytest.fixture
def score_db(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "skill-scores.db"}')
    for table in (User.__table__, Run.__table__, Progress.__table__):
        table.create(engine)
    with Session(engine) as db:
        user = User(username='qa_skill_score', name='QA', password='unused', goal='课程补强')
        db.add(user)
        db.commit()
        yield db, user
    engine.dispose()


def question(qid, skill='A1-S1'):
    return {'id': qid, 'type': 'choice', 'title': '选择标签', 'skill_id': skill,
            'options': ['正确', '错误'], 'answer': '正确'}


def save_run(db, user, rid, questions, answers, *, mode='course', completed=False, revision_of=None):
    run = Run(id=rid, username=user.username, ability_id='A1', level_id='A1-L1', mode=mode,
              questions=deepcopy(questions), answers=deepcopy(answers),
              status='completed' if completed else 'active', revision_of=revision_of,
              report=report(questions, answers) if completed else None,
              finished_at=now() if completed else None)
    db.add(run)
    db.commit()
    return run


def a1(db, user):
    return next(a for a in ability_state(db, user) if a['id'] == 'A1')


def test_all_seventy_levels_open_without_progress_or_diagnostic_inflation(score_db):
    db, user = score_db
    user.diagnostic = {'skills': [{'ability_id': 'A1', 'skill_id': 'A1-S1', 'correct': True}]}
    db.add(Progress(id=f'{user.username}:A1-L1', username=user.username,
                    ability_id='A1', level_id='A1-L1', score=100))
    db.commit()
    states = ability_state(db, user)
    assert len([level for ability in states for level in ability['levels']]) == 70
    assert all(level['unlocked'] for ability in states for level in ability['levels'])
    assert all(a['skill_score'] == 0 and a['answer_count'] == 0 for a in states)
    assert states[0]['completed'] == 1
    assert states[0]['diagnostic_score'] == 100
    assert states[0]['skill_mastery'][0]['assessed'] is False


def test_course_submissions_update_immediately_and_retry_uses_latest_saved_answer(score_db):
    from backend import main
    db, user = score_db
    qs = [question(str(i)) for i in range(4)]
    run = save_run(db, user, 'active-course', qs, {})
    main.submit_answer(run.id, main.AnswerBody(question_id=qs[0]['id'], answer={'value': '正确'}), user, db)
    main.submit_answer(run.id, main.AnswerBody(question_id=qs[1]['id'], answer={'value': '错误'}), user, db)
    with pytest.raises(HTTPException) as blocked:
        main.submit_answer(run.id, main.AnswerBody(question_id=qs[2]['id'], answer={'value': '错误'}), user, db)
    assert blocked.value.status_code == 409
    db.expire_all()
    state = a1(db, user)
    assert (state['correct_count'], state['answer_count'], state['skill_score']) == (1, 2, 5)
    assert state['mastery'] == 50 and state['completed'] == 0
    assert state['skill_mastery'][0]['skill_score'] == 5
    assert state['levels'][0]['skill_score'] == 5
    assert state['levels'][0]['answer_count'] == 2
    main.submit_answer(run.id, main.AnswerBody(question_id=qs[1]['id'], answer={'value': '正确'}), user, db)
    main.submit_answer(run.id, main.AnswerBody(question_id=qs[2]['id'], answer={'value': '错误'}), user, db)
    db.expire_all()
    state = a1(db, user)
    assert (state['correct_count'], state['answer_count'], state['skill_score']) == (2, 3, 6.67)
    assert db.get(Run, run.id).answers[qs[1]['id']] == {'value': '正确'}
    # A later regression is visible; best Progress.score cannot override it.
    main.submit_answer(run.id, main.AnswerBody(question_id=qs[0]['id'], answer={'value': '错误'}), user, db)
    assert a1(db, user)['skill_score'] == 3.33


def test_ability_score_weights_real_answers_instead_of_unassessed_skills_or_runs(score_db):
    db, user = score_db
    qs = [question(str(i)) for i in range(10)] + [question('s2', 'A1-S2')]
    answers = {q['id']: {'value': '正确' if q['id'] in ('0', 's2') else '错误'} for q in qs}
    save_run(db, user, 'weighted', qs, answers, completed=True)
    state = a1(db, user)
    assert (state['correct_count'], state['answer_count'], state['skill_score']) == (2, 11, 1.82)
    assert state['skill_mastery'][0]['skill_score'] == 1
    assert state['skill_mastery'][1]['skill_score'] == 10
    assert state['skill_mastery'][2]['skill_score'] == 0
    assert state['skill_mastery'][2]['assessed'] is False
    rec = recommendation(ability_state(db, user), user.goal)
    assert 'skill_score' in rec and '%' not in rec['reason']
    context = learner_context(user, ability_state(db, user), 'A1', 'A1-S1')
    assert context['skill_score'] == 1 and context['mastery'] == 10


@pytest.mark.parametrize('mode', ['job', 'competition'])
def test_active_packages_do_not_reveal_correctness_through_skill_scores(score_db, mode):
    db, user = score_db
    q = question('package')
    run = save_run(db, user, f'package-{mode}', [q], {q['id']: {'value': '正确'}}, mode=mode)
    assert a1(db, user)['answer_count'] == 0
    run.report = report(run.questions, run.answers)
    run.status = 'completed'
    run.finished_at = now()
    db.commit()
    state = a1(db, user)
    assert (state['answer_count'], state['correct_count'], state['skill_score']) == (1, 1, 10)


def test_unanswered_timeout_questions_and_onboarding_are_not_training_answers(score_db):
    db, user = score_db
    qs = [question(str(i)) for i in range(5)]
    save_run(db, user, 'expired', qs, {'0': {'value': '错误'}}, mode='competition', completed=True)
    save_run(db, user, 'onboarding', qs, {q['id']: {'value': '正确'} for q in qs}, mode='onboarding', completed=True)
    state = a1(db, user)
    assert (state['answer_count'], state['correct_count'], state['skill_score']) == (1, 0, 0)


def test_repair_does_not_count_inherited_correct_answers_twice(score_db):
    db, user = score_db
    qs = [question('correct'), question('repair')]
    parent = save_run(db, user, 'original', qs,
                      {'correct': {'value': '正确'}, 'repair': {'value': '错误'}}, mode='job', completed=True)
    save_run(db, user, 'repaired', qs, {q['id']: {'value': '正确'} for q in qs},
             mode='job', completed=True, revision_of=parent.id)
    state = a1(db, user)
    assert (state['answer_count'], state['correct_count'], state['skill_score']) == (3, 2, 6.67)


def test_score_counts_correct_verdict_not_partial_iou_points(score_db):
    db, user = score_db
    q = {'id': 'bbox', 'type': 'box', 'title': '框选', 'skill_id': 'A1-S1',
         'answer': [{'label': '目标', 'box': [0.1, 0.1, 0.4, 0.4]}]}
    answer = {'boxes': [{'label': '目标', 'box': [0.1, 0.1, 0.45, 0.45]}]}
    result = grade(q, answer)
    assert result['correct'] and 0 < result['score'] < 100
    save_run(db, user, 'geometry', [q], {q['id']: answer}, completed=True)
    assert a1(db, user)['skill_score'] == 10


def test_score_uses_all_saved_runs_and_only_current_user(score_db):
    db, user = score_db
    q = question('historical')
    for i in range(121):
        save_run(db, user, str(i), [q], {q['id']: {'value': '正确' if i == 0 else '错误'}}, completed=True)
    other = User(username='qa_skill_other', name='QA', password='unused')
    db.add(other)
    db.commit()
    save_run(db, other, 'other-user', [q], {q['id']: {'value': '正确'}}, completed=True)
    state = a1(db, user)
    assert (state['answer_count'], state['correct_count'], state['skill_score']) == (121, 1, 0.08)
