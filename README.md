# 智基 · AI 数据标注岗位训练平台

根据本目录的 `agent.md`、`技术栈.md`、`ui交互与功能.md`、`ai功能描述.md`、`题目数据.md`、`知识库采集.md`、模型配置和竞赛 PDF 实现。最后更新：2026-09-10。UI 已对照 `D:\imageagent` 中的五张本地参考图；未引入参考图中划掉的排行榜、营销横幅、每周总结和时间筛选。

## 启动

需要 Python 3.12、Node.js 20.19+/22.12+ 和已启动的 Docker Desktop。在项目目录运行：

```powershell
.\start.ps1
```

脚本启动 PostgreSQL/pgvector、Redis、MinIO，导入已审核知识，构建 Vue 前端，并在后台启动 FastAPI。打开 **http://127.0.0.1:8000**。已有构建时可运行 `./start.ps1 -SkipBuild`。服务日志保存在 `.runtime/server.log` 和 `.runtime/server-error.log`。

| 账号 | 初始密码 |
| --- | --- |
| xuyihao | 123456 |
| zhangxiang | 123456 |
| songsang | 123456 |
| mengfei | 123456 |

每个账号有独立学习记录。首次登录进入新手引导；完成后再次登录进入首页。验证工作使用独立临时账号，不会预先完成以上四个账号的课程。

开发前端：`npm run dev`，地址 http://127.0.0.1:5173，Vite 将 `/api` 与 `/media` 转发到 8000。开发后端：`.venv/Scripts/python.exe -X utf8 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload`。生产构建：`npm run build`；构建文件由同源 FastAPI 服务提供。

## 已实现的学习流程

- 新手教学：认识标注、目标设定、点击目标、拖动画框、选择标签、独立标注、真实区域反馈、三题诊断。
- 首页根据技能前置关系、诊断、近期成绩与学习目标推荐下一关。技能地图涵盖 A1—A10，并展示实际掌握度。
- 每个能力包含五个课关（各5题）、一个岗关（20题）、一个赛关（10题）。课程即时反馈和重试；岗关连续保存后统一质检、报告和返修；赛关需完成全部前置关卡，限时10分钟，关闭页面后后端仍会结算。
- 图像矩形、多目标矩形、多边形、分类与文本实体交互；矩形移动/缩放/键盘微调，撤销和删除；多边形逐点绘制与闭合。
- 后端确定性判分：标签准确率、平均 IoU、漏标率、误标率，另包含分割区域/边界指标。题目标准答案与审核元数据不会在提交前发给前端。
- 首页和题内的小基导师，分别使用通用与视觉模型；包含岗位范围检查、分层提示、提交后解释、来源引用、AI 内容标记与浏览器语音反馈。
- 企业工作描述转换为任务卡：情境、步骤、交付物、知识、技能、安全要点和可访问训练资源；支持保存历史和导出。
- 个人中心展示今日题数、得分率、最近七天蓝色柱状图、能力优势、徽章和训练记录。

## 架构与数据

Vue 3 + TypeScript + Vite / FastAPI + SQLAlchemy / PostgreSQL + pgvector / Redis / MinIO / Python RAG。

| 目录 | 内容 |
| --- | --- |
| `src/views`、`src/components` | 页面与标注交互 |
| `backend/main.py` | 登录、训练、任务卡、资料与对话 API |
| `backend/grading.py` | 独立于大模型的可执行判分器 |
| `backend/adaptive.py` | 学情画像、技能掌握度与推荐 |
| `backend/tutor.py` | 受限辅导、检索、上下文与防泄题 |
| `backend/factory_workflow.py`、`factory_agent.py` | 储备、生成、独立审核、发布与质量监测 |
| `backend/visual_reserve.py` | 从真实标准标注构建交互题 |
| `data/knowledge` | 已审核知识及逐条来源/审核信息 |
| `data/factory` | 候选储备、内容指纹、审核记录与质量统计 |
| `data/initial-question-sets.json` | 随仓库发布的离线 V1 初始题库（10 个能力、550 题） |
| `data/samples` | COCO 原图与官方 GT 清单 |
| `data/industrial` | KolektorSDD 原图、官方掩码、派生标注及许可 |
| `backend/tests`、`docs` | 回归验证与验收证据 |

数据库与对象存储使用 Docker 命名卷持久化；重启服务不会清空学习记录。**不要执行 `docker compose down -v`，该命令会删除持久化数据。**

## 题目与知识更新

首次启动不联网生成题目，也不依赖动态储备是否充足。服务会校验并导入仓库内的 `data/initial-question-sets.json`；只有数据库中缺少某能力的活动题集时才导入对应 V1。维护者需要重新确定初始题目时，可运行 `.venv/Scripts/python.exe -X utf8 scripts/build_initial_question_sets.py` 重建该版本化文件，并在提交前执行完整测试。

模块右上角“更新题目”触发后台工作流，进度来自实际处理阶段。按五个技能点均衡规划，优先使用已有储备，缺口才补题/补素材。AI 场景题由两次独立请求分别生成与审核，程序进一步检查正确答案、反例、技能、来源与内容去重；图像坐标从官方 GT 派生。发布使用事务与互斥锁，既有训练保留题目快照。失败保留原版本并显示失败原因。

完成的答题记录用于质量监测。至少10条有效记录且错误率≥85%只会触发疑问复核，不直接把难题判定为坏题。独立审核明确拒绝后才淘汰、补充并替换。统计是最终保存答案的错误率，不是首答错误率。

知识采集和审核规则见原始 `知识库采集.md`。仅 `approved`、独立审核、来源与质量分数达标且无冲突的条目能进入数据库；正文100—400字并进行去重。导入：`.venv/Scripts/python.exe -X utf8 scripts/import_knowledge.py`。

COCO 原图只选 CC BY / CC BY-SA 样本，每图保留来源与具体许可；标注来自 COCO 2017。KolektorSDD 为 **CC BY-NC-SA 4.0**，当前用于非商业教学/竞赛，署名和派生方式见 `data/industrial/README.md`；不将官方二元缺陷标签伪称为裂纹/划痕细分类。`data/reservoir-sources.json` 中其他数据集是来源目录，不代表已经下载。

## 模型配置

首次配置脚本从本地模型文档写入服务端 `.env`，不会打印密钥或写进前端。可参考 `.env.example` 修改。两个指定模型均已真实调用验证，结果见 `docs/model-verification.json`。

- GENERAL_TUTOR / 任务卡：`deepseek-v4-pro`
- QUESTION_TUTOR / 题库生成审核：`deepseek-v4-flash-vision-exp`
- 模型不可用时，导师明确显示课程/知识库提示；工厂不以重复旧题冒充审核成功。

当前已运行的向量检索为 **1024维词法哈希 + pgvector + 关键词重排**。代码支持 BGE-M3 与 BGE reranker 的服务接口，但本机没有部署这两个模型。切换到 BGE 时必须重建全部知识向量，不能混用两种向量空间。

## 验证与实际边界

```powershell
npm run build
.venv/Scripts/python.exe -X utf8 -m pytest backend/tests -q
```

接口测试需要本地基础服务和 FastAPI 已运行，只创建并清理 `qa_agent_*` 测试账号。真实浏览器验收涵盖登录、新手完整流程、矩形/多边形/实体交互、导师、任务卡、任务报告与响应式界面，详细结果见 `docs/验收报告.md`。

浏览器语音使用设备的 Speech Synthesis，发声需要浏览器支持、可用声音及用户交互。页面同时保留文字反馈。三种页面工具（读取学习进度、打开技能图、开始训练）通过 WebMCP 暴露同一套应用动作。

当前交付为本地可运行的完整服务，未发布公网。截图提供了静态布局参考，未提供的 Brilliant 动效无法作逐帧一致性验证。本版分割操作是单个连续多边形；完整语义掩码、多实例多区域和孔洞编辑尚未实现，相关课程通过规范/场景题讲解，不能将其称为像素级生产标注编辑器。竞赛 PDF 要求的真实用户访谈反馈、校内真实资源接入和正式比赛交付材料须由实际参与者与学校提供，未编造。

