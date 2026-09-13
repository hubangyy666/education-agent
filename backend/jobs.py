"""Fixed, source-grounded job lessons with persisted training evidence. No model calls."""
import copy
import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .catalog import ability, levels
from .db import ROOT, JobLearning, QuestionSet, Run, User, cache, get_db, now
from .grading import grade, report


# Individually checked teaching choices for the quality-report task. A source-
# approved reserve can still contain ambiguous questions; this task deliberately
# excludes the optional-checksum and empty-YOLO-label-file ambiguities and avoids
# repeating the same coordinate-unit question with different wording.
QUALITY_REPORT_QUESTIONS = (
    'QF-666ac7bfe112f6efcedb1a9b',  # coordinate units versus the receiver's requirement
    'QF-fd2d8f14b35e86adfc4e6827',  # training export versus editable project backup
    'QF-4a6c2fac209cc4945d658c49',  # validation subset versus all-image inspection
    'QF-6c4cfb5f4d56f19b574220ae',  # record a located issue and its actual status
    'QF-d3c373a4f2b472c3b0501c42',  # score, repair permission, final acceptance
)


class EvidenceBody(BaseModel):
    evidence: str = Field(min_length=1, max_length=4000)
    run_id: str | None = Field(default=None, max_length=40)


def read_catalog():
    try:
        with (ROOT / 'data' / 'job-catalog.json').open(encoding='utf-8') as handle:
            catalog = json.load(handle)
    except (OSError, ValueError):
        raise HTTPException(503, '岗位资料暂未就绪，请稍后重试。') from None
    return catalog


def catalog_role(catalog, role_id):
    role = next((r for r in catalog['roles'] if r['id'] == role_id), None)
    if role is None:
        raise HTTPException(404, '没有找到这个岗位。')
    return role


def catalog_task(role, task_id):
    task = next((t for t in role['tasks'] if t['id'] == task_id), None)
    if task is None:
        raise HTTPException(404, '没有找到这个岗位的典型任务。')
    return task


def referenced_sources(catalog, role, task=None):
    ids = set(role['source_ids'])
    for major in role.get('majors', []):
        ids.update(major.get('source_ids', []))
    for item in ([task] if task else role['tasks']):
        ids.update(item['source_ids'])
        for knowledge in item.get('knowledge', []):
            ids.update(knowledge.get('source_ids', []))
    return [copy.deepcopy(source) for source in catalog['sources'] if source['id'] in ids]


def learning_dict(learning):
    steps = learning.card['steps']
    completed = sum(bool((learning.progress or {}).get(step['id'], {}).get('completed')) for step in steps)
    return {'id': learning.id, 'role_id': learning.role_id, 'task_id': learning.task_id,
            'goal': learning.goal, 'status': learning.status, 'card': learning.card,
            'progress': learning.progress or {}, 'sources': learning.sources,
            'created_at': learning.created_at, 'completed_at': learning.completed_at,
            'percent': round(100 * completed / len(steps)) if steps else 0}


def training_context(run):
    """Recover the parent task even when a Run is opened without route query data."""
    if not run.level_id.startswith('JT-'):
        return None
    from .db import engine
    with Session(engine) as db:
        learnings = db.scalars(select(JobLearning).where(JobLearning.username == run.username))
        for learning in learnings:
            for step in learning.card['steps']:
                # Failed attempts remain in the task's history after a retry has
                # replaced progress.run_id. The namespaced level still identifies
                # their parent, but cannot be reused as new completion evidence.
                if step['kind'] == 'practice' and run.level_id == job_level(learning, step):
                    return {'learning_id': learning.id, 'role_id': learning.role_id,
                            'task_id': learning.task_id, 'step_id': step['id'], 'title': learning.card['name']}
    return None


def role_with_progress(role, learnings):
    result = copy.deepcopy(role)
    listed_tasks = {task['id'] for task in role['tasks']}
    relevant = {item.task_id: item for item in learnings
                if item.role_id == role['id'] and item.task_id in listed_tasks}
    for task in result['tasks']:
        learning = relevant.get(task['id'])
        task['learning_id'] = learning.id if learning else None
        task['status'] = learning.status if learning else 'not_started'
        task['percent'] = learning_dict(learning)['percent'] if learning else 0
    finished = sum(item.status == 'completed' for item in relevant.values())
    result['progress'] = {'learning_count': len(relevant), 'completed_tasks': finished,
                          'total_tasks': len(role['tasks']),
                          'percent': round(100 * finished / len(role['tasks'])) if role['tasks'] else 0}
    return result


def _skill(item):
    a = ability(item['ability_id'])
    lv = next((level for level in levels(item['ability_id']) if level['skill_id'] == item['skill_id']), None)
    if not a or not lv:
        raise ValueError('岗位任务的知识技能映射无效')
    return {**item, 'title': lv['name'], 'ability_name': a['name'],
            'url': f'/skills/{a["id"]}', 'level_id': lv['id']}


def template_card(catalog, role, task):
    skills = [_skill(copy.deepcopy(item)) for item in task['skills']]
    knowledge = [{**copy.deepcopy(item), 'url': f'/skills/{item["ability_id"]}'} for item in task['knowledge']]
    for item in knowledge:
        _skill(item)  # validate the catalog mapping without changing its authored title
    steps = copy.deepcopy(task['steps'])
    for step in steps:
        step['mandatory_instruction'] = step['instruction']
        step['mandatory_output'] = step['output']
        if step['kind'] == 'practice':
            aid = step['level_id'].split('-')[0]
            if not any(level['id'] == step['level_id'] and level['mode'] == 'course' for level in levels(aid)):
                raise ValueError('岗位任务必须关联可执行的课程训练')
    sources = referenced_sources(catalog, role, task)
    resources = [{'title': item['ability_name'] + ' · ' + item['title'], 'url': item['url'],
                  'kind': 'training', 'skill_id': item['skill_id']} for item in skills]
    resources += [{'title': item['title'], 'url': item['url'], 'kind': 'source'} for item in sources]
    return {'name': task['title'], 'scenario': task['work_scenario'],
            'description': task['description'], 'objectives': copy.deepcopy(task['objectives']),
            'task_description': task['description'], 'work_scenario': task['work_scenario'],
            'mandatory_objectives': copy.deepcopy(task['objectives']),
            'deliverables': copy.deepcopy(task['deliverables']), 'steps': steps,
            'norms': copy.deepcopy(task['norms']), 'quality': copy.deepcopy(task['quality']),
            'assessment': copy.deepcopy(task['assessment']), 'knowledge': knowledge, 'skills': skills,
            'resources': resources, 'source_ids': [s['id'] for s in sources],
            'industry': role['industry'], 'role_title': role['title'], 'majors': copy.deepcopy(role['majors']),
            'duration_minutes': task['duration_minutes'], 'difficulty': task['difficulty'],
            'provider': 'fixed', 'ai_generated': False,
            'notice': '固定岗位任务讲解，内容依据公开岗位资料与专业教学标准编写。',
            'analysis': {'catalog_version': catalog['version'], 'industry': role['industry'],
                         'role': role['title'], 'majors': copy.deepcopy(role['majors']),
                         'work_task': task['title'],
                         'method': '产业应用 → 岗位职责 → 典型任务 → 教学步骤 → 知识技能 → 实操证据'}}


def get_learning(learning_id, user, db, lock=False):
    statement = select(JobLearning).where(JobLearning.id == learning_id, JobLearning.username == user.username)
    if lock:
        statement = statement.with_for_update()
    learning = db.scalar(statement)
    if learning is None:
        raise HTTPException(404, '没有找到你的岗位学习任务。')
    return learning


def current_step(learning, step_id):
    steps = learning.card['steps']
    index = next((i for i, step in enumerate(steps) if step['id'] == step_id), None)
    if index is None:
        raise HTTPException(404, '没有找到这个教学步骤。')
    if any(not (learning.progress or {}).get(step['id'], {}).get('completed') for step in steps[:index]):
        raise HTTPException(409, '请先完成前面的教学步骤，并提交学习证据。')
    return steps[index]


def job_level(learning, step):
    # UUID + step index avoids collisions and stays within Run.level_id String(30).
    index = next(i for i, item in enumerate(learning.card['steps']) if item['id'] == step['id'])
    return f'JT-{learning.id.replace("-", "")[:22]}-{index}'


def evidence_text(value):
    compact = re.sub(r'\s', '', value)
    meaningful = re.sub(r'[^\w\u4e00-\u9fff]', '', compact)
    if len(meaningful) < 15 or len(set(meaningful)) < 7:
        raise HTTPException(422, '请至少用 15 个字写出你的理解、操作记录或复盘，避免只填写“已完成”或重复字符。')
    return value.strip()


def training_questions(step, db):
    """Select only exercises matching the task, retaining original provenance."""
    level_id = step['level_id']
    aid = level_id.split('-')[0]
    level = next(item for item in levels(aid) if item['id'] == level_id)
    skill_id = step.get('skill_id', level['skill_id'])
    if skill_id != level['skill_id']:
        raise HTTPException(503, '教学任务的技能与训练关卡映射不一致。')
    source = step.get('question_source', 'active_set')
    if source == 'visual_reserve':
        from .visual_reserve import visual_questions
        candidates = [q for q in visual_questions(aid)
                      if q['skill_id'] == skill_id and not q.get('curriculum_fallback')]
        if step.get('target_labels'):
            candidates = [q for q in candidates if q['type'] == 'box' and
                          all(target['label'] in step['target_labels'] for target in q['answer'])]
        # Classification includes negative industrial examples; NER spans more than
        # one label. Neither sampling nor ordering changes the source annotations.
        if aid == 'A6' and skill_id == 'A6-S4':
            candidates.sort(key=lambda q: (q['answer'] != '无可见缺陷', q['id']))
        elif aid == 'A8':
            by_label = {}
            for question in candidates:
                by_label.setdefault(question['answer']['label'], []).append(question)
            candidates = [items[index] for index in range(max(map(len, by_label.values()), default=0))
                          for items in by_label.values() if index < len(items)]
    elif source == 'reviewed_reserve':
        from .factory_agent import Store, approve_review, validate_question
        candidates = []
        for question in Store(ROOT / 'data/factory').questions(aid):
            if question.get('skill_id') != skill_id or question.get('status') != 'approved':
                continue
            try:
                validate_question(question, skill_id, question.get('evidence', []))
                if approve_review(question, question.get('ai_review', {})):
                    candidates.append(question)
            except (ValueError, KeyError, TypeError):
                continue
        if skill_id == 'A10-S4':
            approved = {question['id']: question for question in candidates}
            candidates = [approved[question_id] for question_id in QUALITY_REPORT_QUESTIONS
                          if question_id in approved]
    elif source == 'active_set':
        pool = db.scalar(select(QuestionSet).where(QuestionSet.ability_id == aid, QuestionSet.active.is_(True)))
        candidates = (pool.questions or {}).get(level_id, []) if pool else []
        candidates = [q for q in candidates if q.get('skill_id') == skill_id]
    else:
        raise HTTPException(503, '教学任务的训练来源尚未配置。')
    questions = copy.deepcopy(candidates[:5])
    if len(questions) < 5 or len({q['id'] for q in questions}) < 5:
        raise HTTPException(503, '对应技能的合格训练样本不足 5 题，请稍后重试。')
    for question in questions:
        if aid == 'A6' and skill_id == 'A6-S4' and question['type'] == 'choice':
            # Classification evaluates existence, so box/polygon feedback from the
            # shared image adapter would teach the wrong operation. Only change
            # the task snapshot's explanation, never its source answer or grader.
            question['explanation'] = ('本题判断是否存在可见表面缺陷。参考类别由官方二元掩码是否含缺陷像素确定：'
                                       '有缺陷像素对应“存在表面缺陷”，无缺陷像素对应“无可见缺陷”。'
                                       '本练习不要求画框或描轮廓，也不区分裂纹、划痕等缺陷子类别。')
            question['hint'] = ['先从上到下观察整张表面图，判断是否存在与周围表面不同的可见异常。',
                                '放大检查可疑区域，并与周围纹理比较；本题只需判断异常是否存在。',
                                '重新检查整张图是否有可见异常，按本题二元标签选择，不需要框选或推断缺陷子类别。']
        expected = question['answer']
        golden = ({'boxes': expected} if question['type'] == 'box' else
                  {'points': expected['polygon'], 'label': expected['label']} if question['type'] == 'polygon' else
                  expected if question['type'] == 'entity' else {'value': expected})
        result = grade(question, golden)
        if not result['correct'] or result['score'] != 100:
            raise HTTPException(503, '训练样本未通过标准答案判分校验，请稍后重试。')
    return questions


def register_jobs(app, current_user):
    router = APIRouter()

    @router.get('/api/jobs')
    def list_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
        catalog = read_catalog()
        learnings = list(db.scalars(select(JobLearning).where(JobLearning.username == user.username)))
        return {'roles': [role_with_progress(role, learnings) for role in catalog['roles']],
                'sources': catalog['sources'], 'version': catalog['version']}

    @router.get('/api/jobs/{role_id}')
    def read_job(role_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        catalog = read_catalog()
        role = catalog_role(catalog, role_id)
        learnings = list(db.scalars(select(JobLearning).where(JobLearning.username == user.username,
                                                            JobLearning.role_id == role_id)))
        return {'role': role_with_progress(role, learnings), 'sources': referenced_sources(catalog, role),
                'version': catalog['version']}

    @router.get('/api/jobs/{role_id}/tasks/{task_id}')
    def read_task(role_id: str, task_id: str,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
        catalog = read_catalog()
        role = catalog_role(catalog, role_id)
        task = catalog_task(role, task_id)
        learning = db.scalar(select(JobLearning).where(JobLearning.username == user.username,
                            JobLearning.role_id == role_id, JobLearning.task_id == task_id))
        return {'role': {key: role[key] for key in ('id', 'title', 'color', 'industry', 'majors')},
                'task': {**copy.deepcopy(task), **template_card(catalog, role, task)},
                'learning': learning_dict(learning) if learning else None,
                'sources': referenced_sources(catalog, role, task), 'version': catalog['version']}

    @router.post('/api/jobs/{role_id}/tasks/{task_id}/enroll')
    def enroll_job(role_id: str, task_id: str,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
        catalog = read_catalog()
        role = catalog_role(catalog, role_id)
        task = catalog_task(role, task_id)
        learning_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'zhiji:jobs:{user.username}:{role_id}:{task_id}'))
        existing = db.get(JobLearning, learning_id)
        if existing:
            return learning_dict(existing)
        card = template_card(catalog, role, task)
        sources = referenced_sources(catalog, role, task)
        learning = JobLearning(id=learning_id, username=user.username, role_id=role_id, task_id=task_id,
                               goal='岗位学习', status='active', card=card, progress={}, sources=sources)
        db.add(learning)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.get(JobLearning, learning_id)
            if existing is None:
                raise
            learning = existing
        return learning_dict(learning)

    @router.get('/api/job-learning/{learning_id}')
    def read_learning(learning_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return learning_dict(get_learning(learning_id, user, db))

    @router.post('/api/job-learning/{learning_id}/steps/{step_id}/start')
    def start_step(learning_id: str, step_id: str,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
        learning = get_learning(learning_id, user, db, lock=True)
        step = current_step(learning, step_id)
        if step['kind'] != 'practice':
            raise HTTPException(400, '这个步骤需要阅读和记录，请在实操步骤中开始训练。')
        previous = (learning.progress or {}).get(step_id, {})
        if previous.get('run_id'):
            run = db.get(Run, previous['run_id'])
            if (run and run.username == user.username and run.level_id == job_level(learning, step)
                    and run.mode == 'course' and run.ability_id == step['level_id'].split('-')[0]):
                if run.status == 'active':
                    return {'id': run.id}
                if (run.status == 'completed' and run.finished_at and (run.report or {}).get('passed')
                        and len(run.answers or {}) == len(run.questions) and report(run.questions, run.answers)['passed']):
                    return {'id': run.id}
        if previous.get('completed'):
            raise HTTPException(409, '本步骤已经完成。')
        level_id = step['level_id']
        aid = level_id.split('-')[0]
        if cache.exists(f'factory-lock:{aid}'):
            raise HTTPException(409, '该能力题目正在更新，请等待新题集发布。')
        try:
            questions = training_questions(step, db)
        except (OSError, ValueError, KeyError, StopIteration):
            raise HTTPException(503, '关联训练样本暂未通过完整性校验，请稍后重试；本步骤进度已保留。') from None
        run = Run(id=str(uuid.uuid4()), username=user.username, ability_id=aid,
                  level_id=job_level(learning, step), mode='course', questions=copy.deepcopy(questions))
        db.add(run)
        learning.progress = {**(learning.progress or {}), step_id: {**previous, 'completed': False,
                             'run_id': run.id, 'started_at': now().isoformat(), 'training_level_id': level_id}}
        db.commit()
        return {'id': run.id}

    @router.post('/api/job-learning/{learning_id}/steps/{step_id}')
    def complete_step(learning_id: str, step_id: str, body: EvidenceBody,
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
        learning = get_learning(learning_id, user, db, lock=True)
        step = current_step(learning, step_id)
        previous = (learning.progress or {}).get(step_id, {})
        if previous.get('completed'):
            return learning_dict(learning)
        evidence = evidence_text(body.evidence)
        progress = {**previous, 'completed': True, 'evidence': evidence, 'completed_at': now().isoformat()}
        if step['kind'] == 'practice':
            if not body.run_id or body.run_id != previous.get('run_id'):
                raise HTTPException(422, '请先从本步骤开始训练，并提交对应的真实训练记录。')
            run = db.scalar(select(Run).where(Run.id == body.run_id, Run.username == user.username).with_for_update())
            if (not run or run.level_id != job_level(learning, step) or
                    run.ability_id != step['level_id'].split('-')[0] or run.mode != 'course'):
                raise HTTPException(422, '训练记录不属于本人的这个岗位教学步骤。')
            if run.status != 'completed' or not run.finished_at or not (run.report or {}).get('passed'):
                raise HTTPException(409, '请完成全部关联训练并达到本训练的试标要求，再提交实操证据。')
            actual = report(run.questions, run.answers or {})
            if len(run.answers or {}) != len(run.questions) or not actual['passed']:
                raise HTTPException(409, '真实作答尚未达到本训练的试标要求，请重新训练。')
            progress.update(run_id=run.id, score=actual['score'], criteria=actual['criteria'],
                            count=actual['count'], passed=True)
        learning.progress = {**(learning.progress or {}), step_id: progress}
        if all(learning.progress.get(item['id'], {}).get('completed') for item in learning.card['steps']):
            learning.status = 'completed'
            learning.completed_at = now()
        db.commit()
        return learning_dict(learning)

    app.include_router(router)
