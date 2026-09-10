"""Learner evidence and explainable recommendations; no model controls grades."""
from collections import Counter, defaultdict
from sqlalchemy import select
from .catalog import ABILITIES, levels
from .db import Progress, Run


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
        Run.username == user.username, Run.status == 'completed', Run.mode != 'onboarding'
    ).order_by(Run.finished_at.desc()).limit(120)))
    skill_scores, level_scores = defaultdict(list), defaultdict(list)
    skill_errors = defaultdict(Counter)
    for run in runs:
        if not run.report:
            continue
        level_scores[run.level_id].append(float(run.report.get('score', 0)))
        question_skills = {q['id']: q.get('skill_id') for q in (run.questions or [])}
        run_scores = defaultdict(list)
        for answer in run.report.get('results', []):
            sid = question_skills.get(answer.get('question_id'))
            if not sid:
                continue
            run_scores[sid].append(float(answer.get('score', 0)))
            if answer.get('error_type') and len(skill_scores[sid]) < 3:
                skill_errors[sid][answer['error_type']] += 1
        for sid, scores in run_scores.items():
            skill_scores[sid].append(sum(scores) / len(scores))

    diagnosis = _diagnosis(user)
    states = []
    for a in ABILITIES:
        lv = levels(a['id'])
        metrics = []
        for index, name in enumerate(a['skills'], 1):
            sid = f'{a["id"]}-S{index}'
            observed = skill_scores[sid]
            entry = next((e for e in diagnosis[a['id']] if e.get('skill_id') == sid), None)
            # Old onboarding records only supplied ability_id; assign their evidence
            # to S1 instead of pretending that one question assessed every skill.
            if entry is None and index == 1:
                entry = next((e for e in diagnosis[a['id']] if not e.get('skill_id')), None)
            if observed:
                value, source = _recent_average(observed), 'training'
            elif entry:
                value, source = (60 if entry['correct'] else 20), 'diagnostic'
            else:
                matching = [done[l['id']] for l in lv if l['mode'] == 'course' and l['skill_id'] == sid and l['id'] in done]
                value, source = (max(matching), 'record') if matching else (0, 'unassessed')
            metrics.append({'skill_id': sid, 'name': name, 'score': round(value),
                            'source': source, 'assessed': source != 'unassessed',
                            'recent_errors': [key for key, _ in skill_errors[sid].most_common(3)]})
        level_states = []
        for index, level in enumerate(lv):
            measured = level_scores[level['id']]
            level_states.append(dict(level,
                unlocked=index == 0 or all(p['id'] in done for p in lv[:index]),
                completed=level['id'] in done,
                score=round(_recent_average(measured)) if measured else done.get(level['id'], 0),
                best_score=done.get(level['id'], 0)))
        diag = diagnosis[a['id']]
        states.append(dict(a, mastery=round(sum(s['score'] for s in metrics) / max(1, len(metrics))),
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
        # A brief diagnostic changes the starting recommendation, but never unlocks
        # a level or asserts mastery of skills that have not been assessed.
        blocked = sum(byid[p]['mastery'] < 40 and (byid[p].get('diagnostic_score') or 0) < 70
                      for p in a.get('prerequisites', []) if p in byid)
        diagnosed_weak = .28 if a.get('diagnostic_score') is not None and a['diagnostic_score'] < 60 and not a['completed'] else 0
        mode = selected_levels[a['id']]['mode']
        goal_fit = .16 if goal == '竞赛备战' and mode == 'competition' else .10 if goal == '岗位入门' and mode == 'job' else .06 if goal == '课程补强' and mode == 'course' else 0
        return .35 * upstream + .45 * deficit - .55 * blocked + diagnosed_weak + goal_fit

    a = max(candidates, key=weight)
    level = selected_levels[a['id']]
    if level['completed'] and level['score'] < 60:
        reason = f'最近训练显示「{level["name"]}」得分为 {level["score"]}%，建议先复习这个薄弱环节。'
    elif a.get('diagnostic_score') is not None and a['diagnostic_score'] < 60 and not a['completed']:
        reason = f'入门诊断发现你在{a["name"]}上需要补强，先完成「{level["name"]}」。'
    else:
        reason = f'结合「{goal}」目标与技能前置关系，建议学习「{level["name"]}」。当前掌握度 {a["mastery"]}%。'
    path = [level] + [l for l in a['levels'] if l['id'] != level['id'] and not l['completed']]
    return {'ability_id': a['id'], 'ability_name': a['name'], 'level': level, 'mastery': a['mastery'],
            'reason': reason, 'path': [{'id': l['id'], 'name': l['name'], 'mode': l['mode'], 'unlocked': l['unlocked']} for l in path[:4]]}


def learner_context(user, states, aid=None, skill=None):
    rec = recommendation(states, user.goal)
    state = next(a for a in states if a['id'] == (aid or rec['ability_id']))
    current_skill = skill or _next_level(state, user.goal)['skill_id']
    metric = next((s for s in state.get('skill_mastery', []) if s['skill_id'] == current_skill), None)
    return {'goal': user.goal, 'ability_id': state['id'], 'ability_name': state['name'],
            'skill_id': current_skill, 'skill_name': metric['name'] if metric else None,
            'mastery': metric['score'] if metric else state['mastery'],
            'recent_errors': state.get('recent_errors', []),
            'weak_skills': [s for s in state.get('skill_mastery', []) if s['assessed'] and s['score'] < 65],
            'completed_levels': [l['name'] for l in state['levels'] if l['completed']],
            'next_learning': rec['level']['name'], 'recommendation_reason': rec['reason'],
            'learning_path': rec['path'], 'diagnostic': user.diagnostic}
