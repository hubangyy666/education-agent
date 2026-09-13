"""Opt-in real-model/SSE checks using a disposable learner (requires live 8000)."""
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session
from backend.catalog import levels
from backend.db import ROOT, User, cache, engine, password_hash


def main():
    username = 'qa_agent_rec_' + uuid.uuid4().hex[:12]
    password = uuid.uuid4().hex
    evidence = []
    with Session(engine) as db:
        db.add(User(username=username, name='推荐验收', password=password_hash(password), onboarding=True))
        db.commit()
    try:
        def ask(case):
            with httpx.Client(base_url='http://127.0.0.1:8000', trust_env=False, timeout=180) as client:
                client.post('/api/auth/login', json={'username': username, 'password': password}).raise_for_status()
                response = client.post('/api/ai/chat', json={
                    'message': case['message'], 'mode': 'GENERAL_TUTOR', 'history': case.get('history', []),
                })
                response.raise_for_status()
                frames = []
                for frame in response.text.split('\n\n'):
                    lines = frame.splitlines()
                    event = next((line[7:] for line in lines if line.startswith('event: ')), '')
                    data = next((line[6:] for line in lines if line.startswith('data: ')), '')
                    if event and data:
                        frames.append((event, json.loads(data)))
                assert frames[-1][0] == 'done', frames
                result = frames[-1][1]
                result['text'] = ''.join(data['text'] for event, data in frames if event == 'token')
                assert result['provider'] == 'deepseek', result
                assert any(event == 'token' for event, _ in frames[:-1]), 'Missing answer before done'
                resources = result.get('resources', [])
                level_ids = [row['level_id'] for row in resources if row.get('resource_type') == 'level']
                if case.get('expected'):
                    assert case['expected'] in level_ids, (case['message'], result)
                if case.get('empty'):
                    assert not resources, (case['message'], result)
                assert 'get_learning_context' not in result.get('tools_used', []), result
                for row in resources:
                    if row.get('resource_type') == 'level':
                        actual = next(level for level in levels(row['ability_id']) if level['id'] == row['level_id'])
                        assert row['title'] == actual['name'] and row['skill_id'] == actual['skill_id']
                return {'message': case['message'], 'history': case.get('history', []), 'result': result,
                        'events': [event for event, _ in frames], 'passed': True}

        cases = [
            {'message': '什么是 IoU？', 'expected': 'A4-L3'},
            {'message': '文本实体的边界应该怎么确定？', 'expected': 'A8-L2'},
            {'message': '明天会下雨吗？', 'empty': True},
            {'message': '什么是 IoU？只解释概念，这次不要推荐练习。', 'empty': True},
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(ask, cases):
                evidence.append(result)
                print('PASS', result['message'], flush=True)
        evidence.append(ask({
            'message': '这个数值越高越好吗？', 'expected': 'A4-L3',
            'history': [{'role': 'user', 'text': cases[0]['message']},
                        {'role': 'assistant', 'text': evidence[0]['result']['text']}],
        }))
        print('PASS context-led short follow-up', flush=True)
    finally:
        for key in cache.scan_iter('session:*'):
            if cache.get(key) == username:
                cache.delete(key)
        for key in cache.scan_iter('login_attempt:*:' + username):
            cache.delete(key)
        with Session(engine) as db:
            db.execute(delete(User).where(User.username == username))
            db.commit()
        destination = ROOT / '.runtime/homepage-recommendations-live.json'
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps({'cases': evidence, 'temporary_account_cleaned': True},
                                          ensure_ascii=False, indent=2), encoding='utf-8')
        print('Evidence:', destination, flush=True)


if __name__ == '__main__':
    main()
