from collections import Counter
import copy
from pathlib import Path

from backend.catalog import ABILITIES,levels
from backend.factory import (is_image_annotation,load_initial_sets,normalize_course_pool,
                             normalize_visual_pool,public_question,required_image_annotations,validate)
from backend.db import ROOT


def test_committed_initial_question_sets_are_complete_and_executable():
    initial=load_initial_sets()
    assert set(initial)=={a['id'] for a in ABILITIES}
    ids=[];types=Counter()
    for ability in ABILITIES:
        aid=ability['id'];item=initial[aid]
        assert item['version']==1
        validate(item['questions'],aid)
        questions=[q for level in item['questions'].values() for q in level]
        assert len(item['questions'])==7
        assert len(questions)==65
        assert Counter(q['skill_id'] for q in questions)=={f'{aid}-S{i}':13 for i in range(1,6)}
        for level in levels(aid):
            level_questions=item['questions'][level['id']]
            flags=[is_image_annotation(question) for question in level_questions]
            required=required_image_annotations(level['mode'])
            assert sum(flags)>=required
            assert flags==sorted(flags,reverse=True)
        for question in questions:
            ids.append(question['id']);types[question['type']]+=1
            assert not {'answer','hint','explanation','threshold'}.intersection(public_question(question))
            if question.get('image'):
                assert (ROOT/'data/samples'/Path(question['image']).name).is_file()
    assert len(ids)==650 and len(set(ids))==650
    assert types=={'choice':205,'box':368,'polygon':51,'entity':26}
    assert sum(bool(q.get('image')) for item in initial.values() for qs in item['questions'].values() for q in qs)==436


def test_five_question_active_courses_upgrade_to_seven_without_changing_job_or_race():
    initial=load_initial_sets()['A4']['questions']
    old=copy.deepcopy(initial)
    for lid in [key for key in old if '-L' in key]: old[lid]=old[lid][:5]
    before=copy.deepcopy(old)
    upgraded=normalize_course_pool(old,initial,'A4',2)
    assert old==before
    assert [len(upgraded[f'A4-L{i}']) for i in range(1,6)]==[7]*5
    assert upgraded['A4-JOB']==before['A4-JOB']
    assert upgraded['A4-RACE']==before['A4-RACE']
    assert all('-V2-' in q['id'] for i in range(1,6) for q in upgraded[f'A4-L{i}'])


def test_existing_active_pool_is_upgraded_to_visual_count_and_order_without_mutation():
    initial=load_initial_sets()['A6']['questions']
    legacy={}
    for level in levels('A6'):
        questions=copy.deepcopy(initial[level['id']])
        annotations=[question for question in questions if is_image_annotation(question)]
        others=[question for question in questions if not is_image_annotation(question)]
        legacy[level['id']]=others+annotations[:1 if level['mode']=='course' else 2]
    before=copy.deepcopy(legacy)
    upgraded=normalize_visual_pool(legacy,initial,'A6',2)
    assert legacy==before
    for level in levels('A6'):
        questions=upgraded[level['id']]
        flags=[is_image_annotation(question) for question in questions]
        assert len(questions)==level['count']
        assert sum(flags)>=required_image_annotations(level['mode'])
        assert flags==sorted(flags,reverse=True)
        assert all('-V2-' in question['id'] for question in questions)
