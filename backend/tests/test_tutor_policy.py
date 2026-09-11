import asyncio
import json
from types import SimpleNamespace

from backend.grading import grade
from backend import tutor
from backend.tutor_policy import (additional_question_context, build_facts,
                                  build_homepage_facts, source_applies,
                                  validate_homepage_payload,
                                  validate_model_payload)


RIGHT = {'label': '行人', 'box': [.515, .205, .485, .793]}
LEFT = {'label': '行人', 'box': [.085, .220, .388, .585]}
LOWER = {'label': '行人', 'box': [.446, .508, .387, .479]}
QUESTION = {
    'id': 'A4-L1-V1-Q3',
    'type': 'box',
    'title': '请找到画面中最大的行人，框出目标并选择标签。',
    'instruction': '框出题目要求的一个目标。',
    'answer': [RIGHT],
    'threshold': .65,
    'hint': ['观察', '比较', '检查'],
}


def wrong_instance_facts(candidates=None):
    answer = {'boxes': [LEFT]}
    result = grade(QUESTION, answer)
    facts = build_facts(QUESTION, True, result, answer,
                        [LEFT, RIGHT, LOWER] if candidates is None else candidates)
    return answer, result, facts


def model_message(payload=None, tool_calls=None):
    content = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name,
                                 arguments=json.dumps(arguments, ensure_ascii=False)))


class FakeCompletions:
    def __init__(self, messages):
        self.messages = list(messages)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=self.messages.pop(0))])


def install_model(monkeypatch, messages):
    completions = FakeCompletions(messages)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-only')
    monkeypatch.setenv('QUESTION_MODEL', 'question-test-model')
    monkeypatch.setenv('GENERAL_MODEL', 'homepage-test-model')
    monkeypatch.setattr(tutor, 'AsyncOpenAI', lambda **kwargs: client)
    monkeypatch.setattr(tutor, 'candidate_targets', lambda question: [LEFT, RIGHT, LOWER])
    return completions


def test_dialogue_reinterprets_single_selection_without_mutating_grade():
    _, result, facts = wrong_instance_facts()
    assert result['error_type'] == 'MISSED_TARGET'  # scoring remains untouched
    assert facts['assessment']['diagnosis'] == 'WRONG_TARGET_INSTANCE'
    assert facts['assessment']['label_correct'] is True
    assert facts['assessment']['geometry_diagnosable'] is False
    assert facts['task_policy']['target_scope'] == 'single_selected'


def test_candidate_comparison_is_deterministic_and_post_submit_only():
    answer, result, facts = wrong_instance_facts()
    comparison = additional_question_context(
        'candidate_comparison', QUESTION, facts, [LEFT, RIGHT, LOWER], answer, result)
    assert comparison['comparison_basis'] == 'largest_bbox_area'
    assert comparison['candidates'][0]['area_rank'] == 1
    assert comparison['candidates'][0]['is_reference_target'] is True
    assert comparison['candidates'][1]['matches_user_submission'] is True
    before = build_facts(QUESTION, False)
    assert additional_question_context(
        'candidate_comparison', QUESTION, before, [LEFT, RIGHT], None, None
    )['available'] is False


def test_validator_understands_negation_and_rejects_real_contradictions():
    _, _, facts = wrong_instance_facts()
    valid = {'reply': '这次不是漏标所有行人，也不能用零交并比判断所选框的边界。',
             'claims': [{'fact': 'diagnosis', 'value': 'WRONG_TARGET_INSTANCE'}],
             'used_source_ids': [], 'followups': []}
    assert validate_model_payload(valid, QUESTION, facts) == []
    invalid = {'reply': '你漏选了其他行人，而且边界没有贴合。',
               'claims': [{'fact': 'diagnosis', 'value': 'MISSED_TARGET'}],
               'used_source_ids': [], 'followups': []}
    codes = {item['code'] for item in validate_model_payload(invalid, QUESTION, facts)}
    assert {'FACT_CONTRADICTION', 'UNSUPPORTED_MISSED_TARGET_CLAIM',
            'UNSUPPORTED_BOUNDARY_CLAIM'} <= codes


def test_validator_rejects_camera_distance_as_size_rule():
    _, _, facts = wrong_instance_facts()
    payload = {'reply': '面积最大的通常就是离镜头最近、看起来最高大的那个。',
               'claims': [], 'used_source_ids': [], 'followups': []}
    codes = {item['code'] for item in validate_model_payload(
        payload, QUESTION, facts)}
    assert 'UNSUPPORTED_SIZE_PROXY' in codes


def test_validator_keeps_internal_diagnosis_code_out_of_student_reply():
    _, _, facts = wrong_instance_facts()
    payload = {'reply': '系统诊断是 WRONG_TARGET_INSTANCE。',
               'claims': [{'fact': 'diagnosis', 'value': 'WRONG_TARGET_INSTANCE'}],
               'used_source_ids': [], 'followups': []}
    codes = {item['code'] for item in validate_model_payload(
        payload, QUESTION, facts)}
    assert 'INTERNAL_DIAGNOSIS_EXPOSED' in codes


def test_single_selection_filters_conflicting_retrieved_guidance():
    _, _, facts = wrong_instance_facts()
    source = {'title': '目标发现要覆盖任务要求的所有实例',
              'content': '所有实例都应该标注'}
    assert source_applies(source, facts['task_policy']) is False


def test_question_followup_is_not_rejected_or_forced_to_use_rag(monkeypatch):
    completions = install_model(monkeypatch, [model_message({
        'reply': '这里按每个候选外接框的宽乘高比较，面积更大的排在前面。',
        'claims': [{'fact': 'selection_rule', 'value': 'largest_bbox_area'}],
        'used_source_ids': [],
        'followups': ['需要我再解释宽和高怎么取吗？'],
    })])
    loads = []
    output = asyncio.run(tutor.answer(
        '怎样比较目标大小？', 'QUESTION_TUTOR', {}, [], QUESTION, 0, False,
        None, [], None, knowledge_loader=lambda query: loads.append(query) or []))
    assert output['provider'] == 'deepseek'
    assert '宽乘高' in output['text']
    assert output['tools_used'] == [] and loads == []
    assert completions.calls[0]['tool_choice'] == 'auto'


def test_rag_is_called_only_after_model_requests_it(monkeypatch):
    completions = install_model(monkeypatch, [
        model_message(tool_calls=[tool_call('rag-1', 'search_knowledge',
                                             {'query': '目标框外接面积定义'})]),
        model_message({'reply': '外接框面积等于宽乘高。',
                       'claims': [], 'used_source_ids': ['KB-AREA'],
                       'followups': []}),
    ])
    loads = []
    source = {'id': 'KB-AREA', 'title': '外接框面积', 'content': '面积等于宽乘高',
              'source_name': '课程规范', 'source_url': 'https://example.test/area'}
    output = asyncio.run(tutor.answer(
        '外接框面积是什么意思？', 'QUESTION_TUTOR', {}, [], QUESTION, 0,
        False, None, [], None,
        knowledge_loader=lambda query: loads.append(query) or [source]))
    assert loads == ['目标框外接面积定义']
    assert output['tools_used'] == ['search_knowledge']
    assert output['sources'][0]['id'] == 'KB-AREA'
    assert len(completions.calls) == 2


def test_question_context_and_vision_are_available_only_on_model_request(monkeypatch):
    completions = install_model(monkeypatch, [
        model_message(tool_calls=[
            tool_call('context-1', 'read_question_context',
                      {'section': 'candidate_comparison'}),
            tool_call('vision-1', 'inspect_image', {'question': '候选目标有哪些？'}),
        ]),
        model_message({'reply': '系统比较表显示右侧候选的外接框面积排名第一。',
                       'claims': [{'fact': 'expected_position', 'value': '右侧'}],
                       'used_source_ids': [], 'followups': []}),
    ])
    image_calls = []

    async def fake_inspect(*args):
        image_calls.append(args[-2])
        return {'available': True, 'observation': '画面中有多个候选人物',
                'authority': 'visual_observation_not_grading_fact'}

    monkeypatch.setattr(tutor, '_inspect_image', fake_inspect)
    answer, result, _ = wrong_instance_facts()
    output = asyncio.run(tutor.answer(
        '为什么是这个目标？', 'QUESTION_TUTOR', {}, [], QUESTION, 0, True,
        result, [], answer))
    assert output['provider'] == 'deepseek'
    assert output['tools_used'] == ['read_question_context', 'inspect_image']
    assert image_calls == ['候选目标有哪些？']
    tool_outputs = [item for item in completions.calls[1]['messages']
                    if item['role'] == 'tool']
    assert 'bbox_area_ratio' in tool_outputs[0]['content']


def test_fact_validator_regenerates_instead_of_repeating_bad_answer(monkeypatch):
    completions = install_model(monkeypatch, [
        model_message({'reply': '你漏标了其他行人，而且边界没有贴合。',
                       'claims': [{'fact': 'diagnosis', 'value': 'MISSED_TARGET'}],
                       'used_source_ids': [], 'followups': []}),
        model_message({'reply': '你选中了另一个有效行人；这不是漏标所有行人，零交并比也不能评价所选框边界。',
                       'claims': [{'fact': 'diagnosis', 'value': 'WRONG_TARGET_INSTANCE'}],
                       'used_source_ids': [], 'followups': ['我应该怎么重新框？']}),
    ])
    answer, result, _ = wrong_instance_facts()
    output = asyncio.run(tutor.answer(
        '为什么是这个目标？', 'QUESTION_TUTOR', {}, [], QUESTION, 0, True,
        result, [], answer))
    assert output['provider'] == 'deepseek'
    assert output['validation_retries'] == 1
    assert '不是漏标' in output['text']
    assert output['suggestions'] == ['我应该怎么重新框？']
    validator_prompt = completions.calls[1]['messages'][-1]['content']
    assert 'FACT_CONTRADICTION' in validator_prompt


def test_already_asked_followups_are_not_suggested_again(monkeypatch):
    install_model(monkeypatch, [model_message({
        'reply': '比较时用外接框宽乘高。',
        'claims': [{'fact': 'selection_rule', 'value': 'largest_bbox_area'}],
        'used_source_ids': [],
        'followups': ['为什么是这个目标？', '我应该怎么重新框？'],
    })])
    output = asyncio.run(tutor.answer(
        '怎样比较目标大小？', 'QUESTION_TUTOR', {}, [], QUESTION, 0, False,
        None, [{'role': 'user', 'text': '为什么是这个目标？'}], None))
    assert output['suggestions'] == ['我应该怎么重新框？']


def test_homepage_model_understands_from_history_without_eager_tools(monkeypatch):
    completions = install_model(monkeypatch, [model_message({
        'reply': '你是在追问刚才提到的外接框面积：用宽乘高比较即可。',
        'claims': [], 'used_source_ids': [], 'used_resource_ids': [],
        'followups': [],
    })])
    calls = []
    output = asyncio.run(tutor.answer(
        '我哪里做错了', 'GENERAL_TUTOR', {}, [], history=[
            {'role': 'user', 'text': '怎样比较目标大小？'},
            {'role': 'assistant', 'text': '可以比较候选目标的外接框面积。'},
        ], knowledge_loader=lambda query: calls.append(('knowledge', query)) or [],
        learning_context_loader=lambda: calls.append(('learning', '')) or {},
        resource_loader=lambda query: calls.append(('resource', query)) or []))
    assert output['provider'] == 'deepseek'
    assert output['tools_used'] == [] and calls == []
    first_prompt = completions.calls[0]['messages'][1]['content']
    assert '怎样比较目标大小' in first_prompt and '我哪里做错了' in first_prompt
    assert completions.calls[0]['tool_choice'] == 'auto'


def test_homepage_tools_are_loaded_only_after_model_requests_them(monkeypatch):
    completions = install_model(monkeypatch, [
        model_message(tool_calls=[
            tool_call('profile-1', 'get_learning_context', {'reason': '需要推荐下一步'}),
            tool_call('rag-1', 'search_knowledge', {'query': '目标检测学习重点'}),
            tool_call('resource-1', 'search_learning_resources', {'query': 'A4'}),
        ]),
        model_message({
            'reply': '你当前推荐学习目标检测与定位，可以进入对应能力模块继续训练。',
            'claims': [
                {'fact': 'recommended_ability_id', 'value': 'A4'},
                {'fact': 'recommended_ability_name', 'value': '目标检测与定位'},
            ],
            'used_source_ids': ['KB-A4'],
            'used_resource_ids': ['ability:A4'],
            'followups': ['要先看知识还是开始训练？'],
        }),
    ])
    invoked = []
    learning = {
        'goal': '岗位入门', 'daily_goal_minutes': 15,
        'recommended_ability_id': 'A4',
        'recommended_ability_name': '目标检测与定位',
        'recommended_level_id': 'A4-L1',
        'recommended_level_name': '目标发现', 'recommended_mastery': 20,
    }
    source = {'id': 'KB-A4', 'title': '目标检测重点', 'content': '先识别任务范围。',
              'source_name': '课程资料', 'source_url': 'https://example.test/a4'}
    resource = {'id': 'ability:A4', 'title': '目标检测与定位',
                'description': '练习目标检测', 'url': '/skills/A4'}
    output = asyncio.run(tutor.answer(
        '结合我的情况推荐下一步课程', 'GENERAL_TUTOR', {}, [],
        knowledge_loader=lambda query: invoked.append(('knowledge', query)) or [source],
        learning_context_loader=lambda: invoked.append(('learning', '')) or learning,
        resource_loader=lambda query: invoked.append(('resource', query)) or [resource]))
    assert [name for name, _ in invoked] == ['learning', 'knowledge', 'resource']
    assert output['tools_used'] == [
        'get_learning_context', 'search_knowledge', 'search_learning_resources']
    assert output['sources'][0]['id'] == 'KB-A4'
    assert output['resources'][0]['id'] == 'ability:A4'
    tool_outputs = [item for item in completions.calls[1]['messages']
                    if item['role'] == 'tool']
    assert 'recommended_ability_name' in tool_outputs[0]['content']
    assert '/skills/A4' in tool_outputs[2]['content']


def test_homepage_grounding_validator_retries_unsupported_personal_claim(monkeypatch):
    completions = install_model(monkeypatch, [
        model_message({
            'reply': '你当前已经掌握目标检测的 90%。',
            'claims': [{'fact': 'recommended_mastery', 'value': 90}],
            'used_source_ids': [], 'used_resource_ids': [], 'followups': [],
        }),
        model_message({
            'reply': '我还没有读取你的学习记录；如果你希望个性化分析，我可以先查看学习画像。',
            'claims': [], 'used_source_ids': [], 'used_resource_ids': [],
            'followups': ['要结合我的学习记录分析吗？'],
        }),
    ])
    output = asyncio.run(tutor.answer(
        '给我一些建议', 'GENERAL_TUTOR', {}, [],
        knowledge_loader=lambda query: [], learning_context_loader=lambda: {},
        resource_loader=lambda query: []))
    assert output['provider'] == 'deepseek'
    assert output['validation_retries'] == 1
    assert '还没有读取' in output['text']
    validator_prompt = completions.calls[1]['messages'][-1]['content']
    assert 'LEARNING_CONTEXT_NOT_LOADED' in validator_prompt


def test_homepage_resource_advice_does_not_require_personal_profile():
    payload = {
        'reply': '建议你先进入目标检测与定位模块，你现在可以从这里开始。',
        'claims': [], 'used_source_ids': [],
        'used_resource_ids': ['ability:A4'], 'followups': [],
    }
    errors = validate_homepage_payload(
        payload, build_homepage_facts(tutor.homepage_platform_context()), [],
        ['ability:A4'])
    assert errors == []
