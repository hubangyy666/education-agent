"""Verify fixed job lessons against the running server; never invokes a model."""
import json
import sys
import uuid
from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from backend.db import ROOT, JobLearning, Progress, Run, User, cache, engine, password_hash


def main():
    username, password = 'qa_jobs_fixed_' + uuid.uuid4().hex[:12], uuid.uuid4().hex
    evidence = {'task': 'fixed-job-lessons-v2', 'lessons': [], 'passed': False}
    client = httpx.Client(base_url='http://127.0.0.1:8000', timeout=20, trust_env=False)
    try:
        with Session(engine) as db:
            db.add(User(username=username, name='固定岗位验收', password=password_hash(password), onboarding=True, voice=False))
            db.commit()
        client.post('/api/auth/login', json={'username': username, 'password': password}).raise_for_status()
        listing = client.get('/api/jobs'); listing.raise_for_status()
        for role in listing.json()['roles']:
            for task in role['tasks']:
                url = f'/api/jobs/{role["id"]}/tasks/{task["id"]}'
                started = monotonic()
                response = client.get(url); response.raise_for_status()
                lesson = response.json()
                assert lesson['learning'] is None
                assert lesson['task']['provider'] == 'fixed' and not lesson['task']['ai_generated']
                assert lesson['task']['name'] == task['title']
                assert all(len(step['explanation']) >= 2 for step in lesson['task']['steps'])
                picture = client.get(lesson['task']['image']['url']); picture.raise_for_status()
                assert picture.headers['content-type'].startswith('image/')
                evidence['lessons'].append({'id': task['id'], 'seconds': round(monotonic()-started, 3),
                                           'image_loaded': True, 'fixed_steps': len(lesson['task']['steps'])})
        with Session(engine) as db:
            assert not list(db.scalars(select(JobLearning).where(JobLearning.username == username)))
        evidence['reading_creates_no_progress'] = True
        response = client.post('/api/jobs/text/tasks/text-entities/enroll', json={}); response.raise_for_status()
        learning = response.json()
        again = client.post('/api/jobs/text/tasks/text-entities/enroll', json={}); again.raise_for_status()
        assert again.json()['id'] == learning['id']
        with Session(engine) as db:
            assert db.get(JobLearning, learning['id']).card == learning['card']
        evidence.update(database_roundtrip=True, enrollment_idempotent=True, passed=True)
    finally:
        for key in cache.scan_iter('session:*'):
            if cache.get(key) == username: cache.delete(key)
        for key in cache.scan_iter('login_attempt:*:' + username): cache.delete(key)
        with Session(engine) as db:
            for model in (JobLearning, Progress, Run, User):
                db.execute(delete(model).where(model.username == username))
            db.commit()
            evidence['temporary_account_removed'] = db.get(User, username) is None
        client.close()
        (ROOT/'docs/jobs-fixed-live-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    if not evidence['passed']: raise SystemExit('Fixed job lesson verification failed.')


if __name__ == '__main__': main()
