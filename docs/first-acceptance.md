# 修复版独立验收

2026-09-10，目标 `http://127.0.0.1:8000`。未修改项目源码，未调用外部模型。

本轮合计 **630 个用例通过**：原有全套 77 个（包括全部 7 个缺陷回归及 factory 检查）通过；现存 550 道题的逐题标准答案判分全部通过；后台到期、知识库、题集结构 3 个新增检查通过。

## 后台竞赛结算

仅为专属 QA 账号建立一个 10 题竞赛 Run，设定即将到期。创建后 **没有调用 Run 读取、答题、完成或 Dashboard 接口**；等待 3.000 秒后直接查询数据库。

- deadline：`2026-09-10T04:30:13.046247+00:00`
- 后台 finished_at：`2026-09-10T04:30:13.811625+00:00`
- 数据库观察时刻：`2026-09-10T04:30:15.834109+00:00`
- status=`completed`，报告 10 题、0 分、漏标率 100%，Progress attempts=1。

证据：`background-expiration-evidence.json`。

## 题库与知识库

10 个活动题集均为 V1，包含 70 个关卡、550 个不同题 ID；每能力 5 个课关各 5 题、岗位 20 题、竞赛 10 题。题型为 choice 305、box 170、polygon 45、entity 30。**550/550 标准答案判为 correct=True，550/550 得 100 分，均无漏标或多余标注。**

知识库数据库与鉴权 API 都返回 55 条，均具备内容、1024 维向量及 approved 独立审核元数据。GENERAL 4 条、A8 6 条，其余 A1-A10 各 5 条。最初新增测试沿用候选期每类恰好 5 条假设而失败；核对后确认独立审核将 `KB-GENERAL-005`（SQuAD 阅读理解知识）明确归入 A8，属于有记录的合理调整。测试已改为与正式 reviewed artifact 核对分类并检验各能力覆盖，复跑通过，没有修改产品或数据来满足测试。

证据：`golden-grading-evidence.json`、`knowledge-acceptance-evidence.json`。

## 原缺陷与测试记录

多目标匹配、严格相交 Polygon、框布尔坐标、实体布尔/浮点偏移、scope guard 两个方向的原最小复现现已全部通过回归。权限、锁关、岗位整包不泄答案、deadline 拒收、持久化、返修、新手流程、离题 SSE、隔离刷新发布流程仍通过。

- `recheck-original-results.xml`：77 passed。
- `recheck-acceptance-results.xml`：新增首轮 552 passed，1 个过时分类假设 failed（保留原始结果）。
- `recheck-knowledge-results.xml`：修正测试预期后知识检查 1 passed。
- `test_recheck_acceptance.py`：新增 553 个可复现用例。

刷新检查使用隔离 Session/Redis 替身，没有改共享题库版本。此报告覆盖 API 和确定性判分，不代表外部模型回答或所有前端交互已验收。

结束后独立查询 `qa_agent_*` User、Run、Progress、TaskCard、Redis session 均为 **0**，见 `recheck-cleanup-evidence.json`；未操作四个演示用户。
