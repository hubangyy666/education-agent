from pathlib import Path
import os
import hashlib
import secrets
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, String, JSON, Integer, Float, DateTime, ForeignKey, Text, Boolean, text
from sqlalchemy.orm import DeclarativeBase, mapped_column, Session
from pgvector.sqlalchemy import Vector
import redis
from minio import Minio

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
engine = create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True)
cache = redis.Redis.from_url(os.environ['REDIS_URL'], decode_responses=True, socket_connect_timeout=3)
storage = Minio(os.environ['MINIO_ENDPOINT'], access_key=os.environ['MINIO_ACCESS_KEY'], secret_key=os.environ['MINIO_PASSWORD'], secure=False)
def now(): return datetime.now(timezone.utc)

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    username = mapped_column(String(40), primary_key=True)
    password = mapped_column(Text)
    name = mapped_column(String(40))
    onboarding = mapped_column(Boolean, default=False)
    goal = mapped_column(String(30), default='岗位入门')
    daily_goal = mapped_column(Integer, default=10)
    voice = mapped_column(Boolean, default=True)
    diagnostic = mapped_column(JSON, default=dict)
    created_at = mapped_column(DateTime(timezone=True), default=now)
class Run(Base):
    __tablename__ = 'runs'
    id = mapped_column(String(40), primary_key=True)
    username = mapped_column(ForeignKey('users.username'), index=True)
    ability_id = mapped_column(String(10))
    level_id = mapped_column(String(30))
    mode = mapped_column(String(20))
    status = mapped_column(String(20), default='active')
    questions = mapped_column(JSON)
    answers = mapped_column(JSON, default=dict)
    hints = mapped_column(JSON, default=dict)
    report = mapped_column(JSON, nullable=True)
    started_at = mapped_column(DateTime(timezone=True), default=now)
    deadline = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at = mapped_column(DateTime(timezone=True), nullable=True)
    revision_of = mapped_column(String(40), nullable=True)
class Progress(Base):
    __tablename__ = 'progress'
    id = mapped_column(String(100), primary_key=True)
    username = mapped_column(ForeignKey('users.username'), index=True)
    ability_id = mapped_column(String(10))
    level_id = mapped_column(String(30))
    score = mapped_column(Float, default=0)
    attempts = mapped_column(Integer, default=1)
    completed_at = mapped_column(DateTime(timezone=True), default=now)
class QuestionSet(Base):
    __tablename__ = 'question_sets'
    id = mapped_column(String(60), primary_key=True)
    ability_id = mapped_column(String(10), index=True)
    version = mapped_column(Integer)
    questions = mapped_column(JSON)
    active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime(timezone=True), default=now)
class Knowledge(Base):
    __tablename__ = 'knowledge'
    id = mapped_column(String(80), primary_key=True)
    title = mapped_column(Text)
    content = mapped_column(Text)
    scope = mapped_column(String(30))
    ability_id = mapped_column(String(10), nullable=True)
    skill_id = mapped_column(String(30), nullable=True)
    meta = mapped_column(JSON)
    embedding = mapped_column(Vector(1024))
class TaskCard(Base):
    __tablename__ = 'task_cards'
    id = mapped_column(String(40), primary_key=True)
    username = mapped_column(ForeignKey('users.username'))
    content = mapped_column(JSON)
    created_at = mapped_column(DateTime(timezone=True), default=now)

class JobLearning(Base):
    """One persisted teaching conversion per learner and catalog task.

    The deterministic UUID id also makes concurrent generate requests idempotent.
    Training runs use a separate JT level namespace, preserving skill-map gates.
    """
    __tablename__ = 'job_learning'
    id = mapped_column(String(40), primary_key=True)
    username = mapped_column(ForeignKey('users.username'), index=True)
    role_id = mapped_column(String(40), index=True)
    task_id = mapped_column(String(80))
    goal = mapped_column(String(30), default='岗位入门')
    status = mapped_column(String(20), default='active')
    card = mapped_column(JSON)
    progress = mapped_column(JSON, default=dict)
    sources = mapped_column(JSON, default=list)
    created_at = mapped_column(DateTime(timezone=True), default=now)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def password_valid(password, encoded):
    return secrets.compare_digest(password_hash(password,encoded.split(':')[0]), encoded)
def init_db():
    with engine.begin() as conn: conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for username,name in [('xuyihao','徐一豪'),('zhangxiang','张翔'),('songsang','宋桑'),('mengfei','孟飞')]:
            if not db.get(User,username): db.add(User(username=username,name=name,password=password_hash('123456')))
        db.commit()
    cache.ping()
    if not storage.bucket_exists('zhiji-training'): storage.make_bucket('zhiji-training')
def get_db():
    with Session(engine) as db: yield db
