"""Disposable browser QA identity; never modifies the four learner accounts."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import delete
from sqlalchemy.orm import Session
from backend.db import User,Run,Progress,TaskCard,engine,cache,password_hash
username='qa_browser_primary'
with Session(engine) as db:
    if len(sys.argv)>1 and sys.argv[1]=='cleanup':
        for cls in (Run,Progress,TaskCard): db.execute(delete(cls).where(cls.username==username))
        db.execute(delete(User).where(User.username==username));db.commit()
        for key in cache.scan_iter('session:*'):
            if cache.get(key)==username: cache.delete(key)
        print('已清理临时浏览器验收账号及其测试记录。')
    elif not db.get(User,username):
        db.add(User(username=username,name='验收同学',password=password_hash('ZhijiBrowser!2026')));db.commit();print('已创建独立浏览器验收账号。')
