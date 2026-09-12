# 岗位学习目录：来源、教学转化与边界

更新：2026-09-11。目录文件：`data/job-catalog.json`。本文件记录岗位内容与素材依据，不构成外部企业招聘信息、合作关系、内规或生产验收承诺。

## 选择依据

四张岗位卡是 AI 数据标注工作中的常见专业方向：计算机视觉、工业缺陷、文本语义、数据标注质检。企业公开服务资料证明相应业务与工作流真实存在；名称是面向教学的岗位方向归纳，不将每个方向宣称为独立国家职业名称。没有复制招聘薪资、编造合作企业工单或采用无依据的行业统一验收阈值。

专业统一对接教育部 2025《人工智能技术应用专业教学标准（高等职业教育专科）》的 510209 专业。第 1 页职业面向包括人工智能训练师；第 2 页涉及数据标注能力；第 3 页强调依托真实生产项目和典型工作任务开展项目式、情境式教学；第 4 页“人工智能数据服务”包含使用工具标注并进行分类、统计、审核。页面具体职责、教学时长、四阶段学习支架和任务文案为智基教学设计，不冒充标准原文。

## 产业—岗位—专业—任务映射

| 产业需求 | 岗位方向 | 典型任务的教学转化 | 专业与能力落点 |
| --- | --- | --- | --- |
| 智能驾驶、视觉数据服务与零售物体识别 | 计算机视觉标注员 | 多目标检测试标；单个物体的精细轮廓标注 | 510209：人工智能数据服务、计算机视觉；A1/A2/A4/A5/A7 |
| 制造业视觉质检 | 工业缺陷标注员 | 零件表面缺陷定位；正常与异常样本复核 | 510209：数据服务与行业视觉应用；A1/A2/A3/A4/A6 |
| 智能客服、信息抽取 | 文本语义标注员 | 文本实体与名称边界标注；客服沟通意图标签判断 | 510209：人工智能数据服务、自然语言处理；A1/A8 |
| 数据生产与交付 | 数据标注质检员 | 目标标注返修与复核；标注数据交付检查 | 510209：数据统计审核、综合项目；A4/A9/A10 |

## 来源登记

以下链接在本轮通过联网检索或原页阅读核对。数据堂站点部分地区访问会超时或跳转，其公开正文可由搜索索引读取；不绕过登录或付费限制。所有内容均为独立中文归纳，未搬运企业图片或长篇正文。

| 来源 ID | 原始来源 | 发布方 | 本次使用范围 |
| --- | --- | --- | --- |
| MOE-AI-2025 | [人工智能技术应用专业教学标准（高等职业教育专科，2025）](https://hudong.moe.gov.cn/s78/A07/zcs_ztzl/2017_zt06/17zt06_bznr/bznr_zyjyzyjxbz/gdzyjy_zk/zk_dzyxxdl/dzxxdl_jsjl/202502/P020250207532415004946.pdf) | 中华人民共和国教育部 | 专业代码 510209；职业面向包含人工智能训练师。人工智能数据服务涉及多模态标注、分类统计与审核；强调依托真实项目和典型任务开展情境式教学。用于专业及课程映射。 |
| DATATANG-SERVICE | [全栈式数据服务与行业高质量数据集案例](https://datatang.com/news/1182) | 数据堂 | 企业公开说明数据清洗、人工与自动标注、版本管理、质量评测、交付及行业专家协作流程；公开电力行业案例。仅用于确认企业任务形态，未引用其营销质量数字。 |
| DATATANG-DOMAINS | [数据堂行业数据解决方案](https://www.datatang.net/) | 数据堂 | 公开提供智能驾驶、智能客服、新零售等应用的数据服务，包含图像、文本及人机协同质检。用于产业场景映射，不代表具体招聘公告。 |
| KEYMAKR-MANUFACTURING | [Image & Video Annotation for Manufacturing](https://www.keymakr.com/manufacturing.html) | Keymakr | 制造业视觉数据标注用于缺陷检测、生产物项识别与质量控制。用于工业标注岗位场景；课程未使用企业专有图像或内规。 |
| KSDD | [Kolektor Surface-Defect Dataset](https://www.vicos.si/resources/kolektorsdd/) | ViCoS Lab / Kolektor Group | Kolektor 提供并标注的真实工业表面图像，包含有缺陷及无缺陷样本。当前仓库使用官方二元掩码和派生区域，只称表面缺陷。许可 CC BY-NC-SA 4.0。 |
| COCO | [COCO — Common Objects in Context](https://cocodataset.org/#home) | COCO Consortium | 真实日常场景中的目标检测与分割数据。页面样图采用仓库已有 COCO 2017 原图，照片独立许可以单图清单为准；非合作企业生产数据。 |
| CVAT-BOX | [CVAT 矩形标注官方文档](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/annotation-with-rectangles/) | CVAT | 矩形对象创建、标签选择及边界编辑的操作依据。课程中的目标范围与边界策略由当前题目明确，不从工具功能推导行业统一规则。 |
| CVAT-POLYGON | [CVAT 多边形标注官方文档](https://docs.cvat.ai/docs/annotation/manual-annotation/shapes/annotation-with-polygons/) | CVAT | 多边形轮廓绘制与编辑的操作依据。智基本次关联训练为单连续区域多边形，不声称完整像素掩码生产工具。 |
| LS-NER | [Label Studio 命名实体识别模板](https://labelstud.io/templates/named_entity.html) | HumanSignal / Label Studio | 在文本中选择实体片段并赋人名、机构、地点等类型。用于实体类型与边界训练；是否允许嵌套由具体任务定义。 |
| LS-SENTIMENT | [Label Studio 情感分类模板](https://labelstud.io/templates/sentiment_analysis.html) | HumanSignal / Label Studio | 展示文本与单选正向、负向、中性标签，也可组合其他属性。用于区分整句分类与实体片段标注。 |
| LS-INTENT | [Label Studio 槽位填充与意图分类模板](https://labelstud.io/templates/slot_filling.html) | HumanSignal / Label Studio | 组合句子意图分类和文本片段槽位标注的任务形态。课程客服例句由智基编写，未接入真实客户对话。 |
| APPEN-QA | [Appen Task Types and review-data](https://success.appen.com/appen-success-center/create-design-jobs/job-design-universals/guide-to-task-types-and-review-data) | Appen | 标注项目可包含标注、质量审核和仲裁；QA 可载入已有标注供审核与修正。用于解释标注员与质检员协作。 |
| CVAT-QA | [CVAT Manual QA and Review](https://docs.cvat.ai/docs/qa-analytics/manual-qa/) | CVAT | 说明审核分工、创建问题、修正反馈与解决问题的工作流。教学据此设计可定位的问题记录和返修复核。 |
| LS-EXPORT | [Label Studio 标注导出与坐标单位](https://labelstud.io/guide/export) | HumanSignal / Label Studio | JSON矩形字段使用图像尺寸的百分比，需要结合原图尺寸转换成像素；导出格式与是否包含原始媒体要分别核对。用于交付格式检查。 |
| CVAT-YOLO | [CVAT Ultralytics YOLO 格式](https://docs.cvat.ai/docs/dataset_management/formats/format-yolo-ultralytics/) | CVAT | 说明YOLO标注结构及归一化坐标。交付前需要核对图像对应关系、坐标定义、类别映射与接收要求，不能只看文件后缀。 |
| CVAT-MANIFEST | [CVAT 数据清单格式](https://docs.cvat.ai/docs/dataset_management/dataset_manifest/) | CVAT | 图像清单记录文件名、扩展名、宽高；meta和checksum为可选字段。项目额外要求校验值时需单独确认，不能把工具可选项称为通用强制标准。 |
| CVAT-PROJECT-EXPORT | [CVAT 项目备份与数据集导出](https://docs.cvat.ai/docs/api_sdk/sdk/examples/projects/) | CVAT | 项目备份用于保留任务、作业、标注与设置；数据集导出按指定格式产出，是否携带图像取决于参数，include_images=False仅导标注。用于按接收目的选择交付产物。 |
| LS-CHOICES | [Label Studio 单选与多选标签](https://labelstud.io/tags/choices.html) | HumanSignal / Label Studio | Choices可配置单选或多选。沟通意图练习采用项目规定的咨询、投诉、建议单选标签；这组三类是教学项目字典，非官方统一意图分类标准。 |
| SPACY-ENTITIES | [spaCy 命名实体与文本片段](https://spacy.io/usage/linguistic-features#named-entities) | Explosion / spaCy | 实体识别为连续文本片段分配类型，实体可以是人、地点或机构。用于现有原创实体练习的概念来源，不作为虚构句子内容的事实来源。 |
| CVAT-AUTO-QA | [CVAT 基于验证集的自动质量评估](https://docs.cvat.ai/docs/qa-analytics/auto-qa/) | CVAT | 使用带参考标注的验证图像子集估计作业质量；验证子集结果不能证明未抽检图片已经逐张人工审核。用于交付检查中的证据范围。 |
| CVAT-IMMEDIATE-QA | [CVAT 作业即时质量反馈](https://docs.cvat.ai/docs/qa-analytics/immediate-feedback/) | CVAT | 说明验证集配置、完成作业后的质量分数及最低要求；需要分别看计算依据、能否返修和最终接受状态，不把即时分数当成无限次的答案查询。 |

## 真实素材与许可

- 视觉示例：`data/samples/000000011149.jpg`，COCO 2017 图像 11149。已实际查看，内容为街边自行车、摩托车与部分被画面截断的人，说明相邻实例和截断问题。原图未改动，单图清单 `data/samples/manifest.json` 标明 CC BY 2.0。已通过原页重定向和作者元数据核对摄影者为 Umberto Brayj（Flickr 用户 ubrayj02），[原作品页](https://www.flickr.com/photos/ubrayj02/3323418866/)随页面提供；该图是公开教学素材，不是企业街景生产批次。
- 工业示例：`data/industrial/ksdd_kos01_Part5.jpg`。已实际查看，来自 KolektorSDD。Kolektor Group d.o.o. 提供图像与标注，ViCoS Lab 发布，CC BY-NC-SA 4.0。当前用途为非商业教学；原图未改动。真实训练参考区从现有官方二元掩码派生，不能改名为裂纹或划痕子类别。许可与原图对应关系见 `data/industrial/manifest.json` 和 `data/industrial/README.md`。
- 文本与质检卡采用文字和流程示意，不使用来源不明的照片。实体和意图练习使用已存在的智基原创虚构语料，真实的是业务任务形态与可执行的训练操作，不把语料宣称为真实客户对话。
- 本次没有下载新增数据集，没有向现有 RAG 入库，没有更改正式题库、标准答案、评分器或现有知识审核结果。

## 四阶段教学与完成证据

每个任务均包含任务名称、工作情境、描述、目标、交付物、规范、质量要求、考核方式、知识与技能、相关来源，以及 `understand → prepare → practice → review` 四阶段。前两阶段帮助学生读懂任务、准备检查清单；实操阶段必须提交训练答案；复盘阶段基于实际结果记录观察证据与改进方法。

| 任务 ID | 实操技能 | 题目来源配置 | 教学考核范围 |
| --- | --- | --- | --- |
| vision-detection | A4-S4 | visual_reserve，目标类别筛选汽车/行人/自行车 | 真实场景多目标矩形标注 |
| vision-segmentation | A5-S1 | visual_reserve | 单连续区域多边形标注 |
| industrial-localization | A6-S1 | visual_reserve | 真实工业表面缺陷框选 |
| industrial-screening | A6-S4 | visual_reserve | 真实工业正负样本分类 |
| text-entities | A8-S2 | visual_reserve | 虚构文本实体片段与类型选择 |
| text-intent | A8-S4 | reviewed_reserve | 咨询、投诉、建议三类沟通意图情境判断 |
| quality-rework | A9-S5 | visual_reserve | 真实图像重新标注与结果复核教学 |
| quality-delivery | A10-S4 | reviewed_reserve | 坐标、产物、质量证据范围、问题状态和接受条件判断 |

`level_id` 保留关联课关地址，`skill_id` 明确训练技能；知识和技能卡可以跳转对应课程。现有离线初始 A6/A9/A10 课关主要为规范题，不能把课程标题当成工业图像实操已存在的证据。岗位实操由后端按上表配置创建独立训练记录，具体运行与持久化验收由实现测试提供。

教学完成不等同于生产批次交付：沟通意图与交付检查任务明确为情境判断；质检返修是重新标注与结果复核，不是完整预标注编辑器。多边形练习不覆盖孔洞、多区域掩码及完整生产工具功能。阈值由现有确定性训练规则解释，不编造某家企业的录用、交付或行业标准。

## 目录校验

本轮校验通过：4 个岗位、8 个全局唯一任务 ID、21 个来源、27 个技能映射；每个知识/技能 ID 都能在 `backend/catalog.py` 找到；每个步骤使用固定四阶段；所有关联来源存在；两张本地图片文件存在。图像已实际查看。上述校验只验证内容目录和素材，不代替后端端到端或浏览器验收。

## 实际题目与教学文案一致性复核

本轮独立调用 `backend.jobs.training_questions` 读取全部 8 个任务的实际训练快照，并核对每任务 5 题。视觉多目标首组是运动、休闲等日常人物场景，因此将标题收窄为“多目标检测试标”，不再称街景采集；封面街景示例只解释岗位方向。多边形训练包含猫和人物的单连续轮廓，与通用物体任务对应。工业定位为真实 KSDD 缺陷框，正常/异常分类包含 2 个正常和 3 个异常样本。实体练习含地点、人名、机构，均为已标明的虚构句子。

沟通意图任务实际标签为“咨询、投诉、建议”，目录明确这是当前教学项目的沟通意图粒度，不与退款、物流等业务动作标签混用。交付检查改为五类明确决策：坐标单位、产物选择、验证子集分数范围、问题位置与记录状态、分数/返修/最终接受的区别。补充实际题目对应的官方出处，不仅引用产业概述。

复核还识别出储备库中两个不适合本次岗位任务的歧义题：`QF-57aff98c3b5c5b8066136e9e` 未明确项目强制校验值，不能把 CVAT 可选 checksum 缺失直接判失败；`QF-6a6fdc010178f32e9b184aa4` 未说明图像是否为空目标，不能将缺少 YOLO 标签文件直接等同于漏交。这两个题由岗位训练选择逻辑避开，不更改全局题库或评分规则。

阅读和复盘阶段保存学生提交的学习记录，并进行最低文字完整性检查；这不代表程序或教师已经判断文字内容正确。实操阶段则必须关联本人本任务的真实已完成训练并满足现有确定性门槛。页面任务完成表示四阶段学习流程和证据已提交，不宣称全部关联知识技能已掌握。


## 固定讲解版图片与内容（2026-09-11）

本版以固定目录直接展示八项任务，不使用学生目标、学情或企业任务转换器生成页面。新增 64 段解释均为依据上述资料编写的教学文字。原任务步骤、知识技能映射和确定性评价保留。

新增三个真实 Label Studio 工作界面截图，来自 HumanSignal/label-studio 公开仓库，原图未修改：

- `public/jobs/named-entity-recognition.png`：仓库 `label_studio/core/static/templates/named-entity-recognition.png`，说明按原文片段标注实体。
- `public/jobs/intent-classification.png`：仓库 `label_studio/core/static/templates/intent-classification.png`，实际截图包含音频片段与意图选项；页面明确本任务练习中文文本单选，截图不代表平台有音频切段功能。
- `public/jobs/export-workspace.png`：仓库 `docs/themes/v2/source/images/lse-export-snapshots-ui.png`，展示导出范围和内容选择，不宣称本平台具有该工具的快照导出功能。

原始仓库：https://github.com/HumanSignal/label-studio 。许可 Apache-2.0；完整许可随图片保存在 `public/jobs/label-studio-LICENSE.txt`，原文件保留 Copyright 2019 Heartex, Inc。可在 `/jobs/label-studio-LICENSE.txt` 查看。截图中的英文是原始软件内容，中文说明写在图片旁边。图片均可点击查看原图。
