"""External QA: only qa_agent_* users may be mutated; never invokes model APIs."""
import copy
import os
import sys
import uuid
from pathlib import Path
from datetime import timedelta

sys.dont_write_bytecode = True
sys.path.insert(0, os.environ.get('ZHIJI_PROJECT_ROOT', str(Path(__file__).resolve().parents[2])))
# Local API verification must not be routed through a machine-wide HTTP proxy.
os.environ['NO_PROXY'] = ','.join(filter(None, [os.environ.get('NO_PROXY', ''), '127.0.0.1', 'localhost']))
os.environ['no_proxy'] = ','.join(filter(None, [os.environ.get('no_proxy', ''), '127.0.0.1', 'localhost']))
import httpx
import pytest
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session
from backend.db import engine, cache, User, Run, Progress, TaskCard, JobLearning, QuestionSet, password_hash, now

BASE_URL = os.environ.get('ZHIJI_TEST_URL', 'http://127.0.0.1:8000')
SECRET = 'Qa-only-password-9'

def correct_answer(question):
    answer = copy.deepcopy(question['answer'])
    if question['type'] == 'box': return {'boxes': answer}
    if question['type'] == 'polygon': return {'points': answer['polygon'], 'label': answer['label']}
    if question['type'] == 'entity': return answer
    return {'value': answer}

@pytest.fixture
def account_factory():
    accounts = []
    def create():
        username = 'qa_agent_' + uuid.uuid4().hex[:18]
        with Session(engine) as db:
            db.add(User(username=username, name='QA临时', password=password_hash(SECRET)))
            db.commit()
        client = httpx.Client(base_url=BASE_URL, timeout=20)
        account = {'username': username, 'client': client, 'tokens': []}
        accounts.append(account)
        response = client.post('/api/auth/login', json={'username': username, 'password': SECRET})
        assert response.status_code == 200
        account['tokens'].append(client.cookies.get('zhiji_session'))
        return account
    yield create
    for account in accounts:
        username = account['username']
        assert username.startswith('qa_agent_')
        # Track every cookie issued by these test clients; scan values as a final guard.
        token = account['client'].cookies.get('zhiji_session')
        if token: account['tokens'].append(token)
        account['client'].close()
        for token in account['tokens']:
            if token and cache.get('session:' + token) == username: cache.delete('session:' + token)
        for key in cache.scan_iter(match='session:*'):
            if cache.get(key) == username: cache.delete(key)
        for key in cache.scan_iter(match='login_attempt:*:' + username): cache.delete(key)
        with Session(engine) as db:
            for model in (JobLearning, TaskCard, Progress, Run, User):
                db.execute(delete(model).where(model.username == username))
            db.commit()
            assert db.scalar(select(func.count()).select_from(User).where(User.username == username)) == 0

@pytest.fixture
def account(account_factory):
    return account_factory()

@pytest.fixture
def seeded_run():
    def create(account, level='A1-L1', mode='course', deadline=None, answers=None):
        aid = level.split('-')[0]
        with Session(engine) as db:
            pool = db.scalar(select(QuestionSet).where(QuestionSet.ability_id == aid, QuestionSet.active.is_(True)))
            assert pool is not None
            questions = copy.deepcopy(pool.questions[level])
            rid = str(uuid.uuid4())
            db.add(Run(id=rid, username=account['username'], ability_id=aid, level_id=level,
                       mode=mode, questions=questions, answers=answers or {}, deadline=deadline))
            db.commit()
        return rid, questions
    return create
