import math
import pytest
from backend.grading import grade, iou, valid_box, polygon_metrics, report

BOX = {'id': 'box', 'title': '目标', 'type': 'box', 'answer': [{'label': '猫', 'box': [.1,.1,.3,.3]}]}
POLYGON = {'id': 'poly', 'title': '轮廓', 'type': 'polygon', 'answer': {'label': '猫', 'polygon': [[.1,.1],[.4,.1],[.4,.4],[.1,.4]]}}
ENTITY = {'id': 'entity', 'title': '实体', 'type': 'entity', 'answer': {'start': 3, 'end': 5, 'label': '地点'}}
CHOICE = {'id': 'choice', 'title': '规则', 'type': 'choice', 'answer': '先读规范'}

@pytest.mark.parametrize('box', [None, {}, [], [0,0,0,1], [0,0,-1,1], [-.1,0,.2,.2], [0,0,2,1], [0,0,1], [0,0,math.nan,1], [0,0,math.inf,1], ['0',0,1,1]])
def test_invalid_box_safe(box):
    assert valid_box(box) is False
    assert iou(box, [0,0,1,1]) == 0

def test_iou_geometry():
    assert iou([0,0,1,1], [0,0,1,1]) == 1
    assert iou([0,0,.5,.5], [.5,.5,.5,.5]) == 0
    assert iou([0,0,.5,.5], [.25,0,.5,.5]) == pytest.approx(1/3)

@pytest.mark.parametrize('answer', [None, {}, {'boxes': None}, {'boxes': {}}, {'boxes': []}, {'boxes': [None]}, {'boxes': [{'label':'猫','box':None}]}])
def test_null_missing_box_not_correct(answer):
    result = grade(BOX, answer)
    assert not result['correct'] and result['score'] == 0
    assert result['missed'] == 1

def test_box_exact_duplicate_wrong_label():
    exact = BOX['answer'][0]
    assert grade(BOX, {'boxes': [exact]})['correct']
    duplicate = grade(BOX, {'boxes': [exact, exact]})
    assert not duplicate['correct'] and duplicate['false_positive'] == 1
    assert duplicate['score'] == 50
    wrong = grade(BOX, {'boxes': [dict(exact,label='狗')]})
    assert not wrong['correct'] and wrong['label_correct'] == 0 and wrong['iou'] == pytest.approx(1)

def test_two_boxes_missing_target():
    q = dict(BOX, answer=[BOX['answer'][0], {'label':'狗','box':[.6,.6,.3,.3]}])
    result = grade(q, {'boxes': BOX['answer']})
    assert result['expected_count'] == 2 and result['missed'] == 1
    assert not result['correct']

@pytest.mark.parametrize('points', [None, [], [[.1,.1]], [[0,0],[1,0],[math.nan,.5]], [[0,0],[1,0],[1,2]], [None,None,None]])
def test_polygon_invalid_points(points):
    result = grade(POLYGON, {'points': points, 'label':'猫'})
    assert not result['correct'] and result['iou'] == 0

def test_polygon_exact_reverse_label():
    points = POLYGON['answer']['polygon']
    assert grade(POLYGON, {'points':points,'label':'猫'})['correct']
    assert grade(POLYGON, {'points':list(reversed(points)),'label':'猫'})['iou'] == 1
    assert not grade(POLYGON, {'points':points,'label':'狗'})['correct']
    assert polygon_metrics(points, points) == (1,1,0,0)

@pytest.mark.parametrize('answer', [None, {}, {'start':3,'end':4,'label':'地点'}, {'start':3,'end':5,'label':'人名'}, {'start':'3','end':'5','label':'地点'}])
def test_entity_invalid_span_or_label(answer):
    assert not grade(ENTITY, answer)['correct']

def test_entity_exact_and_summary_metrics():
    assert grade(ENTITY, ENTITY['answer'])['correct']
    output = report([BOX, CHOICE], {'box': {'boxes': BOX['answer']}})
    assert output['count'] == 2 and output['correct_count'] == 1
    assert output['score'] == 50 and output['missed_rate'] == 50
    assert not output['passed']
