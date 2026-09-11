"""Authoritative facts and post-generation validation for the question tutor.

The tutor model is free to understand the learner's wording. This module does
not classify that wording. It only exposes application facts and checks that
the generated answer does not contradict them.
"""
import re

from .grading import iou, valid_box


def build_homepage_facts(platform_context, learning_context=None):
    """Expose only program-owned homepage facts to the grounding validator."""
    platform = dict(platform_context or {})
    learning = dict(learning_context or {}) if learning_context else None
    allowed = {
        'platform_name': platform.get('platform_name'),
        'assistant_name': platform.get('assistant_name'),
        'assistant_role': platform.get('assistant_role'),
    }
    if learning:
        allowed.update({
            'learning_goal': learning.get('goal'),
            'daily_goal_minutes': learning.get('daily_goal_minutes'),
            'recommended_ability_id': learning.get('recommended_ability_id'),
            'recommended_ability_name': learning.get('recommended_ability_name'),
            'recommended_level_id': learning.get('recommended_level_id'),
            'recommended_level_name': learning.get('recommended_level_name'),
            'recommended_mastery': learning.get('recommended_mastery'),
        })
    return {
        'platform': platform,
        'learning_context_loaded': bool(learning),
        'learning_context': learning,
        'allowed_claims': {key: value for key, value in allowed.items()
                           if value is not None},
    }


def validate_homepage_payload(payload, facts, available_source_ids=None,
                              available_resource_ids=None):
    """Validate homepage grounding without classifying the user's question."""
    errors = []
    if not isinstance(payload, dict):
        return [{'code': 'INVALID_JSON_OBJECT'}]
    reply = str(payload.get('reply') or '').strip()
    if not reply:
        errors.append({'code': 'EMPTY_REPLY'})

    claims = payload.get('claims', [])
    if not isinstance(claims, list):
        errors.append({'code': 'INVALID_CLAIMS'})
        claims = []
    allowed = facts.get('allowed_claims', {})
    for claim in claims:
        if not isinstance(claim, dict) or not claim.get('fact'):
            errors.append({'code': 'INVALID_CLAIM_SHAPE'})
            continue
        name, value = claim['fact'], claim.get('value')
        if name not in allowed:
            errors.append({'code': 'UNSUPPORTED_FACT', 'fact': name})
        elif isinstance(allowed[name], float) and isinstance(value, (float, int)):
            if abs(allowed[name] - float(value)) > .001:
                errors.append({'code': 'FACT_CONTRADICTION', 'fact': name,
                               'expected': allowed[name], 'received': value})
        elif value != allowed[name]:
            errors.append({'code': 'FACT_CONTRADICTION', 'fact': name,
                           'expected': allowed[name], 'received': value})

    for field, available, invalid_code, unknown_code in (
            ('used_source_ids', set(available_source_ids or []),
             'INVALID_SOURCE_IDS', 'UNKNOWN_SOURCE'),
            ('used_resource_ids', set(available_resource_ids or []),
             'INVALID_RESOURCE_IDS', 'UNKNOWN_RESOURCE')):
        used = payload.get(field, [])
        if not isinstance(used, list):
            errors.append({'code': invalid_code})
        else:
            for item_id in used:
                if item_id not in available:
                    errors.append({'code': unknown_code, 'id': item_id})

    followups = payload.get('followups', [])
    if not isinstance(followups, list) or len(followups) > 3 or any(
            not isinstance(item, str) or not item.strip() or len(item) > 30
            for item in followups):
        errors.append({'code': 'INVALID_FOLLOWUPS'})

    compact = re.sub(r'\s+', '', reply)
    personal_fact = re.search(
        r'你(?:当前|现在|最近)(?:的|已经)?(?:学习目标|掌握度|薄弱项|学习进度|得分|完成|掌握|通过)|'
        r'你(?:已经|尚未|还没)(?:完成|掌握|通过|学习)|'
        r'你的(?:学习目标|掌握度|薄弱项|学习进度|得分)|'
        r'你每天(?:学习|训练)', compact)
    if personal_fact:
        if not facts.get('learning_context_loaded'):
            errors.append({'code': 'LEARNING_CONTEXT_NOT_LOADED'})
        elif not any(str(claim.get('fact', '')).startswith(
                ('learning_', 'daily_', 'recommended_')) for claim in claims
                if isinstance(claim, dict)):
            errors.append({'code': 'MISSING_PERSONAL_FACT_CLAIM'})
    if re.search(r'sk-[a-zA-Z0-9]{12,}', reply):
        errors.append({'code': 'SECRET_PATTERN'})
    return errors


def question_policy(question, submitted=False):
    question = question or {}
    title = str(question.get('title', ''))
    expected = question.get('answer')
    expected_count = len(expected) if isinstance(expected, list) else 1
    selection_rule = question.get('selection_rule')
    target_scope = question.get('target_scope')
    if not selection_rule and '最大' in title:
        selection_rule = 'largest_bbox_area'
    elif not selection_rule and '最小' in title:
        selection_rule = 'smallest_bbox_area'
    if not target_scope:
        if selection_rule:
            target_scope = 'single_selected'
        elif re.search(r'所有|全部|逐一', title):
            target_scope = 'all_required'
        elif submitted and expected_count > 1:
            target_scope = 'all_required'
        else:
            target_scope = 'single'
    policy = {
        'task_type': question.get('type'),
        'target_scope': target_scope,
        'selection_rule': selection_rule,
        'project_rule': question.get('project_rule') or '',
    }
    if selection_rule in ('largest_bbox_area', 'smallest_bbox_area'):
        policy['selection_measure'] = 'normalized_bbox_width * normalized_bbox_height'
        policy['invalid_selection_proxies'] = [
            'camera_distance', 'visual_salience', 'visible_height_alone']
    if submitted:
        policy['expected_count'] = expected_count
        policy['threshold'] = question.get('threshold', .65)
    return policy


def source_applies(source, policy):
    """Prevent retrieved general guidance from overriding the current task."""
    if not source:
        return False
    text = f"{source.get('title', '')} {source.get('content', '')}"
    if policy.get('target_scope') == 'single_selected' and re.search(
            r'覆盖.{0,8}所有实例|所有.{0,8}实例.{0,8}(都|全部|逐一).{0,8}标|标(?:注)?全.{0,8}目标', text):
        return False
    return True


def _expected_targets(question):
    expected = (question or {}).get('answer')
    if isinstance(expected, list):
        return [item for item in expected if isinstance(item, dict)]
    return [expected] if isinstance(expected, dict) else []


def _user_boxes(user_answer):
    boxes = user_answer.get('boxes', []) if isinstance(user_answer, dict) else []
    return [item for item in boxes if isinstance(item, dict) and valid_box(item.get('box'))]


def _position(box):
    if not valid_box(box):
        return '参考位置'
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    horizontal = '左侧' if cx < .4 else '右侧' if cx > .6 else '中间'
    vertical = '上方' if cy < .34 else '下方' if cy > .72 else ''
    return vertical + horizontal if vertical else horizontal


def _best_candidate(user_box, candidates, label):
    eligible = [item for item in (candidates or []) if isinstance(item, dict)
                and item.get('label') == label and valid_box(item.get('box'))]
    if not eligible:
        return None, 0.
    target = max(eligible, key=lambda item: iou(user_box, item['box']))
    return target, iou(user_box, target['box'])


def build_facts(question, submitted=False, result=None, user_answer=None,
                candidate_targets=None, hint_count=0):
    """Create the only authoritative factual input used by the question tutor."""
    policy = question_policy(question, submitted)
    facts = {
        'answer_state': 'submitted' if submitted else 'not_submitted',
        'hint_level': min(max(hint_count + 1, 1), 3),
        'task_policy': policy,
        'assessment': None,
        'disclosure': {
            'may_reveal_reference': bool(submitted),
            'may_reveal_current_image_target': bool(submitted),
        },
    }
    allowed = {
        'answer_state': facts['answer_state'],
        'task_scope': policy.get('target_scope'),
        'selection_rule': policy.get('selection_rule'),
    }
    if not submitted or not result:
        facts['allowed_claims'] = allowed
        return facts

    expected = _expected_targets(question)
    users = _user_boxes(user_answer)
    expected_count = len(expected) or int(result.get('expected_count') or 1)
    submitted_count = len(users)
    label = expected[0].get('label') if expected else None
    label_ok = bool(users and label and users[0].get('label') == label)
    expected_iou = max((iou(u['box'], target.get('box')) for u in users for target in expected
                        if valid_box(target.get('box'))), default=0.)
    evidence = {
        'backend_error_type': str(result.get('error_type') or ''),
        'correct': bool(result.get('correct')),
        'score': result.get('score'),
        'expected_count': expected_count,
        'submitted_count': submitted_count,
        'submitted_label': users[0].get('label') if users else None,
        'expected_label': label,
        'label_correct': label_ok,
        'reference_iou': round(float(result.get('iou') or expected_iou), 6),
        'geometry_diagnosable': expected_iou >= .1,
    }
    diagnosis = 'CORRECT' if result.get('correct') else str(result.get('error_type') or 'UNKNOWN')
    matched_candidate = None
    candidate_iou = 0.
    if users and label:
        matched_candidate, candidate_iou = _best_candidate(users[0]['box'], candidate_targets, label)
        if matched_candidate:
            evidence['submitted_candidate_position'] = _position(matched_candidate.get('box'))
            evidence['candidate_match_iou'] = round(candidate_iou, 6)
    if expected:
        evidence['expected_position'] = _position(expected[0].get('box'))

    single_selection = policy.get('target_scope') == 'single_selected' and expected_count == 1
    if not result.get('correct') and not users:
        diagnosis = 'MISSING_ANSWER'
    elif not result.get('correct') and submitted_count > expected_count:
        diagnosis = 'EXTRA_TARGET'
    elif (not result.get('correct') and single_selection and label_ok and expected_iou < .1
          and matched_candidate is not None and candidate_iou >= .1
          and all(iou(matched_candidate['box'], target.get('box')) < .999 for target in expected)):
        diagnosis = 'WRONG_TARGET_INSTANCE'
        evidence['geometry_diagnosable'] = False
    elif not result.get('correct') and single_selection and expected_iou < .1:
        diagnosis = 'TARGET_LOCATION_MISMATCH'
        evidence['geometry_diagnosable'] = False
    elif not result.get('correct') and expected_count > 1 and result.get('missed'):
        diagnosis = 'MISSED_TARGET'
    elif not result.get('correct') and expected_iou >= .1 and not label_ok:
        diagnosis = 'LABEL_CONFUSION'
    elif not result.get('correct') and expected_iou >= .1:
        diagnosis = 'BOUNDING_BOX_BOUNDARY'

    evidence['diagnosis'] = diagnosis
    facts['assessment'] = evidence
    allowed.update({
        'correct': evidence['correct'],
        'diagnosis': diagnosis,
        'expected_count': expected_count,
        'submitted_count': submitted_count,
        'label_correct': label_ok,
        'geometry_diagnosable': evidence['geometry_diagnosable'],
        'reference_iou': evidence['reference_iou'],
        'expected_position': evidence.get('expected_position'),
        'submitted_candidate_position': evidence.get('submitted_candidate_position'),
    })
    facts['allowed_claims'] = allowed
    return facts


def additional_question_context(section, question, facts, candidate_targets=None,
                                user_answer=None, result=None):
    """Return more context on demand while enforcing answer disclosure rules."""
    section = str(section or 'rules')
    submitted = facts.get('answer_state') == 'submitted'
    if section == 'rules':
        return {
            'title': (question or {}).get('title'),
            'instruction': (question or {}).get('instruction'),
            'project_rule': (question or {}).get('project_rule'),
            'labels': (question or {}).get('labels'),
            'task_policy': facts.get('task_policy'),
        }
    if not submitted:
        return {'available': False, 'reason': '提交前不能读取标准答案或当前图片目标事实'}
    if section == 'grading_evidence':
        return {'available': True, 'assessment': facts.get('assessment'),
                'user_answer': user_answer}
    if section == 'reference':
        return {'available': True, 'standard_answer': (result or {}).get('standard_answer'),
                'explanation': (question or {}).get('explanation')}
    if section == 'candidate_comparison':
        expected = _expected_targets(question)
        users = _user_boxes(user_answer)
        label = expected[0].get('label') if expected else None
        rows = []
        for target in candidate_targets or []:
            if not isinstance(target, dict) or target.get('label') != label or not valid_box(target.get('box')):
                continue
            box = target['box']
            rows.append({
                'position': _position(box),
                'label': target.get('label'),
                'width_ratio': round(box[2], 6),
                'height_ratio': round(box[3], 6),
                'bbox_area_ratio': round(box[2] * box[3], 6),
                'is_reference_target': any(iou(box, item.get('box')) >= .999 for item in expected),
                'matches_user_submission': any(iou(box, item.get('box')) >= .1 for item in users),
            })
        rows.sort(key=lambda row: row['bbox_area_ratio'], reverse=True)
        for index, row in enumerate(rows):
            row['area_rank'] = index + 1
        return {'available': bool(rows), 'comparison_basis': facts['task_policy'].get('selection_rule'),
                'candidates': rows}
    return {'available': False, 'reason': '不支持的题目上下文区段'}


def _negated(text, index):
    prefix = text[max(0, index - 10):index]
    return bool(re.search(r'(不是|并非|而非|不算|不能说|不能判断为|没有|并没有|未发生|不属于)[^，。；！？]{0,4}$', prefix))


def _positive_term(text, pattern):
    return any(not _negated(text, match.start()) for match in re.finditer(pattern, text))


def validate_model_payload(payload, question, facts, available_source_ids=None):
    """Check structured claims and high-risk prose against application facts."""
    errors = []
    if not isinstance(payload, dict):
        return [{'code': 'INVALID_JSON_OBJECT'}]
    reply = str(payload.get('reply') or '').strip()
    if not reply:
        errors.append({'code': 'EMPTY_REPLY'})
    claims = payload.get('claims', [])
    if not isinstance(claims, list):
        errors.append({'code': 'INVALID_CLAIMS'})
        claims = []
    allowed = facts.get('allowed_claims', {})
    for claim in claims:
        if not isinstance(claim, dict) or not claim.get('fact'):
            errors.append({'code': 'INVALID_CLAIM_SHAPE'})
            continue
        name, value = claim['fact'], claim.get('value')
        if name not in allowed:
            errors.append({'code': 'UNSUPPORTED_FACT', 'fact': name})
        elif isinstance(allowed[name], float) and isinstance(value, (float, int)):
            if abs(allowed[name] - float(value)) > .001:
                errors.append({'code': 'FACT_CONTRADICTION', 'fact': name,
                               'expected': allowed[name], 'received': value})
        elif value != allowed[name]:
            errors.append({'code': 'FACT_CONTRADICTION', 'fact': name,
                           'expected': allowed[name], 'received': value})

    source_ids = set(available_source_ids or [])
    used = payload.get('used_source_ids', [])
    if not isinstance(used, list):
        errors.append({'code': 'INVALID_SOURCE_IDS'})
    else:
        for source_id in used:
            if source_id not in source_ids:
                errors.append({'code': 'UNKNOWN_SOURCE', 'source_id': source_id})
    followups = payload.get('followups', [])
    if not isinstance(followups, list) or len(followups) > 3 or any(
            not isinstance(item, str) or not item.strip() or len(item) > 30 for item in followups):
        errors.append({'code': 'INVALID_FOLLOWUPS'})

    assessment = facts.get('assessment') or {}
    diagnosis = assessment.get('diagnosis')
    compact = re.sub(r'\s+', '', reply)
    if re.search(r'\b(?:WRONG_TARGET_INSTANCE|TARGET_LOCATION_MISMATCH|MISSED_TARGET|EXTRA_TARGET|LABEL_CONFUSION|BOUNDING_BOX_BOUNDARY)\b', reply):
        errors.append({'code': 'INTERNAL_DIAGNOSIS_EXPOSED'})
    if diagnosis in ('WRONG_TARGET_INSTANCE', 'TARGET_LOCATION_MISMATCH'):
        if _positive_term(compact, r'漏标|漏选|漏掉'):
            errors.append({'code': 'UNSUPPORTED_MISSED_TARGET_CLAIM'})
    if assessment and not assessment.get('geometry_diagnosable', True):
        if _positive_term(compact, r'边界.{0,6}(没|未|不).{0,4}贴合|框.{0,5}(太大|太小|不准|不准确)|边界错误'):
            errors.append({'code': 'UNSUPPORTED_BOUNDARY_CLAIM'})
    if facts.get('task_policy', {}).get('target_scope') == 'single_selected':
        if _positive_term(compact, r'(应该|需要|必须|要).{0,8}(所有|全部).{0,8}(目标|实例|行人).{0,6}标|所有.{0,8}(目标|实例|行人).{0,5}(都|全部).{0,3}(要|需|应该|必须).{0,3}标'):
            errors.append({'code': 'TASK_SCOPE_CONTRADICTION'})
    if facts.get('task_policy', {}).get('selection_rule') in (
            'largest_bbox_area', 'smallest_bbox_area'):
        if re.search(r'(通常|一般).{0,8}(就是|等于|是).{0,12}(离镜头.{0,4}近|更显眼|最高大)', compact):
            errors.append({'code': 'UNSUPPORTED_SIZE_PROXY'})
    return errors


def fallback_response(question, facts, result=None):
    """Last-resort factual summary; normal question answering stays model-led."""
    if facts.get('answer_state') != 'submitted':
        hints = (question or {}).get('hint') or ['先读清任务，再按规范观察目标。']
        hint = hints[min(max(0, facts.get('hint_level', 1) - 1), len(hints) - 1)]
        if facts.get('task_policy', {}).get('selection_rule') == 'largest_bbox_area':
            return ('本题的“最大”按候选目标外接框的宽×高比较，不按距离镜头远近、显眼程度或单独高度判断。'
                    + str(hint))
        if facts.get('task_policy', {}).get('selection_rule') == 'smallest_bbox_area':
            return ('本题的“最小”按候选目标外接框的宽×高比较，不按距离镜头远近、显眼程度或单独高度判断。'
                    + str(hint))
        return hint
    evidence = facts.get('assessment') or {}
    code = evidence.get('diagnosis')
    if code == 'WRONG_TARGET_INSTANCE':
        return (f'确定性记录显示：本题要求 1 个目标，你提交的标签正确；提交框匹配{evidence.get("submitted_candidate_position", "另一位置")}目标，'
                f'参考答案位于{evidence.get("expected_position", "参考位置")}。两者属于不同实例，因此交并比为 '
                f'{evidence.get("reference_iou", 0) * 100:.1f}%；该数值不能用于判断你给所选实例画的边界质量。')
    if code == 'TARGET_LOCATION_MISMATCH':
        return '确定性记录只能确认提交区域与参考目标没有有效重叠，无法证明你框住了另一个有效实例，也无法据此评价边界。'
    if code == 'MISSED_TARGET':
        return f'确定性记录显示，本题要求 {evidence.get("expected_count", 1)} 个目标，当前仍有参考目标未匹配。'
    if code == 'EXTRA_TARGET':
        return f'确定性记录显示，本题要求 {evidence.get("expected_count", 1)} 个目标，但提交了 {evidence.get("submitted_count", 0)} 个。'
    if code == 'LABEL_CONFUSION':
        return '确定性记录显示，提交区域已经匹配参考目标，主要差异在类别。'
    if code in ('BOUNDING_BOX_BOUNDARY', 'POLYGON_BOUNDARY', 'ENTITY_BOUNDARY'):
        return f'确定性记录显示已匹配参考目标，当前区域交并比为 {evidence.get("reference_iou", 0) * 100:.1f}%，可以继续检查边界。'
    if code == 'CORRECT':
        return '确定性记录显示，这次提交已经通过。'
    feedback = str((result or {}).get('feedback') or '')
    metric = (result or {}).get('iou')
    if isinstance(metric, (int, float)):
        return f'当前区域与参考区域的交并比为 {metric * 100:.1f}%。{feedback}'.strip()
    return feedback or '当前模型暂不可用，请稍后重试。'


def plain_text(text):
    text = str(text or '').replace('**', '').replace('`', '')
    return re.sub(r'\n{3,}', '\n\n', text).strip()
