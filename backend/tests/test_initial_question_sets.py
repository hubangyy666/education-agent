from collections import Counter
from pathlib import Path

from backend.catalog import ABILITIES
from backend.factory import load_initial_sets,public_question,validate
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
        assert len(questions)==55
        assert Counter(q['skill_id'] for q in questions)=={f'{aid}-S{i}':11 for i in range(1,6)}
        for question in questions:
            ids.append(question['id']);types[question['type']]+=1
            assert not {'answer','hint','explanation','threshold'}.intersection(public_question(question))
            if question.get('image'):
                assert (ROOT/'data/samples'/Path(question['image']).name).is_file()
    assert len(ids)==550 and len(set(ids))==550
    assert types=={'choice':305,'box':170,'polygon':45,'entity':30}
