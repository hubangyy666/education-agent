# 智基 · AI 数据标注岗位训练平台

智基是一个面向职业教育场景的本地全栈训练平台，围绕 AI 数据标注岗位，把“知识学习—交互练习—岗位实战—限时竞赛—质量报告—返修复盘”串成可真实运行的学习闭环。

项目不是静态演示：账号、学习进度、答题记录、岗位学习证据、题集版本和管理者新增知识均写入 PostgreSQL；会话与题目更新状态使用 Redis；训练图片由 MinIO 提供；前后端通过真实 API 联调。大模型负责受约束的辅导和内容更新，标准答案与成绩始终由后端确定性规则判定。

最后更新：2026-09-12。

## 项目特点

- **完整能力体系**：A1—A10 共 10 个能力模块、70 个关卡，所有关卡均可直接进入，箭头只表示建议学习顺序。
- **多种标注交互**：支持单选分类、文本实体、单目标/多目标矩形框、多边形标注，以及框的移动、缩放、键盘微调、撤销和删除。
- **分层训练机制**：每个能力包含 5 个课关、1 个岗关和 1 个赛关；课关逐题学习，岗关整包质检并支持返修，赛关由服务端限时结算。
- **真实岗位教学**：4 个岗位方向、8 项固定典型任务，包含工作情境、任务目标、步骤、规范、质量要求、考核方式、学习证据和关联实操。
- **确定性评价**：标签、实体边界、IoU、漏标率、误标率和分割指标由 `backend/grading.py` 计算，不让模型决定分数。
- **AI 学习导师**：首页与题内均提供“小基”文字导师，可按需读取学情、检索知识和解释已提交结果；比赛进行中不会提示答案。
- **可追溯内容更新**：固定 V1 离线题库保证首次启动；题目工厂支持生成、独立审核、去重、原子发布和旧 Run 快照保留。
- **本地语音鼓励**：答对后播放随项目提供的 Kokoro 中文 WAV；错误答案、AI 回复和教学讲解不朗读，也不调用浏览器文字转语音。
- **独立后台管理端**：管理者可创建/删除学习者或管理者账号，查看知识库分区，并将已核对内容写入 PostgreSQL/pgvector 供导师检索。

## 快速启动

### 环境要求

当前启动脚本面向 Windows PowerShell，首次运行前请准备：

| 依赖 | 要求 |
| --- | --- |
| Python | 3.12，并可通过 `py -3.12` 调用 |
| Node.js | 20.19+ 或 22.12+ |
| Docker | Docker Desktop，包含 Docker Compose V2 |
| PowerShell | 可执行本地 `.ps1` 脚本 |

首次安装依赖、拉取 Docker 镜像或补采训练素材时需要联网；仓库内的 V1 初始题库不依赖联网或模型生成。

### 一键启动

在项目根目录运行：

```powershell
.\start.ps1
```

脚本会依次完成：

1. 首次创建 `.venv` 并安装 `backend/requirements.txt`；
2. 首次生成仅供服务端使用的 `.env` 和随机基础服务密码；
3. 启动 PostgreSQL/pgvector、Redis 和 MinIO；
4. 在训练素材缺失时执行采集脚本；
5. 安装前端依赖（仅 `node_modules` 不存在时）并构建 Vue；
6. 校验并导入已审核知识；
7. 启动 FastAPI，等待 `/api/health` 返回就绪。

启动成功后访问：**http://127.0.0.1:8000**

如果依赖和 `dist` 已经准备好，可跳过前端构建：

```powershell
.\start.ps1 -SkipBuild
```

`-SkipBuild` 不会启动 Vite；它仍会检查基础服务、导入知识并确保 8000 端口上的 FastAPI 可用。

### 演示账号

| 类型 | 账号 | 初始密码 |
| --- | --- | --- |
| 学习者 | `xuyihao`、`zhangxiang`、`songsang`、`mengfei` | `123456` |
| 管理者 | `user1` | `123456` |

学习者首次登录后进入新手教学，各账号的训练和进度相互隔离；管理者登录后直接进入 `/admin`。这些是本地演示凭据，不应直接用于公网部署。

Linux ECS 公网部署请参阅 [`docs/production-deployment.md`](docs/production-deployment.md)。生产配置会通过服务器本地的 `.env.production` 为体验账号和管理员设置不同的初始密码，该文件不会提交到 Git。

### 启动状态与日志

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 8000,5173,54329,63799,9009,9010
```

FastAPI 后台进程 PID 写入 `.runtime/server.pid`，标准输出和错误日志分别位于 `.runtime/server.log`、`.runtime/server-error.log`。停止基础服务可运行 `docker compose stop`；不要添加 `-v`，否则会删除命名卷中的学习数据。

## 开发方式

先运行 `.\start.ps1` 完成基础服务和数据初始化，再按需要启动开发服务。

### 前端热更新

```powershell
npm run dev
```

访问 http://127.0.0.1:5173。Vite 只负责前端，并将 `/api`、`/media` 转发到 `127.0.0.1:8000`；单独运行 `npm run dev` 不会启动 FastAPI、数据库或对象存储。

### 后端热更新

确保 8000 端口没有旧的 FastAPI 进程，再运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 前端生产构建

```powershell
npm ci
npm run build
```

构建结果写入 `dist/`，FastAPI 会以同源方式提供页面和静态资源。

## 学习流程

### 1. 新手教学

新账号先完成标注认知、点击目标、拖动画框、选择标签、独立标注和 3 道学情诊断。诊断结果用于后续推荐，但不计入正式技能分。

### 2. 技能地图与关卡

能力体系覆盖标注基础、规范理解、分类属性、目标检测、图像分割、工业缺陷、复杂场景、文本语义、质量审核和项目交付。每个能力固定包含：

| 关卡类型 | 数量 | 题量 | 反馈方式 |
| --- | ---: | ---: | --- |
| 课关 | 5 | 每关 5 题 | 逐题确定性反馈，答对后继续 |
| 岗关 | 1 | 20 题 | 整包提交后生成报告，可返修错误样本 |
| 赛关 | 1 | 10 题 | 10 分钟服务端计时，结束后统一反馈 |

仓库内 `data/initial-question-sets.json` 固定提供 10 个能力、70 个关卡、550 道 V1 题，当前题型分布为选择题、矩形框、多边形和文本实体。数据库已有 V2/V3 等活动题集时，启动不会用 V1 覆盖它们。

### 3. 技能分

```text
技能分 = 答对题数 ÷ 已判定题数 × 10
```

技能分范围为 `0.00–10.00`，保留两位小数。它与关卡完成数、入门诊断分、百分制训练报告和历史最高成绩分别统计：

- 同一次训练的同一道题以最新保存答案为准；
- 课关提交后立即更新；
- 岗关和赛关在整包结算后更新，避免中途泄露对错；
- 返修中自动继承的正确答案不会重复累计。

### 4. 岗位学习

`/jobs` 使用 `data/job-catalog.json` 中的固定目录，不调用模型临时编写页面。当前包含计算机视觉、工业缺陷、文本语义和数据标注质检 4 个方向，共 8 项典型任务。

任务详情的 GET 请求是只读操作；只有学习者主动保存步骤时，`/enroll` 才会创建或恢复 PostgreSQL 学习记录。阅读步骤需要提交文字证据，实操步骤必须关联本人真实完成且达到门槛的训练 Run。页面“完成”表示四阶段教学证据齐全，不等同于企业生产批次已经验收。

旧版企业任务转换接口和 `/tasks` 页面仍为历史兼容能力，但已从当前首页、主导航和岗位流程中移除；固定岗位教学不依赖该功能。

## AI、题目与知识库

### 模型配置

`.env` 仅在服务端读取。首次自动生成的配置不会包含模型密钥，如需启用真实模型调用，请填写：

```dotenv
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
GENERAL_MODEL=deepseek-v4-pro
QUESTION_MODEL=deepseek-v4-flash-vision-exp
```

- `GENERAL_MODEL` 用于首页导师和历史任务卡转换；
- `QUESTION_MODEL` 用于题内视觉辅导、候选题生成与独立审核；
- 未配置或模型不可用时，确定性训练、评分、固定岗位内容和离线题库仍可运行，导师会退回课程/知识库提示，题目工厂不会把失败伪装成成功发布。

默认向量方案是本地 **1024 维词法哈希 + pgvector + 关键词重排**。代码也支持 BGE-M3 与 reranker 服务；切换 `EMBEDDING_BACKEND` 后必须重建全部知识向量，不能混用不同向量空间。

### 题目版本与刷新

首次启动只在某个能力没有活动题集时导入其 V1；已有活动版本和历史 Run 保持不变。能力页“更新题目”会执行储备检查、技能均衡、必要的有界补充、生成与独立审核、答案执行校验、内容去重和事务发布。

新版本按内容指纹统计真正变化的题目；不足部分可以复用已发布且未淘汰的合格题，但至少存在新内容才会发布。发布失败时保留原活动题集和失败原因，旧训练始终使用创建时保存的题目与答案快照。

维护者需要重新生成仓库内固定 V1 时运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/build_initial_question_sets.py
```

该命令会改写版本化种子文件，应在完整复核和测试后再提交；动态版本更新仍由题目工厂负责。

### 知识库

已审核知识位于 `data/knowledge/`，导入命令为：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/import_knowledge.py
```

导入程序会检查审核状态、来源、正文长度、质量分数和冲突信息。管理者新增知识会按段落切分、生成向量并立即加入所选的通用或 A1—A10 检索范围；请只录入已经核对、允许使用的内容。

## 技术架构与数据

```text
Vue 3 + TypeScript + Vite
            │ /api、/media
            ▼
FastAPI + SQLAlchemy
    ├── PostgreSQL 16 + pgvector：账号、进度、Run、题集、岗位记录、知识
    ├── Redis：登录会话、题目更新锁和进度状态
    └── MinIO：训练图片对象
```

| 路径 | 作用 |
| --- | --- |
| `src/views/`、`src/components/` | 页面、训练流程与交互组件 |
| `src/store.ts`、`src/api.ts` | 登录态、学习数据与 API 调用 |
| `src/webmcp.ts` | 读取学习进度、打开技能图、开始训练的页面工具 |
| `backend/main.py` | 鉴权、训练、导师、题目更新与静态站点入口 |
| `backend/grading.py` | 独立于大模型的确定性判分器 |
| `backend/adaptive.py` | 技能分、学情画像与学习推荐 |
| `backend/tutor.py` | 受限导师、按需工具调用、RAG 与防泄题策略 |
| `backend/jobs.py` | 固定岗位目录、学习记录与实操关联 |
| `backend/admin.py` | 账号与知识库管理接口 |
| `backend/factory_workflow.py` | 题目工厂刷新、审核、发布和质量监测 |
| `data/job-catalog.json` | 4 个岗位方向与 8 项固定教学任务 |
| `data/initial-question-sets.json` | 可克隆、可校验的离线 V1 初始题库 |
| `data/samples/`、`data/industrial/` | COCO 与 KolektorSDD 教学素材及来源信息 |
| `backend/tests/`、`docs/` | 自动化测试、验收证据与内容边界说明 |

PostgreSQL、Redis 和 MinIO 使用 Docker 命名卷持久化。普通重启、`docker compose stop` 或不带 `-v` 的 `docker compose down` 不会主动清空命名卷；**不要执行 `docker compose down -v`**。

## 验证

基础验证命令：

```powershell
npm run build
npm run test:api
node scripts/verify_encouragement_audio.mjs
```

2026-09-12 按当前工作树复验：前端生产构建通过，后端 **708 项测试通过**（2 条依赖弃用警告），语音文件与异步交互 **17 项检查通过**。

岗位在线验证需要 8000 服务已启动：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/verify_jobs_live.py
```

测试脚本使用 `qa_agent_*` 临时账号并在结束后清理。单元/API 测试、题库种子校验或音频文件解码不等同于浏览器端到端验收；不同层级的证据应分别记录。

## 常见问题

### `npm run dev` 后出现 `ECONNREFUSED 127.0.0.1:8000`

Vite 没有启动后端。先检查 8000 端口和健康接口，再运行 `.\start.ps1` 或单独启动 Uvicorn。不要因为代理报错就先改前端请求地址。

### Docker 服务启动失败

确认 Docker Desktop 已运行，执行 `docker compose ps` 查看 PostgreSQL、Redis、MinIO 状态，并检查 `.env` 是否存在。首次环境可以删除错误的 `.env` 后重新生成；已经有持久化数据库时不要随意更换 PostgreSQL 密码。

### 拉取新代码后前端依赖异常

`start.ps1` 在 `node_modules` 已存在时不会自动执行 `npm ci`。依赖锁文件变化后请手动运行：

```powershell
npm ci
npm run build
```

### 页面仍显示旧版本

先重新构建 `dist`，再刷新页面。生产资源使用哈希文件名；路由层也会在旧懒加载分块失效时尝试一次安全刷新。

## 数据来源、许可与边界

- COCO 训练图片按单图来源和许可清单使用，属于公开教学素材，不是企业委托工单。
- KolektorSDD 工业图像及官方掩码采用 **CC BY-NC-SA 4.0**，当前仅用于非商业教学；本项目派生边界框和外轮廓，不把二元“表面缺陷”伪称为裂纹/划痕细分类。
- Label Studio 工作界面截图来自其公开仓库并保留 Apache-2.0 许可文件；截图只说明行业工具形态，不代表本平台实现了截图中的全部功能。
- 文本实体和沟通意图语料是智基原创虚构教学内容，不宣称为真实客户对话。
- 当前多边形编辑器面向单个连续区域，不支持完整语义掩码、多区域实例或孔洞编辑，不能称为生产级像素标注工具。
- 仓库根目录没有统一许可文件；复用代码、数据和媒体前，应分别核对对应来源与许可。
- 当前交付面向本机运行，未按公网生产环境完成 HTTPS、密钥托管、备份恢复和安全加固。

## 相关文档

- [岗位内容来源与教学边界](docs/job-sources.md)
- [岗位固定讲解版验收](docs/jobs-acceptance.md)
- [关卡、技能分、题目更新与语音验收](docs/learning-updates-acceptance.md)
- [正确答题激励语音说明](docs/voice-feedback.md)
- [候选知识独立审核记录](docs/knowledge-review.md)
- [确定性判分与题库复验](docs/first-acceptance.md)
- [KolektorSDD 子集、派生方式与许可](data/industrial/README.md)
