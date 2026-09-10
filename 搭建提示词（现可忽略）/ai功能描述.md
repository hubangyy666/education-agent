# AI 数据标注训练平台：AI 答疑功能实现说明（给 Codex）

> 目标：在现有 AI 数据标注工程师训练平台中实现一套“嵌入式 AI 学习导师”，主要用于 **首页岗位答疑** 与 **答题页面情境化答疑**。  。  
> 核心原则：**不要把它做成通用聊天机器人，不要为了“Agent 化”而过度设计。**

---

## 1. 产品定位

AI 功能只承担“学习答疑 / 训练辅导”，不承担课程主流程控制，也不直接负责判分。

平台有两个 AI 入口：

### 1.1 首页 AI：岗位知识导师

用于回答 AI 数据标注岗位相关问题，例如：

- 什么是 IoU？
- Bounding Box 和 Polygon 有什么区别？
- 工业缺陷标注需要注意什么？
- 裂纹和划痕如何区分？
- 文本实体标注是什么？
- 数据质检一般检查什么？
- 我现在应该重点补哪项能力？

首页 AI 可以直接解释知识，但必须尽量结合用户当前学习状态进行个性化回答。

模式标识：

```text
GENERAL_TUTOR
```

### 1.2 答题页 AI：情境化训练导师

答题页左下角固定一个 AI 助手按钮。

用户点击后可询问：

- 这道题怎么看？
- 给我一点提示
- 为什么我刚才错了？
- 裂纹和划痕有什么区别？
- 这个框为什么不对？
- 我应该注意图片哪里？

答题页 AI 必须自动知道当前题目，不要求用户再次复制题目内容。

模式标识：

```text
QUESTION_TUTOR
```

核心原则：

> 用户尚未提交答案时，AI 不能轻易直接泄露标准答案。AI 应通过“观察方向 → 关键特征 → 强提示 → 提交后完整解析”的方式逐级帮助用户。

---

# 2. 第一版技术方案

## 2.1 推荐架构

第一版 **不使用 LangGraph**。

当前核心流程本质上是：

```text
用户问题
→ 岗位范围判断
→ 构建上下文
→ RAG 检索
→ 重排
→ 调用模型
→ 输出检查
→ 返回
```

暂时不涉及：

- Agent 自主规划
- 多工具循环调用
- 多 Agent 协作
- 长流程状态机
- 自动执行复杂任务

所以第一版使用简单、稳定、容易调试的架构。

## 2.2 推荐 AI 技术栈

```text
Python 3.12
FastAPI
Pydantic v2
SQLAlchemy 2.x / asyncpg
PostgreSQL
pgvector
模型官方 SDK
SSE / StreamingResponse
```

RAG 推荐：

```text
BGE-M3                # Embedding
bge-reranker-v2-m3    # Reranker
```

LangChain：

- 可以使用 Retriever / Text Splitter / VectorStore 等成熟组件；
- 不要求整个 AI 服务依赖 LangChain；
- 不使用 LangGraph；
- 不要为了“Agent 化”增加不必要复杂度。

---

# 3. 系统总体架构

```text
                    前端学习平台
                         │
        ┌────────────────┴────────────────┐
        │                                 │
     首页 AI                           答题页 AI
 GENERAL_TUTOR                    QUESTION_TUTOR
        │                                 │
        └────────────────┬────────────────┘
                         ↓
                  AI Service /ai/chat
                         ↓
                  Scope Classifier
                         ↓
                  Context Builder
                 /        |        \
                /         |         \
         用户学习画像   当前课程    当前题目
                \         |         /
                 \        |        /
                         ↓
                     RAG Retriever
                         ↓
                       Reranker
                         ↓
                    Prompt Builder
                         ↓
                         LLM
                         ↓
                    Output Guard
                         ↓
                    Streaming 返回
```

---

# 4. AI 服务边界

AI 负责：

- 岗位知识解释
- 当前题目提示
- 错误原因解释
- 标注规范解释
- 根据学习画像调整回答难度
- 基于 RAG 给出有依据的回答
- 提供个性化学习建议

AI 不负责：

- 最终判分
- IoU 计算
- 判断某题是否通过
- 课程解锁
- 技能掌握度计算
- 奖励计算
- 任务状态流转
- 直接修改用户成绩

以上逻辑必须由普通后端代码完成。

---

# 5. 两种 AI 工作模式

## 5.1 GENERAL_TUTOR 首页 AI

完整流程：

```text
用户输入问题
      ↓
Scope Check
      ↓
是否属于数据标注岗位相关？
  ├─ 否 → 返回固定引导语
  └─ 是
      ↓
Intent Classification
      ↓
读取 Learner Context
      ↓
构造 RAG Query
      ↓
Metadata Filter
      ↓
向量检索 / 关键词检索
      ↓
Rerank
      ↓
构建 Prompt
      ↓
调用模型
      ↓
Output Guard
      ↓
返回回答
```

首页 AI 可以直接回答知识。

## 5.2 QUESTION_TUTOR 答题页 AI

完整流程：

```text
进入题目
    ↓
加载 Question Context
    ↓
用户点击 AI 助手
    ↓
输入问题
    ↓
Scope Check
    ↓
读取当前答题状态
    ↓
判断 submitted / attemptCount / hintCount
    ↓
决定 Hint Level
    ↓
Question Context
+ Learner Context
+ RAG Context
    ↓
构建 Question Tutor Prompt
    ↓
调用模型
    ↓
检查是否泄露答案
    ↓
返回提示 / 解析
```

---

# 6. 首页 AI 的范围控制

## 6.1 允许回答的范围

只允许以下主题：

```text
annotation_basics
annotation_rules
classification
object_detection
segmentation
industrial_annotation
complex_vision
text_annotation
ai_assisted_annotation
quality_control
project_delivery
career_skill
current_training
learning_guidance
```

对应中文领域：

- 数据标注基础
- 数据标注规范
- 分类与属性标注
- 目标检测
- Bounding Box
- 图像分割
- Polygon / Mask
- 工业缺陷
- 自动驾驶 / 监控等复杂视觉
- 文本分类 / 实体 / 情感 / 意图
- AI 辅助标注
- 数据质检
- 标注返修
- 项目交付
- 数据标注岗位技能
- 当前训练内容
- 学习路径建议

## 6.2 非岗位问题处理

例如：

```text
“今天天气怎么样？”
“帮我写一篇旅游攻略”
“王者荣耀后羿怎么出装？”
```

禁止正常回答。

统一返回：

```text
当前助手主要提供 AI 数据标注岗位学习与训练相关帮助。
你可以问我标注规范、任务操作、行业案例、质量审核或岗位技能方面的问题。
```

---

# 7. Scope Classifier

不要只靠 System Prompt 限制。

必须增加程序级 Scope Check。

---

# 8. Context Builder

AI 的核心不是“聊天记录”，而是“当前学习上下文”。

## 8.1 Learner Context

后端需要提供类似结构：

```json
{
  "userId": "10001",
  "currentAbilityId": "A4",
  "currentSkillId": "A4-S3",
  "currentSkillName": "边界控制",
  "masteryScore": 63,
  "currentMode": "course",
  "recentErrors": [
    "bounding_box_too_large",
    "small_target_missed"
  ],
  "weakSkills": [
    {
      "skillId": "A4-S3",
      "score": 61
    },
    {
      "skillId": "A4-S5",
      "score": 55
    }
  ]
}
```

## 8.2 Question Context

只有 QUESTION_TUTOR 模式必须加载。

示例：

```json
{
  "questionId": "Q10234",
  "questionType": "image_classification",
  "abilityId": "A6",
  "skillId": "A6-S6",
  "skillName": "相似缺陷判断",
  "questionText": "请选择图片中的缺陷类型",
  "candidateLabels": [
    "Crack",
    "Scratch",
    "Dent"
  ],
  "submitted": false,
  "attemptCount": 1,
  "hintCount": 1,
  "userAnswer": null,
  "gradingResult": null
}
```

已经提交后的示例：

```json
{
  "submitted": true,
  "attemptCount": 2,
  "userAnswer": "Scratch",
  "gradingResult": {
    "correct": false,
    "standardAnswer": "Crack",
    "errorType": "LABEL_CONFUSION"
  }
}
```

---

# 9. 判分与 AI 必须彻底分离

## 9.1 分类题

普通后端负责：

```text
userAnswer == standardAnswer
```

AI 只解释。

## 9.2 Bounding Box

普通后端负责：

```text
IoU
漏标
误标
框过大
框过小
目标是否匹配
```

示例：

```json
{
  "correct": false,
  "iou": 0.58,
  "errorType": "BOUNDING_BOX_TOO_LARGE"
}
```

然后传给 AI：

```text
用户目标位置基本正确，但框选范围过大。
请解释哪里需要改进。
```

禁止让大模型自己决定 IoU 或判定标准答案。

## 9.3 Polygon / Mask

普通后端负责：

- Mask IoU
- Boundary IoU
- 漏标面积
- 冗余面积
- 边界偏差

AI 只负责将这些数据翻译成用户容易理解的反馈。

---

# 10. QUESTION_TUTOR 分层提示机制

这是答题页 AI 的核心。

建议至少四个阶段。

## Hint Level 1：观察方向

条件：

```text
submitted = false
attemptCount = 0
```

AI 只能告诉用户“看哪里”。

示例：

```text
先观察缺陷的整体走向。
重点看看它是否连续、是否存在分叉。
```

不得说：

```text
答案是 Crack。
```

## Hint Level 2：关键特征

条件：

```text
submitted = false
attemptCount = 1
```

示例：

```text
可以重点比较“裂纹”和“划痕”：

裂纹通常更不规则，可能出现分叉；
划痕通常方向更连续、更平直。
```

仍然不要直接给答案。

## Hint Level 3：强提示

条件：

```text
submitted = false
attemptCount >= 2
```

示例：

```text
这张图中的缺陷存在明显的不规则延伸，并且局部出现分叉。
再结合两个候选标签的特征判断一次。
```

依然尽量让用户自己完成最后一步。

## Hint Level 4：提交后完整解析

条件：

```text
submitted = true
```

此时允许：

- 给出标准答案
- 对比用户答案
- 解释原因
- 引用项目规范
- 提醒用户历史薄弱点

示例：

```text
这道题的标准标签是 Crack。

你选择了 Scratch，主要混淆点在于两者都可能呈细长结构。
但这里存在明显的不规则分叉，而且宽度变化较大，因此更符合 Crack。

你最近几次任务也出现过 Crack / Scratch 混淆，建议继续完成“裂纹与划痕辨别”强化训练。
```

---

# 11. RAG 设计

## 11.1 不要把所有资料无脑切块

知识库必须和能力树结构绑定。

例如：

```text
A4 目标检测
 ├─ A4-S1 目标发现
 ├─ A4-S2 单目标框选
 ├─ A4-S3 边界控制
 ├─ A4-S4 多目标
 ├─ A4-S5 小目标
 └─ A4-S6 遮挡目标
```

---

# 12. RAG 知识类型

至少包含以下内容：

```text
岗位基础知识
技能知识
标注规范
行业知识
课程内容
项目规范
正确案例
错误案例
易混淆案例
质检规则
```

其中“错误案例库”和“易混淆案例库”非常重要。

例如：

```text
Crack / Scratch 混淆案例
Bounding Box 过大案例
Bounding Box 过小案例
小目标漏标案例
遮挡目标误判案例
```

---

# 13. 检索流程

不要只做 Vector TopK。

推荐：

```text
用户问题
    ↓
Query Rewrite
    ↓
Metadata Filter
    ↓
Vector Search
+
Keyword / Full-text Search
    ↓
Top 20
    ↓
Reranker
    ↓
Top 3~5
    ↓
LLM
```

优先级：

```text
当前项目规范
>
当前题目 / 当前技能规范
>
当前课程
>
行业知识
>
通用岗位知识
```



## 18.1 统一入口

用户 ID 不要由前端明文可信传入。

优先从登录 Token / Session 中取得。

