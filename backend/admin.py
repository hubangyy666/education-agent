import re
import uuid
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from . import tutor
from .catalog import ABILITIES
from .db import (
    JobLearning,
    Knowledge,
    KnowledgeBase,
    Progress,
    Run,
    TaskCard,
    User,
    cache,
    get_db,
    password_hash,
)


GENERAL_PURPOSE = '回答数据标注基础概念、通用流程、数据合规与跨能力共通知识。'
ABILITY_PURPOSES = {
    'A1': '支撑标注基础认知、岗位术语和基本任务流程学习。',
    'A2': '支撑标注规范阅读、标签体系和项目规则理解。',
    'A3': '支撑分类标签、属性判断和类别映射训练。',
    'A4': '支撑目标检测、矩形框选、边界控制和多目标标注。',
    'A5': '支撑多边形、掩码、轮廓与精细分割知识学习。',
    'A6': '支撑工业表面缺陷、正常异常样本和缺陷定位训练。',
    'A7': '支撑遮挡、跟踪、复杂视觉场景和多实例处理。',
    'A8': '支撑文本分类、实体边界、意图与语义标注。',
    'A9': '支撑 AI 协同标注、质量审核、问题记录与返修。',
    'A10': '支撑数据导出、质量证据、项目验收与交付归档。',
}


class AccountBody(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r'^[A-Za-z0-9_]+$')
    name: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=6, max_length=128)
    role: Literal['student', 'admin'] = 'student'


class KnowledgeBaseBody(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    purpose: str = Field(min_length=5, max_length=300)
    scope: str = Field(default='GENERAL', max_length=10)
    content: str = Field(min_length=20, max_length=20000)


def _admin_user(current_user):
    def dependency(user: User = Depends(current_user)):
        if user.role != 'admin':
            raise HTTPException(403, '只有管理者可以访问后台管理端。')
        return user
    return dependency


def _account(user: User):
    return {
        'username': user.username,
        'name': user.name,
        'role': user.role,
        'onboarding': user.onboarding,
        'created_at': user.created_at,
    }


def _chunks(content: str):
    paragraphs = [part.strip() for part in re.split(r'\n\s*\n|\r?\n', content) if part.strip()]
    chunks = []
    current = ''
    for paragraph in paragraphs:
        pieces = [paragraph[i:i + 400] for i in range(0, len(paragraph), 400)]
        for piece in pieces:
            candidate = piece if not current else current + '\n' + piece
            if len(candidate) <= 400:
                current = candidate
            else:
                chunks.append(current)
                current = piece
    if current:
        chunks.append(current)
    return chunks


def register_admin(app, current_user):
    require_admin = _admin_user(current_user)

    @app.get('/api/admin/users')
    def list_users(admin: User = Depends(require_admin), db=Depends(get_db)):
        del admin
        users = list(db.scalars(select(User).order_by(User.role.desc(), User.created_at, User.username)))
        return [_account(user) for user in users]

    @app.post('/api/admin/users')
    def create_user(body: AccountBody, admin: User = Depends(require_admin), db=Depends(get_db)):
        del admin
        if db.get(User, body.username):
            raise HTTPException(409, '该用户名已存在。')
        user = User(
            username=body.username,
            name=body.name,
            password=password_hash(body.password),
            role=body.role,
            onboarding=body.role == 'admin',
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return _account(user)

    @app.delete('/api/admin/users/{username}')
    def remove_user(username: str, admin: User = Depends(require_admin), db=Depends(get_db)):
        if username == admin.username:
            raise HTTPException(409, '不能删除当前正在使用的管理者账号。')
        user = db.get(User, username)
        if not user:
            raise HTTPException(404, '没有找到该账号。')
        for model in (JobLearning, TaskCard, Progress, Run):
            db.execute(delete(model).where(model.username == username))
        db.delete(user)
        db.commit()
        for key in cache.scan_iter(match='session:*'):
            if cache.get(key) == username:
                cache.delete(key)
        return {'ok': True, 'username': username}

    @app.get('/api/admin/knowledge-bases')
    def list_knowledge_bases(admin: User = Depends(require_admin), db=Depends(get_db)):
        del admin
        grouped = {
            (scope if scope == 'GENERAL' else ability_id): count
            for scope, ability_id, count in db.execute(
                select(Knowledge.scope, Knowledge.ability_id, func.count())
                .where(~Knowledge.id.like('KB-ADMIN-%'))
                .group_by(Knowledge.scope, Knowledge.ability_id)
            )
        }
        ability_names = {item['id']: item['name'] for item in ABILITIES}
        built_in = [{
            'id': 'builtin-GENERAL',
            'name': '通用岗位知识库',
            'purpose': GENERAL_PURPOSE,
            'scope': 'GENERAL',
            'scope_name': '通用知识',
            'knowledge_count': grouped.get('GENERAL', 0),
            'source': '原知识库拆分',
            'active': True,
        }]
        built_in.extend({
            'id': f'builtin-{ability_id}',
            'name': f'{ability_id} · {ability_names[ability_id]}知识库',
            'purpose': ABILITY_PURPOSES[ability_id],
            'scope': ability_id,
            'scope_name': ability_names[ability_id],
            'knowledge_count': grouped.get(ability_id, 0),
            'source': '原知识库拆分',
            'active': True,
        } for ability_id in ABILITY_PURPOSES)
        custom = [{
            'id': base.id,
            'name': base.name,
            'purpose': base.purpose,
            'scope': base.scope,
            'scope_name': '通用知识' if base.scope == 'GENERAL' else ability_names.get(base.scope, base.scope),
            'knowledge_count': len(base.knowledge_ids or []),
            'source': '管理者新增',
            'active': True,
            'created_by': base.created_by,
            'created_at': base.created_at,
        } for base in db.scalars(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))]
        return {'built_in': built_in, 'custom': custom, 'scope_options': [
            {'value': 'GENERAL', 'label': '通用知识', 'purpose': GENERAL_PURPOSE},
            *({'value': item['id'], 'label': f"{item['id']} · {item['name']}", 'purpose': ABILITY_PURPOSES[item['id']]}
              for item in ABILITIES),
        ]}

    @app.post('/api/admin/knowledge-bases')
    def create_knowledge_base(body: KnowledgeBaseBody, admin: User = Depends(require_admin), db=Depends(get_db)):
        valid_scopes = {'GENERAL', *ABILITY_PURPOSES}
        if body.scope not in valid_scopes:
            raise HTTPException(422, '请选择有效的知识适用范围。')
        chunks = _chunks(body.content)
        try:
            embeddings = [tutor.embed(f'{body.name} {body.purpose} {chunk}') for chunk in chunks]
        except Exception as exc:
            raise HTTPException(503, '知识向量生成失败，本次没有保存，请稍后重试。') from exc
        base_id = str(uuid.uuid4())
        knowledge_ids = [f'KB-ADMIN-{base_id}-{index + 1}' for index in range(len(chunks))]
        base = KnowledgeBase(
            id=base_id,
            name=body.name,
            purpose=body.purpose,
            scope=body.scope,
            ability_id=None if body.scope == 'GENERAL' else body.scope,
            content=body.content,
            knowledge_ids=knowledge_ids,
            created_by=admin.username,
        )
        db.add(base)
        for index, (knowledge_id, chunk, embedding) in enumerate(zip(knowledge_ids, chunks, embeddings), start=1):
            db.add(Knowledge(
                id=knowledge_id,
                title=body.name if len(chunks) == 1 else f'{body.name}（{index}/{len(chunks)}）',
                content=chunk,
                scope='GENERAL' if body.scope == 'GENERAL' else 'ABILITY',
                ability_id=None if body.scope == 'GENERAL' else body.scope,
                skill_id=None,
                meta={
                    'source_name': body.name,
                    'source_type': '管理者维护知识库',
                    'knowledge_base_id': base_id,
                    'purpose': body.purpose,
                    'managed_by_admin': True,
                    'created_by': admin.username,
                },
                embedding=embedding,
            ))
        db.commit()
        return {
            'id': base.id,
            'name': base.name,
            'purpose': base.purpose,
            'scope': base.scope,
            'knowledge_count': len(knowledge_ids),
            'source': '管理者新增',
            'active': True,
            'created_by': base.created_by,
            'created_at': base.created_at,
        }
