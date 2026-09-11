"""Desired-behavior regressions: failures here document defects, not xfails."""
import pytest
from backend.grading import grade, valid_box

def test_multitarget_matching_respects_labels_and_achievable_iou():
    q={'type':'box','answer':[{'label':'cat','box':[0,0,.5,.5]}, {'label':'dog','box':[.1,0,.5,.5]}]}
    answer={'boxes':[{'label':'cat','box':[0,0,.45,.5]}, {'label':'dog','box':[0,0,.5,.5]}]}
    assert grade(q,answer)['correct'] is True
    assert grade(dict(q,answer=list(reversed(q['answer']))),answer)['correct'] is True

def test_bool_is_not_a_box_coordinate():
    assert valid_box([False,False,True,True]) is False

@pytest.mark.parametrize('start,end', [(False,True),(0.0,1.0)])
def test_entity_offsets_must_be_integer_not_bool_or_float(start,end):
    q={'type':'entity','answer':{'start':0,'end':1,'label':'person'}}
    assert grade(q,{'start':start,'end':end,'label':'person'})['correct'] is False

def test_self_intersecting_polygon_is_not_a_valid_annotation():
    q={'type':'polygon','answer':{'label':'cat','polygon':[[.1,.1],[.4,.1],[.4,.4],[.1,.4]]}}
    # Nonadjacent segments cross strictly inside the shape at (.25,.25).
    points=[[.1,.1],[.4,.1],[.4,.4],[.1,.4],[.3,.2],[.2,.2],[.3,.3],[.1,.3]]
    assert grade(q,{'points':points,'label':'cat'})['correct'] is False
