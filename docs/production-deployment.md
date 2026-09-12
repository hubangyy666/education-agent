# Linux ECS 生产部署

本文适用于已安装 Docker Engine 与 Docker Compose V2 的 Linux ECS。生产编排只向公网开放 Caddy 的 80/443 端口，PostgreSQL、Redis、MinIO 和 FastAPI 均留在 Docker 内网。

## 1. 安全组

- TCP 22：只允许管理员当前公网 IP。
- TCP 80、443：允许 `0.0.0.0/0`。
- 不要向公网开放 8000、5432、6379、9000、9001。

## 2. 准备生产环境变量

进入服务器仓库：

```bash
cd /opt/zhiji
cp .env.production.example .env.production
vi .env.production
```

首次使用公网 IP 验证时，把下面两项中的地址换成 ECS 公网 IP：

```dotenv
SITE_ADDRESS=http://你的公网IP
PUBLIC_ORIGIN=http://你的公网IP
COOKIE_SECURE=false
```

必须替换所有 `replace-with-...`。可以多次执行 `openssl rand -hex 32` 生成互不相同的随机值。竞赛体验账号和管理员密码也必须不同，不能使用 `123456`。如需模型功能，再填写 `DEEPSEEK_API_KEY`；不要把 `.env.production` 提交到 Git。

## 3. 启动

```bash
cd /opt/zhiji
chmod +x deploy.sh
./deploy.sh
```

首次构建和拉取镜像需要几分钟。生产配置通过 DaoCloud 国内镜像代理拉取 Docker Hub 与 Quay 镜像，以降低中国内地 ECS 直接访问海外仓库超时的概率。完成后检查：

```bash
docker compose --env-file .env.production -f compose.production.yaml ps
curl -i http://127.0.0.1/api/health
```

所有服务应为 `Up`，带健康检查的服务应显示 `healthy`，健康接口应返回 `HTTP/1.1 200 OK`。然后在浏览器打开 `http://你的公网IP`。

查看故障日志：

```bash
docker compose --env-file .env.production -f compose.production.yaml logs --tail=200 app
docker compose --env-file .env.production -f compose.production.yaml logs --tail=200 caddy
```

## 4. 绑定域名并启用 HTTPS

先把域名 A 记录解析到 ECS 公网 IP，再修改：

```dotenv
SITE_ADDRESS=https://你的域名
PUBLIC_ORIGIN=https://你的域名
COOKIE_SECURE=true
```

重新执行 `./deploy.sh`。Caddy 会自动申请和续期证书，因此安全组必须允许 80 和 443。

## 5. 更新版本

提交并推送本地代码后，在服务器执行：

```bash
cd /opt/zhiji
git pull --ff-only
./deploy.sh
```

日常停止使用 `docker compose --env-file .env.production -f compose.production.yaml stop`。不要执行 `docker compose down -v`，否则会删除数据库、学习记录和训练资源所在的命名卷。
