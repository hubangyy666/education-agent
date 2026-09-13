# 首页 AI 相关关卡推荐验收

日期：2026-09-13；本地服务：`http://127.0.0.1:8000`。

## 行为与范围

首页小基回答技能树相关知识或操作问题后，会显示“接着练一练”卡片，包含真实能力名称、关卡名称和课/岗/赛类型。点击“开始练习”通过既有 `/api/runs/start` 创建或恢复对应关卡训练，再进入 `/train/{run.id}`。无需先展开资源折叠区或到模块目录寻找关卡。

相关性仍由原首页模型结合问题与最近对话判断；只扩充首页提示和现有 `search_learning_resources` 的关卡检索结果。知识检索、个人学情读取继续按需调用，原模型调用链、事实校验、SSE、题内导师、确定性评分和题库均保持原流程。查询使用目录中的真实关卡，IoU 等术语以检索同义词关联到对应技能，没有新增用户问题的固定意图分流。

推荐只在 SSE `done` 到达后显示，每条回答最多三张。无匹配、无关问题或学生明确不要推荐时不附卡片。开始训练有等待状态、防重复点击、错误重试和卸载取消；原知识来源与普通模块资源仍可展开查看。

## 实际参考观察

在用户已登录的联想浏览器 Brilliant 首页，普通提问 `What is probability?` 得到解释后自动显示 `Introduction to Probability` 推荐卡，不需要明确索要推荐。原有 Python 推荐卡 `Variables` 的 Start 实际进入具体关卡导语页，未继续作答。该观察只用于参考回答后推荐与直达关卡的交互。

## 自动与真实模型验证

```powershell
npm run build
.\.venv\Scripts\python.exe -X utf8 -m pytest backend/tests/test_tutor_policy.py -q
node scripts/verify_tutor_recommendations.mjs
# 以下脚本需要本地服务及已配置模型，会真实调用模型，并清理自己的临时账号。
.\.venv\Scripts\python.exe -X utf8 scripts/verify_homepage_recommendations_live.py
```

- TypeScript 检查与生产构建通过。
- 导师定向测试 36 项通过，包括原有题内事实约束、按需工具、70 关目录 ID、无匹配、虚构资源过滤及回答 token 先于推荐元数据。
- 真实 Vue setup、模板、按钮事件与可控 SSE 的组件检查 8 组通过，包括加载中重复点击、失败重试、卸载后的迟到响应，以及首页/题内推荐隔离。这一层使用 API 替身。
- 最终真实模型/SSE 五个场景全部通过，provider 为 `deepseek`、model 为 `deepseek-v4-pro`，均无事实校验重试。结果保存在 `.runtime/homepage-recommendations-live.json`。

| 实际提问 | 最终推荐 | 按需工具 |
| --- | --- | --- |
| 什么是 IoU？ | A4-L3 边界控制 | search_learning_resources |
| 文本实体的边界应该怎么确定？ | A8-L2 实体边界、A8-L1 实体识别 | search_learning_resources |
| 明天会下雨吗？ | 无 | 无 |
| 什么是 IoU？只解释概念，这次不要推荐练习。 | 无 | 无 |
| 接着 IoU 对话问“这个数值越高越好吗？” | A4-L3 边界控制 | search_learning_resources |

首次真实验证发现旧的“信息足够直接回答”策略会跳过资源查询，后续发现短追问也会跳过；已在首页提示中区分讲解信息和关卡元数据，并明确每轮独立查询相关关卡。上表记录修正后的最终运行，不用组件替身代替真实模型结果。

## 浏览器与存储验证

独立账号 `qa_agent_tutor_recommend_0913` 在首页点击“什么是 IoU？”：等待期间没有卡片，回答后显示“目标检测与定位 · 课关 / 边界控制 / 开始练习”。桌面与 390px 视口实际查看均无卡片文字遮挡；手机可用文档宽与滚动宽同为 375px，无页面横向溢出。

真实点击推荐卡后进入 `/train/e9ccb5ea-72fd-4703-a313-d8c6a5d9be95`；PostgreSQL 确认仅创建一个 A4-L3、course 模式、7 题的 Run，答案记录为 0。继续进入后页面显示当前题库中的实际第一题，没有提交答案。浏览器未发现控制台错误。

测试账号、Run 和登录会话已清理，未对演示账号提交答案。本次没有重新运行全库测试，也不将一个关卡的浏览器操作称为全部 70 关的逐关验收。
