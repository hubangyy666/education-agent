"""HTTP settings and published-run behavior, isolated from the shared database."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from backend import main
from backend.adaptive import ability_state, recommendation, _next_level
from backend.db import Progress, QuestionSet, Run, User


@pytest.fixture
def isolated_api(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "settings-runs.db"}', connect_args={'check_same_thread': False})
    for table in (User.__table__, Run.__table__, Progress.__table__, QuestionSet.__table__):
        table.create(engine)
    with Session(engine) as db:
        db.add_all([
            User(username='qa_voice_owner', name='本人', password='unused', goal='课程补强', daily_goal=20, voice=True),
            User(username='qa_voice_other', name='他人', password='unused', goal='岗位入门', daily_goal=10, voice=True),
        ])
        db.commit()
    tokens = {'owner-token': 'qa_voice_owner', 'other-token': 'qa_voice_other'}
    monkeypatch.setattr(main, 'cache', SimpleNamespace(
        get=lambda key: tokens.get(key.removeprefix('session:')) if key.startswith('session:') else None,
        exists=lambda key: False,
    ))

    def get_db():
        with Session(engine) as db:
            yield db

    prior_overrides = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[main.get_db] = get_db
    # No context manager: TestClient exercises ASGI routes without starting the
    # production lifespan (which would initialize global databases and workers).
    client = TestClient(main.app)
    try:
        yield client, engine
    finally:
        client.close()
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(prior_overrides)
        engine.dispose()


def test_voice_setting_requires_auth_and_survives_new_http_request(isolated_api):
    client, engine = isolated_api
    assert client.post('/api/profile/voice', json={'voice': False}).status_code == 401
    client.cookies.set('zhiji_session', 'owner-token')
    response = client.post('/api/profile/voice', json={'voice': False})
    assert response.status_code == 200 and response.json()['voice'] is False
    assert client.get('/api/auth/me').json()['voice'] is False
    with Session(engine) as db:
        user = db.get(User, 'qa_voice_owner')
        assert user.voice is False
        assert (user.name, user.goal, user.daily_goal) == ('本人', '课程补强', 20)
    assert client.post('/api/profile/voice', json={'voice': True}).json()['voice'] is True
    with Session(engine) as db:
        assert db.get(User, 'qa_voice_owner').voice is True


def test_voice_setting_isolates_users_and_ignores_spoofed_identity(isolated_api):
    client, engine = isolated_api
    client.cookies.set('zhiji_session', 'owner-token')
    response = client.post('/api/profile/voice', json={'voice': False, 'username': 'qa_voice_other', 'name': '篡改'})
    assert response.status_code == 200 and response.json()['username'] == 'qa_voice_owner'
    client.cookies.set('zhiji_session', 'other-token')
    other = client.get('/api/auth/me').json()
    assert other['username'] == 'qa_voice_other' and other['voice'] is True and other['name'] == '他人'
    with Session(engine) as db:
        assert db.get(User, 'qa_voice_owner').voice is False
        assert db.get(User, 'qa_voice_other').voice is True


@pytest.mark.parametrize('payload', [{}, {'voice': None}, {'voice': '不是布尔值'}])
def test_invalid_voice_payload_never_changes_preference(isolated_api, payload):
    client, engine = isolated_api
    client.cookies.set('zhiji_session', 'owner-token')
    assert client.post('/api/profile/voice', json=payload).status_code == 422
    with Session(engine) as db:
        assert db.get(User, 'qa_voice_owner').voice is True


def test_voice_setting_rejects_untrusted_origin(isolated_api):
    client, engine = isolated_api
    client.cookies.set('zhiji_session', 'owner-token')
    response = client.post('/api/profile/voice', json={'voice': False}, headers={'Origin': 'https://untrusted.example'})
    assert response.status_code == 403
    with Session(engine) as db:
        assert db.get(User, 'qa_voice_owner').voice is True


def question(qid, title):
    return {'id': qid, 'type': 'choice', 'title': title, 'skill_id': 'A1-S1',
            'options': ['标签', '文件名'], 'answer': '标签', 'hint': ['观察类别'], 'explanation': '标签说明类别。'}


@pytest.mark.parametrize('reuse_question_id', [False, True])
def test_newly_published_questions_start_new_run_and_preserve_old_snapshot(isolated_api, reuse_question_id):
    client, engine = isolated_api
    client.cookies.set('zhiji_session', 'owner-token')
    old_questions = [question('v1-q1', '旧版题目')]
    with Session(engine) as db:
        db.add(QuestionSet(id='A1-V1', ability_id='A1', version=1, active=True, questions={'A1-L1': old_questions}))
        db.commit()
    original = client.post('/api/runs/start', json={'level_id': 'A1-L1'}).json()
    rid = original['id']
    assert client.post(f'/api/runs/{rid}/answer', json={'question_id': 'v1-q1', 'answer': {'value': '标签'}}).status_code == 200
    saved_answers = {'v1-q1': {'value': '标签'}}
    new_questions = [question('v1-q1' if reuse_question_id else 'v2-q1', '真实发布的新版题目')]
    with Session(engine) as db:
        db.get(QuestionSet, 'A1-V1').active = False
        db.add(QuestionSet(id='A1-V2', ability_id='A1', version=2, active=True, questions={'A1-L1': new_questions}))
        db.commit()
    response = client.post('/api/runs/start', json={'level_id': 'A1-L1'})
    assert response.status_code == 200
    current = response.json()
    assert current['id'] != rid and current['questions'][0]['title'] == '真实发布的新版题目'
    assert current['answers'] == {}
    assert 'answer' not in current['questions'][0] and 'hint' not in current['questions'][0]
    # Reentering the same published version resumes its own persisted Run.
    assert client.post('/api/runs/start', json={'level_id': 'A1-L1'}).json()['id'] == current['id']
    historical = client.get(f'/api/runs/{rid}').json()
    assert historical['questions'][0]['title'] == '旧版题目'
    assert historical['answers'] == saved_answers and historical['status'] == 'active'
    with Session(engine) as db:
        assert db.get(Run, rid).questions == old_questions
        assert db.get(Run, rid).answers == saved_answers
        assert db.get(Run, current['id']).questions == new_questions
        assert db.get(QuestionSet, 'A1-V1').questions == {'A1-L1': old_questions}
        assert db.scalar(select(func.count()).select_from(Run)) == 2


@pytest.mark.parametrize('goal', ['岗位入门', '竞赛备战', '课程补强'])
def test_open_levels_still_recommend_foundation_course_first(isolated_api, goal):
    _, engine = isolated_api
    with Session(engine) as db:
        user = db.get(User, 'qa_voice_owner')
        states = ability_state(db, user)
        assert all(level['unlocked'] for state in states for level in state['levels'])
        rec = recommendation(states, goal)
        assert rec['ability_id'] == 'A1' and rec['level']['id'] == 'A1-L1'


@pytest.mark.parametrize('goal,mode', [('岗位入门', 'job'), ('竞赛备战', 'competition')])
def test_goal_recommends_package_after_foundation_courses_and_keeps_review_available(isolated_api, goal, mode):
    _, engine = isolated_api
    with Session(engine) as db:
        user = db.get(User, 'qa_voice_owner')
        for i in range(1, 6):
            db.add(Progress(id=f'{user.username}:A1-L{i}', username=user.username,
                            ability_id='A1', level_id=f'A1-L{i}', score=100))
        db.commit()
        state = ability_state(db, user)[0]
        assert _next_level(state, goal)['mode'] == mode
        weak_state = deepcopy(state)
        weak_state['levels'][2]['score'] = 40
        assert _next_level(weak_state, goal)['id'] == 'A1-L3'
