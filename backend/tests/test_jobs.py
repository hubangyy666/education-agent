"""Isolated job API + PostgreSQL evidence checks; no external model requests."""
import copy
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend import jobs, main
from backend.db import JobLearning, Progress, Run, User, cache, engine, now, password_hash
from backend.factory import public_question
from backend.grading import report
from conftest import correct_answer


EVIDENCE = '我已核对本题要求和标注范围，记录不确定项并在提交前逐项复核。'


@pytest.fixture
def job_accounts(monkeypatch):
    # Real scoring and persistence remain active, while QA answers must not enqueue
    # modifications to the shared question-quality factory on another live server.
    def scoped_cache_set(key, *args, **kwargs):
        return True if key.startswith('quality-dirty:') else cache.set(key, *args, **kwargs)
    monkeypatch.setattr(main, 'cache', SimpleNamespace(get=cache.get, set=scoped_cache_set))
    JobLearning.__table__.create(engine, checkfirst=True)
    app = FastAPI()
    jobs.register_jobs(app, main.current_user)
    app.router.routes.extend(route for route in main.app.router.routes
                             if getattr(route, 'path', '').startswith('/api/runs/'))
    accounts = []

    def create():
        username = 'qa_agent_' + uuid.uuid4().hex[:18]
        token = 'job-test-' + uuid.uuid4().hex
        with Session(engine) as db:
            db.add(User(username=username, name='岗位QA', password=password_hash('qa-local-only')))
            db.commit()
        cache.set('session:' + token, username, ex=600)
        client = TestClient(app)
        client.cookies.set('zhiji_session', token)
        account = SimpleNamespace(client=client, username=username, token=token)
        accounts.append(account)
        return account

    yield create
    for account in accounts:
        account.client.close()
        cache.delete('session:' + account.token)
        with Session(engine) as db:
            for model in (JobLearning, Progress, Run, User):
                db.execute(delete(model).where(model.username == account.username))
            db.commit()


def generate(account, role_id=None, task_id=None):
    catalog = jobs.read_catalog()
    role = next((r for r in catalog['roles'] if r['id'] == role_id), catalog['roles'][0])
    task = next((t for t in role['tasks'] if t['id'] == task_id), role['tasks'][0])
    response = account.client.post(f'/api/jobs/{role["id"]}/tasks/{task["id"]}/enroll', json={})
    assert response.status_code == 200, response.text
    return response.json()


def prepare(account, learning):
    for step in learning['card']['steps']:
        if step['kind'] == 'practice':
            return step
        response = account.client.post(f'/api/job-learning/{learning["id"]}/steps/{step["id"]}',
                                       json={'evidence': EVIDENCE})
        assert response.status_code == 200, response.text


def start_practice(account, learning, step):
    response = account.client.post(f'/api/job-learning/{learning["id"]}/steps/{step["id"]}/start')
    assert response.status_code == 200, response.text
    return response.json()['id']


def finish_practice(account, run_id, correct=True):
    with Session(engine) as db:
        questions = copy.deepcopy(db.get(Run, run_id).questions)
    for question in questions:
        response = account.client.post(f'/api/runs/{run_id}/answer',
                                       json={'question_id': question['id'],
                                             'answer': correct_answer(question) if correct else {}})
        assert response.status_code == 200, response.text
    response = account.client.post(f'/api/runs/{run_id}/finish')
    assert response.status_code == 200, response.text
    return response.json()


def test_catalog_sources_and_executable_skill_mappings():
    catalog = jobs.read_catalog()
    ids = {source['id'] for source in catalog['sources']}
    assert len(catalog['roles']) >= 4
    assert all(source['url'].startswith('https://') and source['summary'] for source in catalog['sources'])
    for role in catalog['roles']:
        assert set(role['source_ids']).issubset(ids)
        assert role['scenario'] and role['responsibilities'] and role['majors']
        for task in role['tasks']:
            assert set(task['source_ids']).issubset(ids)
            assert all(set(point['source_ids']).issubset(ids) for point in task['knowledge'])
            card = jobs.template_card(catalog, role, task)
            assert card['skills'] and card['knowledge'] and card['assessment']
            assert [step['kind'] for step in card['steps']] == ['read', 'read', 'practice', 'review']


def test_authentication_and_user_isolation(job_accounts):
    account, other = job_accounts(), job_accounts()
    learning = generate(account)
    assert other.client.get('/api/job-learning/' + learning['id']).status_code == 404
    assert other.client.post('/api/job-learning/' + learning['id'] + '/steps/understand',
                             json={'evidence': EVIDENCE}).status_code == 404
    other_listing = other.client.get('/api/jobs').json()
    assert all(role['progress']['learning_count'] == 0 for role in other_listing['roles'])
    account.client.cookies.clear()
    assert account.client.get('/api/jobs').status_code == 401
    assert account.client.post('/api/jobs/vision/tasks/vision-detection/enroll', json={}).status_code == 401


def test_fixed_enrollment_is_persisted_and_idempotent(job_accounts):
    account = job_accounts()
    learning = generate(account)
    assert learning['card']['provider'] == 'fixed' and learning['card']['ai_generated'] is False
    assert '固定岗位任务讲解' in learning['card']['notice']
    assert learning['percent'] == 0 and learning['status'] == 'active'
    assert 'learner_context' not in learning['card']['analysis']
    assert 'learning_goal' not in learning['card']['analysis']
    first = learning['card']['steps'][0]
    account.client.post(f'/api/job-learning/{learning["id"]}/steps/{first["id"]}', json={'evidence': EVIDENCE})
    again = generate(account)
    assert again['id'] == learning['id'] and again['percent'] == 25
    with Session(engine) as db:
        saved = db.get(JobLearning, learning['id'])
        assert saved.progress[first['id']]['evidence'] == EVIDENCE
        assert saved.card == learning['card'] and saved.sources == learning['sources']
    listing = account.client.get('/api/jobs').json()
    role = next(r for r in listing['roles'] if r['id'] == learning['role_id'])
    assert role['progress']['learning_count'] == 1 and role['progress']['completed_tasks'] == 0


@pytest.mark.parametrize('bad', ['已完成', '啊' * 100, '            ', 'abcdefghijklmn', '。' * 30])
def test_read_evidence_requires_substantive_text(job_accounts, bad):
    account = job_accounts()
    learning = generate(account)
    response = account.client.post(f'/api/job-learning/{learning["id"]}/steps/understand', json={'evidence': bad})
    assert response.status_code == 422
    assert account.client.get('/api/job-learning/' + learning['id']).json()['percent'] == 0


def test_steps_cannot_be_skipped_and_clicking_does_not_complete(job_accounts):
    account = job_accounts()
    learning = generate(account)
    base = f'/api/job-learning/{learning["id"]}/steps'
    assert account.client.post(base + '/review', json={'evidence': EVIDENCE}).status_code == 409
    assert account.client.post(base + '/practice/start').status_code == 409
    step = prepare(account, learning)
    run_id = start_practice(account, learning, step)
    saved = account.client.get('/api/job-learning/' + learning['id']).json()
    assert saved['percent'] == 50 and saved['progress'][step['id']]['completed'] is False
    assert saved['progress'][step['id']]['run_id'] == run_id
    assert start_practice(account, learning, step) == run_id
    assert account.client.post(base + '/practice', json={'evidence': EVIDENCE, 'run_id': run_id}).status_code == 409


def test_unavailable_material_preserves_preparation_and_creates_no_run(job_accounts, monkeypatch):
    account = job_accounts()
    learning = generate(account)
    step = prepare(account, learning)
    def unavailable(step, db):
        raise OSError('test-only missing media')
    monkeypatch.setattr(jobs, 'training_questions', unavailable)
    response = account.client.post(f'/api/job-learning/{learning["id"]}/steps/{step["id"]}/start')
    assert response.status_code == 503 and '进度已保留' in response.json()['detail']
    saved = account.client.get('/api/job-learning/' + learning['id']).json()
    assert saved['percent'] == 50 and not saved['progress'].get(step['id'], {}).get('run_id')
    with Session(engine) as db:
        assert not list(db.scalars(select(Run).where(Run.username == account.username)))


def test_fake_foreign_and_cross_card_runs_cannot_be_used(job_accounts):
    account, other = job_accounts(), job_accounts()
    first = generate(account)
    step = prepare(account, first)
    own_run = start_practice(account, first, step)
    foreign = generate(other)
    foreign_step = prepare(other, foreign)
    foreign_run = start_practice(other, foreign, foreign_step)
    role = next(r for r in jobs.read_catalog()['roles'] if r['id'] == first['role_id'])
    second = generate(account, role['id'], role['tasks'][1]['id'])
    second_step = prepare(account, second)
    second_run = start_practice(account, second, second_step)
    url = f'/api/job-learning/{first["id"]}/steps/{step["id"]}'
    for invalid in ('no-such-run', foreign_run, second_run):
        assert account.client.post(url, json={'evidence': EVIDENCE, 'run_id': invalid}).status_code == 422
    assert own_run not in (foreign_run, second_run)


def test_failed_training_must_retry_and_forged_report_is_recomputed(job_accounts):
    account = job_accounts()
    learning = generate(account)
    step = prepare(account, learning)
    run_id = start_practice(account, learning, step)
    finished = finish_practice(account, run_id, correct=False)
    assert finished['report']['passed'] is False
    url = f'/api/job-learning/{learning["id"]}/steps/{step["id"]}'
    assert account.client.post(url, json={'evidence': EVIDENCE, 'run_id': run_id}).status_code == 409
    with Session(engine) as db:
        run = db.get(Run, run_id)
        run.report = {**run.report, 'passed': True, 'score': 100}
        db.commit()
    assert account.client.post(url, json={'evidence': EVIDENCE, 'run_id': run_id}).status_code == 409
    retry_id = start_practice(account, learning, step)
    assert retry_id != run_id
    with Session(engine) as db:
        run = db.get(Run, run_id)
        assert jobs.training_context(run)['learning_id'] == learning['id']
    assert start_practice(account, learning, step) == retry_id


def test_complete_real_training_and_review_persists_without_unlocking_map(job_accounts):
    account = job_accounts()
    learning = generate(account)
    step = prepare(account, learning)
    run_id = start_practice(account, learning, step)
    public = account.client.get('/api/runs/' + run_id).json()
    assert public['mode'] == 'course' and public['level_id'].startswith('JT-')
    for question in public['questions']:
        assert not {'answer', 'standard_answer', 'hint', 'threshold', 'ai_review', 'evidence', 'grader_validation'}.intersection(question)
    finished = finish_practice(account, run_id)
    assert finished['report']['passed'] is True and finished['report']['score'] == 100
    url = f'/api/job-learning/{learning["id"]}/steps/{step["id"]}'
    response = account.client.post(url, json={'evidence': EVIDENCE, 'run_id': run_id})
    assert response.status_code == 200 and response.json()['percent'] == 75
    assert response.json()['progress'][step['id']]['score'] == 100
    response = account.client.post(f'/api/job-learning/{learning["id"]}/steps/review', json={'evidence': EVIDENCE})
    final = response.json()
    assert final['percent'] == 100 and final['status'] == 'completed' and final['completed_at']
    assert generate(account)['id'] == final['id'] and generate(account)['status'] == 'completed'
    duplicate = account.client.post(url, json={'evidence': '重复', 'run_id': 'changed'})
    assert duplicate.json()['progress'][step['id']]['run_id'] == run_id
    with Session(engine) as db:
        assert db.get(Progress, f'{account.username}:{step["level_id"]}') is None
        assert db.get(Progress, f'{account.username}:{public["level_id"]}').score == 100
        assert db.get(JobLearning, learning['id']).status == 'completed'


def test_every_task_has_five_valid_exercises_with_correct_provenance():
    observed = {}
    with Session(engine) as db:
        for role in jobs.read_catalog()['roles']:
            for task in role['tasks']:
                step = next(step for step in task['steps'] if step['kind'] == 'practice')
                questions = jobs.training_questions(step, db)
                assert len(questions) == 5
                assert all(q['skill_id'] == step['skill_id'] for q in questions)
                actual = report(questions, {q['id']: correct_answer(q) for q in questions})
                assert actual['passed'] and actual['score'] == 100
                for q in questions:
                    assert q.get('source_url')
                    assert 'answer' not in public_question(q)
                observed[task['id']] = questions
    assert all(q['type'] == 'box' and 'KolektorSDD' in q['source'] for q in observed['industrial-localization'])
    assert {q['answer'] for q in observed['industrial-screening']} == {'存在表面缺陷', '无可见缺陷'}
    assert all('不要求画框' in q['explanation'] and '像素掩码的外轮廓与包围框' not in q['explanation']
               and '本题只需判断异常是否存在' in q['hint'][1] for q in observed['industrial-screening'])
    assert all(q['type'] == 'polygon' for q in observed['vision-segmentation'])
    assert all(q['type'] == 'entity' for q in observed['text-entities'])
    assert all(q['type'] == 'choice' and q['ai_review']['decision'] == 'approved'
               for name in ('text-intent', 'quality-delivery') for q in observed[name])
    assert tuple(q['id'] for q in observed['quality-delivery']) == jobs.QUALITY_REPORT_QUESTIONS
    assert not {'QF-57aff98c3b5c5b8066136e9e', 'QF-6a6fdc010178f32e9b184aa4'}.intersection(
        q['id'] for q in observed['quality-delivery'])
    # Snapshot pedagogy fixes must leave the shared reserve and its original
    # deterministic answers unchanged.
    from backend.visual_reserve import visual_questions
    originals = {q['id']: q for q in visual_questions('A6') if q['skill_id'] == 'A6-S4'}
    assert all(q['answer'] == originals[q['id']]['answer'] and q['threshold'] == originals[q['id']]['threshold']
               and '外轮廓与包围框' in originals[q['id']]['explanation'] for q in observed['industrial-screening'])



def test_task_details_are_fixed_for_all_students_and_reading_creates_no_progress(job_accounts):
    first, other = job_accounts(), job_accounts()
    with Session(engine) as db:
        db.get(User, other.username).goal = '竞赛备战'
        db.commit()
    for role in jobs.read_catalog()['roles']:
        for task in role['tasks']:
            url = f'/api/jobs/{role["id"]}/tasks/{task["id"]}'
            one, two = first.client.get(url), other.client.get(url)
            assert one.status_code == two.status_code == 200
            a, b = one.json(), two.json()
            assert a['task'] == b['task']
            assert a['task']['name'] == task['title']
            assert a['task']['provider'] == 'fixed' and a['learning'] is None
            assert a['task']['image']['url'] and a['task']['image']['source_url']
            assert all(len(step['explanation']) >= 2 for step in a['task']['steps'])
    with Session(engine) as db:
        assert not list(db.scalars(select(JobLearning).where(JobLearning.username.in_([first.username, other.username]))))


def test_fixed_task_has_no_generator_or_converter_dependency(job_accounts):
    account = job_accounts()
    assert not hasattr(jobs, 'request_enrichment')
    assert account.client.post('/api/jobs/vision/tasks/vision-detection/generate', json={}).status_code == 404
    assert account.client.get('/api/jobs/vision/tasks/text-intent').status_code == 404
    assert account.client.get('/api/jobs/unknown/tasks/vision-detection').status_code == 404
    assert account.client.post('/api/jobs/text/tasks/vision-detection/enroll', json={}).status_code == 404
    account.client.cookies.clear()
    assert account.client.get('/api/jobs/vision/tasks/vision-detection').status_code == 401


def test_saved_progress_does_not_replace_fixed_lesson_with_old_generated_prose(job_accounts):
    account = job_accounts()
    learning = generate(account)
    with Session(engine) as db:
        row = db.get(JobLearning, learning['id'])
        row.card = {**row.card, 'description': '旧版本生成内容', 'ai_generated': True}
        db.commit()
    response = account.client.get(f'/api/jobs/{learning["role_id"]}/tasks/{learning["task_id"]}').json()
    assert response['learning']['id'] == learning['id']
    assert response['task']['description'] != '旧版本生成内容'
    assert response['task']['ai_generated'] is False
