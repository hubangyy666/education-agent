"""A1 content, refresh and one-time publication regression checks."""
import copy
import json
from collections import Counter

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend import factory, visual_reserve
from backend.a1_quality import duplicates_candidate, needs_repair, rejected_hashes
from backend.catalog import levels
from backend.db import ROOT, QuestionSet, Run, User
from backend.factory_agent import Store, content_hash, golden_answer
from backend.grading import grade


def test_a1_seed_uses_distinct_images_and_skill_specific_choices():
    from backend.a1_curriculum import generate_pool
    pool = factory.load_initial_sets()['A1']['questions']
    assert pool == generate_pool(1)
    selected = []
    for level in levels('A1'):
        questions = pool[level['id']]
        assert len(questions) == level['count']
        if level['mode'] == 'course':
            assert {q['skill_id'] for q in questions} == {level['skill_id']}
            assert Counter(q['type'] for q in questions) == {'box': 2, 'choice': 5}
        for question in questions:
            assert not duplicates_candidate(question, selected)
            assert content_hash(question) not in rejected_hashes()
            assert grade(question, golden_answer(question))['correct']
            if question['type'] == 'choice':
                for option in question['options']:
                    assert grade(question, {'value': option})['correct'] == (option == question['answer'])
            selected.append(question)
    assert len({q['image'] for q in selected if q.get('image')}) == 30
    assert Counter(q['skill_id'] for q in selected) == {f'A1-S{i}': 13 for i in range(1, 6)}


def test_a1_boxes_are_real_source_targets_and_reserve_images_have_one_skill():
    from backend.a1_curriculum import authored_visuals
    sources = {s['id']: s for s in factory.samples()}
    questions = authored_visuals()
    assert len({q['image'] for q in questions}) == len(questions)
    assert min(Counter(q['skill_id'] for q in questions).values()) >= 6
    for question in questions:
        sample = sources[question['sample_id']]
        for target in question['answer']:
            assert any(target['box'] == source['box'] and target['label'] == source['label']
                       for source in sample['targets'])
        assert grade(question, {'boxes': []})['correct'] is False


def test_a1_review_exclusions_match_actual_stored_content():
    review = json.loads((ROOT / 'data/a1-question-review.json').read_text(encoding='utf-8'))
    reserve = {content_hash(q): q for q in Store(ROOT / 'data/factory').questions('A1')}
    assert review['rejected']
    for row in review['rejected']:
        assert row['content_hash'] in reserve
        assert row['reason']
        assert row['skill_id'] == reserve[row['content_hash']]['skill_id']


def test_a1_refresh_keeps_unique_images_and_excludes_reviewed_bad_questions():
    initial = factory.load_initial_sets()['A1']['questions']
    previous = {content_hash(q) for qs in initial.values() for q in qs}
    pool = visual_reserve.combined_pool('A1', 7, Store(ROOT / 'data/factory'),
                                       previous=previous, published=initial)
    factory.validate(pool, 'A1')
    assert not needs_repair(pool)
    current = {content_hash(q) for qs in pool.values() for q in qs}
    assert len(current) == 65
    assert current - previous
    assert not current.intersection(rejected_hashes())


def test_a1_startup_repairs_only_bad_pool_once_and_preserves_old_runs(monkeypatch):
    initial = factory.load_initial_sets()
    local_engine = create_engine('sqlite://')
    for model in (QuestionSet, User, Run):
        model.__table__.create(local_engine)
    legacy = copy.deepcopy(initial['A1']['questions'])
    legacy['A1-L2'][0] = copy.deepcopy(legacy['A1-L1'][0])
    legacy['A1-L2'][0].update(id='legacy-l2-q1', skill_id='A1-S2')
    assert needs_repair(legacy)
    with Session(local_engine) as db:
        db.add(User(username='qa_agent_a1_isolated', password='not-a-login'))
        for aid, item in initial.items():
            db.add(QuestionSet(id=aid, ability_id=aid, version=4,
                               questions=legacy if aid == 'A1' else copy.deepcopy(item['questions'])))
        db.add(Run(id='old-run', username='qa_agent_a1_isolated', ability_id='A1',
                   level_id='A1-L2', mode='course', questions=copy.deepcopy(legacy['A1-L2']),
                   answers={'legacy-l2-q1': {'boxes': []}}))
        db.commit()
    monkeypatch.setattr(factory, 'engine', local_engine)
    monkeypatch.setattr(factory, 'upload_media', lambda: None)
    factory.initialize_sets()
    factory.initialize_sets()
    with Session(local_engine) as db:
        items = list(db.scalars(select(QuestionSet)))
        assert len(items) == 11
        active = {item.ability_id: item for item in items if item.active}
        assert active['A1'].version == 5
        assert not needs_repair(active['A1'].questions)
        assert db.get(QuestionSet, 'A1').questions == legacy
        assert db.get(QuestionSet, 'A1').active is False
        for aid in initial.keys() - {'A1'}:
            assert active[aid].id == aid and active[aid].version == 4
            assert active[aid].questions == initial[aid]['questions']
        run = db.get(Run, 'old-run')
        assert run.questions == legacy['A1-L2']
        assert run.answers == {'legacy-l2-q1': {'boxes': []}}
    local_engine.dispose()
