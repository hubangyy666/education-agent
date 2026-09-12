import uuid
from pathlib import Path

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.db import Knowledge, KnowledgeBase, User, cache, engine
from backend import tutor

from conftest import BASE_URL


def test_admin_account_and_knowledge_management(account):
    suffix = uuid.uuid4().hex[:10]
    username = f'qa_agent_managed_{suffix}'
    manager_username = f'qa_agent_manager_{suffix}'
    base_name = f'QA知识库-{suffix}'
    client = httpx.Client(base_url=BASE_URL, timeout=20)
    knowledge_ids = []
    base_id = None
    try:
        login = client.post('/api/auth/login', json={'username': 'user1', 'password': '123456'})
        assert login.status_code == 200
        assert login.json()['role'] == 'admin'

        users = client.get('/api/admin/users')
        assert users.status_code == 200
        assert any(item['username'] == 'user1' and item['role'] == 'admin' for item in users.json())
        assert client.delete('/api/admin/users/user1').status_code == 409

        created = client.post('/api/admin/users', json={
            'username': username,
            'name': '后台验收用户',
            'password': 'qa-password-123',
            'role': 'student',
        })
        assert created.status_code == 200
        assert created.json()['role'] == 'student'
        manager = client.post('/api/admin/users', json={
            'username': manager_username,
            'name': '后台验收管理者',
            'password': 'qa-password-456',
            'role': 'admin',
        })
        assert manager.status_code == 200 and manager.json()['role'] == 'admin'
        manager_client = httpx.Client(base_url=BASE_URL, timeout=20)
        try:
            assert manager_client.post('/api/auth/login', json={'username': manager_username, 'password': 'qa-password-456'}).status_code == 200
            assert manager_client.get('/api/admin/users').status_code == 200
        finally:
            manager_client.close()
        learner = httpx.Client(base_url=BASE_URL, timeout=20)
        try:
            assert learner.post('/api/auth/login', json={'username': username, 'password': 'qa-password-123'}).status_code == 200
            assert learner.get('/api/admin/users').status_code == 403
        finally:
            learner.close()

        bases = client.get('/api/admin/knowledge-bases')
        assert bases.status_code == 200
        body = bases.json()
        assert len(body['built_in']) == 11
        assert all(item['purpose'] and item['source'] == '原知识库拆分' for item in body['built_in'])
        assert {item['value'] for item in body['scope_options']} == {'GENERAL', *(f'A{i}' for i in range(1, 11))}

        added = client.post('/api/admin/knowledge-bases', json={
            'name': base_name,
            'purpose': '补充 A4 目标检测课程中的校内项目边界说明。',
            'scope': 'A4',
            'content': '验收专用知识：标注前先核对项目定义和目标范围，不根据个人经验猜测边界。\n\n提交前复核标签、边界和遗漏情况。',
        })
        assert added.status_code == 200
        base_id = added.json()['id']
        assert added.json()['active'] is True
        with Session(engine) as db:
            base = db.get(KnowledgeBase, base_id)
            assert base is not None and base.scope == 'A4'
            knowledge_ids = list(base.knowledge_ids)
            rows = list(db.scalars(select(Knowledge).where(Knowledge.id.in_(knowledge_ids))))
            assert len(rows) == added.json()['knowledge_count']
            assert all(len(row.embedding) == 1024 for row in rows)
            assert all(row.ability_id == 'A4' and row.meta['knowledge_base_id'] == base_id and row.meta['managed_by_admin'] is True for row in rows)
            retrieved = tutor.retrieve(db, '验收专用知识中的项目边界说明', 'A4')
            assert any(item['id'] in knowledge_ids for item in retrieved)

        assert client.delete(f'/api/admin/users/{username}').status_code == 200
        assert client.delete(f'/api/admin/users/{manager_username}').status_code == 200
        with Session(engine) as db:
            assert db.get(User, username) is None
            assert db.get(User, manager_username) is None
    finally:
        try:
            client.post('/api/auth/logout')
        except httpx.HTTPError:
            pass
        client.close()
        for key in cache.scan_iter(match='session:*'):
            if cache.get(key) in (username, manager_username):
                cache.delete(key)
        with Session(engine) as db:
            if knowledge_ids:
                db.execute(delete(Knowledge).where(Knowledge.id.in_(knowledge_ids)))
            if base_id:
                db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == base_id))
            db.execute(delete(User).where(User.username == username))
            db.execute(delete(User).where(User.username == manager_username))
            db.commit()


def test_goal_and_duration_selectors_removed_from_user_pages():
    root = Path(__file__).resolve().parents[2]
    onboarding = (root / 'src/views/Onboarding.vue').read_text(encoding='utf-8')
    profile = (root / 'src/views/Profile.vue').read_text(encoding='utf-8')
    assert 'goal-options' not in onboarding
    assert 'time-options' not in onboarding
    assert 'learning-goal' not in profile
    assert 'daily-minutes' not in profile
