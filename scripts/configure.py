"""One-time local configuration. Never prints the supplied model credential."""
from pathlib import Path
import secrets
import re

root = Path(__file__).resolve().parents[1]
env = root / '.env'
if env.exists():
    print('本地配置已存在，保留原配置。')
else:
    source_path=root / '模型配置.md'
    source = source_path.read_text(encoding='utf-8') if source_path.exists() else ''
    match = re.search(r'sk-[A-Za-z0-9_-]+', source)
    password = secrets.token_hex(24)
    minio_password = secrets.token_hex(24)
    config = (root / '.env.example').read_text(encoding='utf-8')
    config = config.replace('replace-with-a-long-random-password', password, 2)
    config = config.replace('replace-with-a-long-random-password', minio_password)
    config = config.replace('DEEPSEEK_API_KEY=\n', f'DEEPSEEK_API_KEY={match.group(0) if match else ""}\n')
    env.write_text(config, encoding='utf-8')
    print('已生成服务端环境配置；密钥不会写入前端。')
