"""Learner evidence and explainable recommendations; no model controls grades."""
from collections import Counter, defaultdict
from sqlalchemy import select
from .catalog import ABILITIES, levels
from .db import Progress, Run
from .grading import grade

MODE_WEIGHTS = {'course': 1.0, 'job': 2.0, 'competition': 3.0}


def _recent_average(values):
    selected = values[:3]  # newest first; a later regression must remain visible
    weights = (0.6, 0.3, 0.1)[:len(selected)]
    return round(sum(v * w for v, w in zip(selected, weights)) / sum(weights), 1) if selected else 0.0


def _diagnosis(user):
    result = defaultdict(list)
    for entry in (user.diagnostic or {}).get('skills', []):
        aid = entry.get('ability_id')
        if aid and isinstance(entry.get('correct'), bool):
            result[aid].append(entry)
    return result


def ability_state(db, user):
    progress = list(db.scalars(select(Progress).where(Progress.username == user.username)))
    done = {p.level_id: p.score for p in progress}
    runs = list(db.scalars(select(Run).where(
        Run.username == user.username, Run.mode != 'onboarding'
    ).order_by(Run.started_at.desc())))
    by_run_id = {run.id: run for run in runs}
    skill_counts = defaultdict(Counter)
    level_scores = defaultdict(list)
    skill_errors = defaultdict(Counter)
    error_runs = Counter()
    for run in runs:
        # Package/competition answers stay private until final submission. Updating
        # their public skill score earlier would disclose per-question correctness.
        if run.status != 'completed' and run.mode != 'course':
            continue
        results = {r['question_id']: r for r in (run.report or {}).get('results', [])}
        if run.status == 'completed' and run.report:
            level_scores[run.level_id].append(float(run.report.get('score', 0)))
        parent = by_run_id.get(run.revision_of)
        parent_results = {r['question_id']: r for r in (parent.report or {}).get('results', [])} if parent else {}
        observed_skills = set()
        for question in run.questions or []:
            qid, sid = question['id'], question.get('skill_id')
            if not sid or qid not in (run.answers or {}):
                continue
            # A repair inherits previously correct answers without submitting them
            # again. Those copies must not inflate the answer count or skill score.
            if (parent and parent_results.get(qid, {}).get('correct')
                    and qid in (parent.answers or {}) and run.answers[qid] == parent.answers[qid]):
                continue
            result = results.get(qid) if run.status == 'completed' else None
            if result is None or not isinstance(result.get('correct'), bool):
                result = grade(question, run.answers[qid])
            attempts, correct_attempts = 1, int(result['correct'])
            if run.mode == 'course' and not run.level_id.startswith('JT-'):
                attempt_key = f'course-score-attempts:{qid}'
                correct_key = f'course-score-correct-attempts:{qid}'
                attempts = max(1, int((run.hints or {}).get(attempt_key, 0)))
                correct_attempts = int((run.hints or {}).get(correct_key, int(result['correct'])))
            weight = MODE_WEIGHTS.get(run.mode, 1.0)
            skill_counts[sid]['answer_count'] += 1
            skill_counts[sid]['correct_count'] += int(result['correct'])
            skill_counts[sid]['weighted_answer_count'] += attempts * weight
            skill_counts[sid]['weighted_correct_count'] += correct_attempts * weight
            observed_skills.add(sid)
            if result.get('error_type') and error_runs[sid] < 3:
                skill_errors[sid][result['error_type']] += 1
        error_runs.update(observed_skills)

    diagnosis = _diagnosis(user)
    states = []
    for a in ABILITIES:
        lv = levels(a['id'])
        metrics = []
        for index, name in enumerate(a['skills'], 1):
            sid = f'{a["id"]}-S{index}'
            counts = skill_counts[sid]
            answers, correct = counts['answer_count'], counts['correct_count']
            weighted_answers = counts['weighted_answer_count']
            weighted_correct = counts['weighted_correct_count']
            accuracy = weighted_correct / weighted_answers if weighted_answers else 0
            metrics.append({'skill_id': sid, 'name': name, 'score': round(accuracy * 100, 2),
                            'skill_score': round(accuracy * 10, 2),
                            'answer_count': answers, 'correct_count': correct,
                            'weighted_answer_count': weighted_answers,
                            'weighted_correct_count': weighted_correct,
                            'source': 'training' if answers else 'unassessed', 'assessed': bool(answers),
                            'recent_errors': [key for key, _ in skill_errors[sid].most_common(3)]})
        level_states = []
        for level in lv:
            measured = level_scores[level['id']]
            state = dict(level,
                unlocked=True,
                completed=level['id'] in done,
                score=round(_recent_average(measured)) if measured else done.get(level['id'], 0),
                best_score=done.get(level['id'], 0))
            if level['mode'] == 'course':
                metric = next(s for s in metrics if s['skill_id'] == level['skill_id'])
                state.update({key: metric[key] for key in ('skill_score', 'answer_count', 'correct_count',
                                                            'weighted_answer_count', 'weighted_correct_count')})
            level_states.append(state)
        diag = diagnosis[a['id']]
        answers = sum(s['answer_count'] for s in metrics)
        correct = sum(s['correct_count'] for s in metrics)
        weighted_answers = sum(s['weighted_answer_count'] for s in metrics)
        weighted_correct = sum(s['weighted_correct_count'] for s in metrics)
        accuracy = weighted_correct / weighted_answers if weighted_answers else 0
        states.append(dict(a, mastery=round(accuracy * 100, 2), skill_score=round(accuracy * 10, 2),
            answer_count=answers, correct_count=correct,
            weighted_answer_count=weighted_answers, weighted_correct_count=weighted_correct,
            completed=sum(l['completed'] for l in level_states), total=len(lv), levels=level_states,
            skill_mastery=metrics, diagnostic_score=round(sum(e['correct'] for e in diag) / len(diag) * 100) if diag else None,
            recent_errors=list(dict.fromkeys(error for s in metrics for error in s['recent_errors']))))
    return states


def _depth(aid, byid, visiting=None):
    visiting = set(visiting or ())
    if aid in visiting:
        return 0
    visiting.add(aid)
    parents = [p for p in byid[aid].get('prerequisites', []) if p in byid]
    return 0 if not parents else 1 + max(_depth(p, byid, visiting) for p in parents)


def _next_level(ability, goal):
    unlocked = [l for l in ability['levels'] if l['unlocked']]
    if not unlocked:
        return ability['levels'][0]
    weak = sorted((l for l in unlocked if l['completed'] and l['mode'] == 'course' and l['score'] < 60), key=lambda l: l['score'])
    if weak:
        return weak[0]
    pending = [l for l in unlocked if not l['completed']]
    # Opening every entry point does not remove the recommended teaching order.
    # Finish the foundational lessons before suggesting a package or competition.
    pending_course = next((l for l in pending if l['mode'] == 'course'), None)
    if pending_course:
        return pending_course
    preferred = 'competition' if goal == '竞赛备战' else 'job' if goal == '岗位入门' else 'course'
    return next((l for l in pending if l['mode'] == preferred), pending[0] if pending else min(unlocked, key=lambda l: l['score']))


def recommendation(states, goal):
    byid = {a['id']: a for a in states}
    if not states:
        raise ValueError('能力树不能为空')
    candidates = [a for a in states if a['mastery'] < 95 or any(not l['completed'] for l in a['levels'])] or states
    selected_levels = {a['id']: _next_level(a, goal) for a in candidates}

    def weight(a):
        upstream = 1 / (1 + _depth(a['id'], byid))
        deficit = (100 - a['mastery']) / 100
        # Diagnostics guide recommendations independently from the score calculated
        # from real saved training answers. All levels remain freely available.
        blocked = sum(byid[p]['mastery'] < 40 and (byid[p].get('diagnostic_score') or 0) < 70
                      for p in a.get('prerequisites', []) if p in byid)
        diagnosed_weak = .28 if a.get('diagnostic_score') is not None and a['diagnostic_score'] < 60 and not a['completed'] else 0
        mode = selected_levels[a['id']]['mode']
        goal_fit = .16 if goal == '竞赛备战' and mode == 'competition' else .10 if goal == '岗位入门' and mode == 'job' else .06 if goal == '课程补强' and mode == 'course' else 0
        return .35 * upstream + .45 * deficit - .55 * blocked + diagnosed_weak + goal_fit

    a = max(candidates, key=weight)
    level = selected_levels[a['id']]
    if level['completed'] and level['score'] < 60:
        reason = f'最近训练显示「{level["name"]}」得分为 {level["score"]} 分，建议先复习这个薄弱环节。'
    elif a.get('diagnostic_score') is not None and a['diagnostic_score'] < 60 and not a['completed']:
        reason = f'入门诊断发现你在{a["name"]}上需要补强，先完成「{level["name"]}」。'
    else:
        reason = f'结合「{goal}」目标与技能前置关系，建议学习「{level["name"]}」。当前技能分 {a["skill_score"]:.2f} / 10。'
    path = [level] + [l for l in a['levels'] if l['id'] != level['id'] and not l['completed']]
    return {'ability_id': a['id'], 'ability_name': a['name'], 'level': level, 'mastery': a['mastery'],
            'skill_score': a['skill_score'], 'answer_count': a['answer_count'], 'correct_count': a['correct_count'],
            'reason': reason, 'path': [{'id': l['id'], 'name': l['name'], 'mode': l['mode'], 'unlocked': l['unlocked']} for l in path[:4]]}


def learner_context(user, states, aid=None, skill=None):
    rec = recommendation(states, user.goal)
    state = next(a for a in states if a['id'] == (aid or rec['ability_id']))
    current_skill = skill or _next_level(state, user.goal)['skill_id']
    metric = next((s for s in state.get('skill_mastery', []) if s['skill_id'] == current_skill), None)
    return {'goal': user.goal, 'ability_id': state['id'], 'ability_name': state['name'],
            'skill_id': current_skill, 'skill_name': metric['name'] if metric else None,
            'mastery': metric['score'] if metric else state['mastery'],
            'skill_score': metric['skill_score'] if metric else state['skill_score'],
            'answer_count': metric['answer_count'] if metric else state['answer_count'],
            'correct_count': metric['correct_count'] if metric else state['correct_count'],
            'recent_errors': state.get('recent_errors', []),
            'weak_skills': [s for s in state.get('skill_mastery', []) if s['assessed'] and s['score'] < 65],
            'completed_levels': [l['name'] for l in state['levels'] if l['completed']],
            'next_learning': rec['level']['name'], 'recommendation_reason': rec['reason'],
            'learning_path': rec['path'], 'diagnostic': user.diagnostic}
