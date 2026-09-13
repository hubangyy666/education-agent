"""Authored A1 exercises, with disjoint images and explicit skill objectives.

Scenario rules are fictional teaching-project requirements, not legal or
industry-wide requirements. Geometry and image labels remain source annotations.
"""
import copy
from collections import Counter


CURRICULUM_REVISION = 'a1-skills-2026-09-13'
_GLOSSARY = 'https://labelstud.io/guide/glossary'
_TYPES = 'https://docs.cvat.ai/docs/getting_started/overview/'
_QUALITY = 'https://docs.cvat.ai/docs/qa-analytics/auto-qa/'
_REVIEW = 'https://docs.cvat.ai/docs/qa-analytics/manual-qa/'
_WORKFLOW = 'https://labelstud.io/guide/get_started'
_ACCESS = 'https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html'


def authored_choices():
    """Return seven genuinely different concepts per skill: five course, two job."""
    result = []

    def add(skill, concept, title, correct, wrong, explanation, hints, rule='', source=None):
        number = sum(q['skill_id'] == f'A1-S{skill}' for q in result) + 1
        options = [correct, *wrong]
        offset = (skill + number) % len(options)
        options = options[offset:] + options[:offset]
        result.append({
            'id': f'A1-AUTH-S{skill}-C{number}', 'type': 'choice',
            'skill_id': f'A1-S{skill}', 'title': title, 'options': options,
            'answer': correct, 'explanation': explanation, 'hint': hints,
            'project_rule': rule, 'source': '智基原创教学情境 · 公开标注概念参考',
            'source_url': source or {1: _GLOSSARY, 2: _TYPES, 3: _QUALITY,
                                      4: _WORKFLOW, 5: _ACCESS}[skill],
            'ai_generated': False, 'gt_origin': 'authored_scenario',
            'a1_curriculum_revision': CURRICULUM_REVISION,
            'authored_concept': f'A1-S{skill}:{concept}',
        })

    add(1, 'input-and-label',
        '一条教学记录包含原始猫照片，以及人工填写的“猫”类别。哪一项准确区分了输入数据与标签？',
        '照片是输入数据，“猫”是赋给数据的类别标签',
        ['“猫”是原始照片，照片是标签', '照片的文件大小就是类别标签', '照片与“猫”都属于模型参数'],
        '数据是待解释的材料，标签表达任务要求的含义；文件大小属于文件信息，不是本题类别。',
        ['先找实际被观察的材料。', '再找人工对材料含义作出的标记。', '把内容、类别与文件属性分开考虑。'])
    add(1, 'region-label-link',
        '同一张图里，左侧画了一个椅子框，右侧画了一个杯子框。标签列表中也有“椅子”和“杯子”。怎样的记录才能保留标注含义？',
        '每个框都分别关联自己的类别：左框椅子、右框杯子',
        ['只保存两个标签，不记录它们对应哪个框', '把两个标签都挂到整张图片，删除框', '只保存两个框的颜色，不保留类别'],
        '出现过哪些标签不足以说明各个区域是什么；区域与标签必须保持对应关系。',
        ['这里有两个不同对象。', '检查别人是否能知道每个框对应哪个类别。', '类别集合与逐对象对应关系不是同一信息。'])
    add(1, 'labels-not-filenames',
        '一张已确认内容为狗的照片，文件名是 cat_017.jpg。当前任务按照片中的动物类别标注，应以什么决定类别？',
        '依据照片内容与本项目类别定义，标为狗',
        ['依据文件名中的 cat，标为猫', '依据编号 017，标为第 17 类', '文件名与内容不同，所以不需要标签'],
        '文件名只是资源标识，不能代替实际内容和类别定义。此题已明确画面是狗，因此不能照抄文件名。',
        ['区分资源名称与资源内容。', '题目已说明类别判定依据。', '排除依靠编号或文件名作语义判断的做法。'])
    add(1, 'category-versus-attribute',
        '本练习的类别字段记录“汽车/自行车”，颜色字段记录“红/蓝”。观察到红色汽车，应怎样填写这两个字段？',
        '类别填汽车，颜色填红',
        ['类别填红，颜色填汽车', '两个字段都填汽车', '把类别自行扩展为“红色汽车”并留空颜色'],
        '类别说明对象是什么，属性补充对象特征；本题已给定两个字段，不能交换含义或擅自改字典。',
        ['先分别读清两个字段的用途。', '“是什么”与“具有什么特征”是两层信息。', '将观察结果放进匹配的字段。'],
        '本练习类别与颜色使用分开的字段，按给定字典填写。')
    add(1, 'unlabeled-data',
        '训练材料目录里有 80 张完整照片，但从未为它们填写类别或区域。就标注状态而言，最准确的描述是什么？',
        '已有原始图像数据，尚未形成对应的人工标注结果',
        ['没有标签就说明照片文件不存在', '只要能打开照片，就已经完成标注', '照片数量就是所有照片的类别标签'],
        '原始数据可以在标注之前存在。能读取照片只证明输入可用，不能证明类别或区域已被标出。',
        ['分别判断照片是否存在和标签是否存在。', '可打开文件与完成语义标记是不同状态。', '不要把数据量当作标注内容。'])
    add(1, 'task-identity',
        '交接表规定每条标注必须保留原图编号。两张不同照片被导出成同一个编号，尽管类别各自正确，主要丢失了什么？',
        '标注与原始数据的唯一对应关系',
        ['照片的拍摄亮度', '类别中文名称的发音', '模型训练的学习率'],
        '标签必须能回到其所属数据。编号冲突会使接收者无法可靠区分一条标注属于哪张图。',
        ['考虑接收者如何找到这条标注的原图。', '两份数据共用一个标识会造成什么歧义？', '问题在对应关系，不在类别字面是否正确。'],
        '本练习交接要求每个原图编号唯一。')
    add(1, 'negative-is-annotation',
        '本练习的整图标签只有“有汽车”和“无汽车”。一张完整检查过、没有汽车的照片，应保留什么记录？',
        '保留照片，并将它的类别记录为“无汽车”',
        ['没有汽车就删除照片，不能形成标签', '为了有标签，随意圈出一块背景作为汽车', '只写照片尺寸，替代类别结果'],
        '“无汽车”也是本项目明确的类别结果；没有目标不等于没有数据或不能标注。',
        ['读清字典是否包含没有目标的情况。', '负例也能表达明确的任务含义。', '不要为了产生对象而虚构目标。'],
        '本练习为二分类，检查后的无目标图使用“无汽车”标签。')

    add(2, 'image-classification',
        '相册整理任务只需要给每张照片选一个“室内/室外”标签，不要求指出具体物体的位置。最匹配哪种任务？',
        '整图分类', ['目标检测', '实例分割', '文本实体标注'],
        '输出单位是一整张图的类别，不要求对象框或轮廓，因此属于整图分类。',
        ['先看最终结果对应整图还是局部对象。', '题目没有要求坐标或轮廓。', '选择能直接产出整图类别的任务。'])
    add(2, 'object-detection',
        '盘点人员需要知道每把椅子在哪里，并要求每把椅子有独立矩形框和类别。应安排哪种任务？',
        '目标检测标注', ['只给整张图一个“有椅子”标签', '逐字转写音频', '只给照片打清晰度分'],
        '每个对象的位置与类别共同构成检测结果；整图有无标签不能说明各把椅子的位置。',
        ['留意“每把”和“独立矩形框”。', '这个输出同时回答对象是什么和在哪里。', '只给整图标签会遗漏题目要求的位置。'])
    add(2, 'segmentation',
        '抠图任务需要沿动物外轮廓区分前景与背景，矩形里的大块背景不能算作动物。哪种输出更符合需求？',
        '描述动物边界的分割区域', ['只给出动物类别名称', '只记录图片拍摄时间', '将整张图片统一标成动物'],
        '分割表达对象的区域边界；类别名称不含区域，整图统一赋值也无法区分前景背景。',
        ['观察任务是否要求细致的空间边界。', '矩形周围的背景为什么不能一起算入？', '选择能描述前景区域的结果类型。'])
    add(2, 'text-entity',
        '文本任务要求在“李华去杭州出差”中选出“杭州”这段原文，并标记为地点。它属于哪类标注？',
        '文本实体标注', ['整句情感分类', '图像目标检测', '音频说话人分段'],
        '实体标注同时指定文本片段与类型，本题的结果是“杭州”的片段边界和地点类型。',
        ['先确认输入材料是什么。', '结果针对整句还是句中一段名称？', '片段范围与实体类型需要一起保留。'],
        source='https://labelstud.io/templates/named_entity.html')
    add(2, 'sentence-classification',
        '客服教学任务只需把“请帮我查快递进度”整句归为“物流查询”，不选择句中片段。这是什么任务？',
        '句子意图分类', ['文本实体边界标注', '图像实例分割', '目标轨迹标注'],
        '任务对整句表达的目的赋类别，属于意图分类；并未要求选出人名、地点等文本片段。',
        ['标签表达的是用户想完成的事。', '题目明确不选择文本片段。', '区分整句分类与实体范围标注。'],
        source='https://labelstud.io/templates/slot_filling.html')
    add(2, 'semantic-versus-instance',
        '路面图片里两辆相邻汽车都需要区域边界，而且后续必须分别统计两辆车。与仅区分“汽车像素/背景”相比，还需要什么？',
        '为两辆车保留各自独立的实例区域',
        ['只保存全图一个汽车标签', '把所有汽车区域合成一个不可区分的对象', '删除边界，只保存两种颜色'],
        '同类像素的语义类别不能单独表达是哪一辆车；逐实例区域保留了两个对象的区分。',
        ['注意后续要分别统计两个对象。', '相同类别不意味着同一个实例。', '检查输出是否还能分清第一辆和第二辆。'])
    add(2, 'polyline-output',
        '本练习要求记录一段道路中心线的走向，不测量道路覆盖的完整面积。哪一种几何结果最合适？',
        '沿中心线排列的折线', ['包住道路的一个矩形', '整张图的场景类别', '封闭的整幅图像边界'],
        '折线用于表达线状对象或路径；本题明确要中心线走向，不能用整图类别或外包矩形替代。',
        ['区分线的位置和面的范围。', '题目需要的是沿路延伸的路径。', '选择能够保留路径弯折的几何形状。'],
        '本题仅要求记录道路中心线走向，不要求覆盖道路面积。')

    add(3, 'reference-purpose',
        '质检练习保存了一份经审核的参考标注。学习者提交后，系统将其与参考比较。这份标准答案主要承担什么作用？',
        '提供本练习计算差异和反馈的参考依据',
        ['保证训练出的模型永不出错', '证明所有未检查图片都已经合格', '自动替代后续所有项目的规范'],
        '标准答案提供当前任务下可比较的参考，但不能保证模型表现，也不能替代其他项目定义。',
        ['关注系统实际比较的两份结果。', '参考的适用范围是这道练习。', '排除把局部参考扩大为永久保证的选项。'])
    add(3, 'prediction-not-gold',
        '模型给一张图生成了预测框，尚无人核对。项目规定只有核对通过的标注才可列入参考集。现在这份预测应如何看待？',
        '它是待核对的建议，暂不能按该项目规则当作标准答案',
        ['因为模型置信度高，所以已经是标准答案', '只要框能显示，就可以跳过核对', '任何预测框都没有检查价值，必须永久丢弃'],
        '预测的生成方式不等于审核结论；能作为参考与否，要满足本题明确的核对要求。',
        ['先辨认预测与审核这两个环节。', '题目给出了进入参考集的条件。', '查看条件是否已经满足。'],
        '本练习项目只有核对通过的标注才进入参考集。')
    add(3, 'reference-disagreement',
        '两份标为“参考”的答案对同一物体给出不同类别。项目要求分歧由负责人复核定稿。此时应怎样确定判分依据？',
        '记录分歧及对应样本，复核定稿后使用确认的参考',
        ['任选较早打开的一份当作唯一真值', '哪份更接近自己的答案就用哪份', '把两种冲突类别无条件都判正确'],
        '参考冲突需要明确的复核结论；随意选择或迁就作答会让评价失去共同依据。',
        ['当前是否已有唯一、确认的判定依据？', '题目已指定由谁处理分歧。', '避免按个人便利选择参考。'],
        '本练习的参考分歧交负责人复核定稿。', source=_REVIEW)
    add(3, 'reference-version',
        '规范 V1 规定只标最大杯子，V2 改为标全部杯子。本次练习明确使用 V2，已有两版参考。应使用哪份？',
        '使用依照 V2 生成并确认的全部杯子参考',
        ['使用 V1，因为旧版总是更权威', '把 V1 的部分参考与 V2 题干随意组合', '只改参考文件名为 V2，内容不必核对'],
        '参考必须对应当前题目的目标范围。版本名称相同还不够，参考内容也要与所用规则一致。',
        ['先比较两个版本的目标范围。', '本次明确采用的是哪一版？', '检查规则与实际参考内容是否一致。'],
        '本次教学练习使用已确认的 V2 规则。')
    add(3, 'reference-error',
        '学习者发现一份参考框明显套在背景上，而题目要求标椅子。项目允许提交参考疑点并由维护者复核。合理做法是什么？',
        '附上样本与疑点说明，申请复核参考，确认后按流程修正',
        ['标准答案不可能出错，不需要核对', '为了跟参考一致，今后总把背景当椅子', '自行修改其他人的历史成绩来消除差异'],
        '标准答案也是需要维护的标注。具体疑点应可追踪地复核，不能把明显异常变成新规则。',
        ['将题目要求、图像内容和参考放在一起检查。', '题目是否提供了参考疑点处理渠道？', '保留证据比盲从或擅自改历史记录更合适。'],
        '本练习允许提出参考疑点，参考修订须经维护者确认。', source=_REVIEW)
    add(3, 'reference-has-semantics',
        '本练习要求框和标签都正确。作答框与参考框完全重合，但把参考中的“杯子”选成了“椅子”。能据此说整题已符合标准答案吗？',
        '不能，位置符合参考但类别不符合',
        ['能，只要框重合，标签就没有意义', '能，只要两个标签都是名词', '不能，因为任何完全重合的框都无效'],
        '参考包含几何位置和类别两个维度；只在一个维度相符不代表完整标注正确。',
        ['列出本题要求同时正确的内容。', '分别比较几何位置与类别。', '不要用一项符合掩盖另一项不符。'],
        '本练习框的位置与类别均须符合参考。')
    add(3, 'reference-scope',
        '一批 100 张图片中，只有指定的 10 张具有已确认参考。学习者在这 10 张上全部与参考一致，可以直接证明什么？',
        '这 10 张的作答与所用参考一致',
        ['其余 90 张也已逐张通过核对', '所有未来图片都不再需要检查', '该参考能覆盖所有其他项目类别'],
        '比较证据只直接覆盖有参考且实际核对的样本，不能把子集结果当成全部图片逐张通过的证明。',
        ['先数清实际参与参考比较的图片。', '区分已观察结果与未检查部分。', '结论的范围应与证据范围相同。'])

    add(4, 'prepare-before-labeling',
        '新练习已经提供任务说明和标签字典，但标注员还没有阅读。项目流程要求理解规范后再试标，当前首先应做什么？',
        '阅读任务说明，确认目标范围和标签定义',
        ['直接复制上一项目的标签开始生产', '立即导出尚不存在的标注结果', '先把困难样本全部删除'],
        '流程前置步骤尚未完成，应先明确本批任务要求；直接开始会把未经确认的习惯带入新项目。',
        ['定位现在处于哪一步。', '找出开始试标前的前置要求。', '选择补齐前置准备的动作。'],
        '本练习流程为理解规范后试标。')
    add(4, 'configure-before-entry',
        '项目已建好且图像已导入，但标注界面还没有配置标签和任务类型。负责人下一步应准备什么，才能让标注员按要求开始？',
        '配置并核对当前项目的标注界面与标签',
        ['把空标注作为完成结果导出', '先宣告审核通过再补标签', '将尚未标注的图像标记为已完成'],
        '导入数据与配置可执行的标注界面是不同准备工作；缺少任务类型和标签时，开始标注的条件不齐。',
        ['哪些准备已完成，哪些仍缺失？', '标注员需要用什么标签与操作类型？', '下一步应补足能实际操作的配置。'],
        source='https://labelstud.io/guide/setup')
    add(4, 'self-check-next',
        '本练习流程为“标注 → 自检 → 提交审核”。一批框已画完、尚未检查漏标或类别，当前下一步是什么？',
        '先自检范围、标签和边界，再提交审核',
        ['跳过自检直接宣布交付完成', '马上重新创建项目并丢弃本批结果', '进入归档环节并关闭所有问题'],
        '本题明确自检位于标注和审核之间。画完只是当前步骤的产出，还未完成后续检查。',
        ['对照题目列出的顺序。', '画完与检查完是不是同一状态？', '选择紧邻当前阶段的动作。'],
        '本练习采用标注、自检、提交审核的顺序。')
    add(4, 'saved-versus-reviewed',
        '任务界面显示“已保存，待审核”。本练习规定审核员确认后才算审核通过。这条状态说明什么？',
        '标注已经保存，但还没有得到审核通过结论',
        ['保存按钮已经代替审核员完成审核', '待审核表示原始图片一定不存在', '已保存表示可以跳过后续所有环节'],
        '保存确认数据写入，审核结论属于后续环节；两种状态不能互相代替。',
        ['分别理解“已保存”和“待审核”。', '题目由谁确认审核通过？', '查看该确认是否已发生。'],
        '本练习审核通过需要审核员确认。', source=_REVIEW)
    add(4, 'rework-loop',
        '一条任务因标签错误被退回。标注员已改正并完成自检。本练习要求所有退回任务重新审核，接下来应怎样流转？',
        '将修正结果重新提交给审核环节',
        ['标注员自行宣告审核通过', '删除退回记录，假装从未有问题', '保持旧错误结果并直接归档'],
        '修正解决作答问题，重新审核确认修正结果；返修闭环应保留问题与处理关系。',
        ['区分修正者与确认修正结果的人。', '题干是否允许修正后直接跳过审核？', '选择回到明确审核环节的流转。'],
        '本练习所有退回任务在改正后重新审核。', source=_REVIEW)
    add(4, 'stage-state-assignee',
        '作业卡显示“阶段：审核；状态：进行中；负责人：质检员”。本练习中标注员已经提交此作业。当前主要工作是什么？',
        '由质检员在审核阶段检查已提交的结果',
        ['由标注员把进行中直接改成已交付', '重新导入原图，代替审核结果', '把审核阶段解释为尚未配置标签'],
        '阶段说明工作环节，状态说明当前进展，负责人说明执行角色；应结合三个字段理解当前任务。',
        ['分别读取阶段、状态与负责人。', '“进行中”需要结合哪个阶段解释？', '不要把审核中的作业误读为尚未标注。'],
        source='https://docs.cvat.ai/docs/workspace/jobs-page/')
    add(4, 'export-after-acceptance',
        '本练习流程要求审核通过后再导出交接。当前整批任务已经审核通过，但尚未生成交接文件。下一步应是什么？',
        '按已约定的输出要求导出审核通过的结果并交接',
        ['把审核通过重新解释为原图导入完成', '跳过导出，声称接收方已经收到文件', '清空所有标注后再交接空目录'],
        '审核通过是质量环节的结果，导出交接是后续产出环节；尚未生成和交接文件时不能假定已经交付。',
        ['当前已完成的是哪个环节？', '接收方还缺少哪项实际产出？', '选择题目流程中的下一步。'],
        '本练习审核通过后按约定导出并交接。')

    add(5, 'least-access',
        '本练习只授权你处理任务包甲。另一个目录里的任务包乙能够打开，但没有分配给你。应怎样使用数据？',
        '只处理已授权的甲，若确需乙则先申请并获得授权',
        ['能够打开就代表可以任意使用乙', '先复制乙到个人设备，再补问是否允许', '把乙分享给同学，让大家一起判断权限'],
        '技术上可访问与项目授权范围不同；本题明确只有甲得到授权，不能把可打开当作新增许可。',
        ['区分可访问状态与明确授权。', '题目把哪个任务包分配给了你？', '使用额外材料需要满足什么前提？'],
        '本练习仅授权处理任务包甲，访问其他包须另获批准。')
    add(5, 'approved-processing',
        '本练习规定原图只能在批准的项目环境内处理。你想把原图上传到个人使用的外部识图网站求建议，应怎样做？',
        '继续在批准环境内处理；需要外部服务时先取得明确批准',
        ['只上传一张就不受环境限制', '将文件名改掉后可直接上传', '对方是智能网站，所以天然获得项目授权'],
        '外部服务属于新的数据接收和处理环境。文件数量或名称变化不会自动满足本题的环境授权要求。',
        ['外部网站是否在题目给出的批准范围？', '改文件名是否改变图像内容和接收方？', '先检查环境授权条件是否满足。'],
        '本练习原图仅允许在批准的项目环境处理，外部服务须另获批准。')
    add(5, 'authorized-recipient',
        '项目规则只允许将标注结果交给指定接收人，且本次交接不含原图。收到一封陌生地址来信索要“原图和标注”，应如何处理？',
        '先通过项目指定渠道核实接收人和范围，不向陌生地址发送',
        ['来信写了项目名，就把原图和标注一起发出', '只要压缩包加密码，任何接收人都可以', '发送后再询问是否有权限'],
        '接收方身份和允许交付的内容都必须符合本题规则；加密不能替代接收授权。',
        ['分别核对接收方和可发送内容。', '本题允许的交接是否含原图？', '传输保护与授权范围不是同一条件。'],
        '本练习仅向指定接收人交付标注结果，不交付原图。')
    add(5, 'license-distinction',
        '公开数据页分别列出了图片使用条件和标注文件使用条件。本练习要求复用前分别核对两者。准备把图片连同标注用于新项目，应先做什么？',
        '分别核对原图与标注条件，以及新项目用途是否在允许范围内',
        ['只看标注文件条件，并认定图片条件相同', '只要能下载，就不必考虑任何使用条件', '去掉来源名称就能扩大许可用途'],
        '公开可获取不等于所有组成部分具有相同使用条件。本练习要求分开核对，不能从标注许可推断原图许可。',
        ['图片与标注是否被分别列出条件？', '能下载与能按某用途复用是否等同？', '逐项核对实际用途和对应条件。'],
        '本练习要求分别核对原图与标注使用条件，不推定二者相同。',
        source='https://cocodataset.org/#termsofuse')
    add(5, 'incidental-personal-data',
        '本练习仅授权标椅子，不允许记录人物身份。图中碰巧有清晰人脸，有同学建议顺便写下人物姓名，应如何处理？',
        '按授权只完成椅子标注，不额外识别或记录人物身份',
        ['能看清人脸就自动获得识别姓名的授权', '将人脸截图发到社交平台询问姓名', '把人物姓名作为椅子的标签保存'],
        '能观察到某类信息不代表可以扩展用途；本题的授权对象和禁止额外记录的范围已经明确。',
        ['任务指定对象是什么？', '姓名信息是否为完成当前任务所需且获授权？', '不要把可见信息全部转成额外标注。'],
        '本练习仅标椅子，不识别、不记录人物身份。')
    add(5, 'incident-response',
        '本练习规定误发数据后立即联系项目负责人，记录接收方并按指示止损。你发现原图误发到未授权群聊，首先应采取什么措施？',
        '立即报告误发情况，记录接收范围，并按项目指示停止扩散',
        ['不报告，等项目结束自然失效', '再发到其他群，询问是否有人看见', '只修改原文件名，就当没有误发'],
        '本题已有明确的误发处理规则；及时报告和停止扩散能让负责人依据事实处理，不应继续扩大接收范围。',
        ['先找题目指定的误发处理步骤。', '哪些做法会扩大而不是限制传播？', '报告应包括可追踪的接收范围。'],
        '本练习误发后立即报告负责人，记录接收方，按指示止损。')
    add(5, 'retention-purpose',
        '本练习只批准在项目期内使用任务副本，结束后按负责人清单清理，原始档案由项目库保管。项目结束时如何处理个人任务副本？',
        '按批准的清理清单处理副本，不自行留作其他用途',
        ['永久保留所有副本，用于个人作品展示', '自行删除项目库原始档案以证明已清理', '转存到个人网盘就不算继续保留'],
        '本题区分个人任务副本与项目库原始档案。应按既定保留和清理范围执行，不能扩大用途或擅自删除原始档案。',
        ['先区分任务副本与由项目保管的原始档案。', '批准使用期限是否已经结束？', '清理动作必须符合指定对象和清单。'],
        '本练习项目结束后按负责人清单清理任务副本，原始档案由项目库保管。')
    return result


def _sample_key(sample):
    identity = str(sample['id'])
    return (0, int(identity)) if identity.isdigit() else (1, identity)


def authored_visuals():
    """Partition source images once, then make skill-specific existing box tasks.

    Every image belongs to one skill, including reserve images used by refresh.
    Allocation is deterministic and greedily diversifies the first six images
    of each skill. S5 selects non-person targets whenever present in a source.
    """
    from .factory import samples
    from .visual_reserve import make_question, sample_hash
    from .db import ROOT
    from .grading import valid_box

    available = []
    seen = set()
    for sample in sorted(samples(), key=_sample_key):
        targets = sample.get('targets', [])
        if not targets or not all(valid_box(t['box']) for t in targets):
            continue
        if not (ROOT / 'data/samples' / sample['file']).is_file():
            continue
        digest = sample_hash(sample['file'])
        if digest in seen:
            continue
        seen.add(digest)
        available.append(sample)

    partitions = {i: [] for i in range(1, 6)}
    labels = {i: Counter() for i in partitions}

    def source_target(sample, skill):
        candidates = sample['targets']
        if skill == 5:
            candidates = [t for t in candidates if t['label'] != '行人'] or candidates
        return max(candidates, key=lambda t: t['box'][2] * t['box'][3])

    # S5 takes first pick within a round to protect its restricted-object task.
    while available:
        for skill in (5, 1, 2, 3, 4):
            if not available:
                break
            sample = min(available, key=lambda s: (
                skill == 5 and source_target(s, skill)['label'] == '行人',
                labels[skill][source_target(s, skill)['label']], _sample_key(s)))
            partitions[skill].append(sample)
            labels[skill][source_target(sample, skill)['label']] += 1
            available.remove(sample)
    if any(len(group) < 6 for group in partitions.values()):
        raise ValueError('A1 每个技能至少需要 6 张互不重复的有效图片')

    result = []
    for skill, group in partitions.items():
        for number, sample in enumerate(group, 1):
            target = source_target(sample, skill)
            # Restrict eligible source targets without altering source geometry.
            scoped = dict(sample, targets=[t for t in sample['targets'] if t['label'] == target['label']])
            q = make_question(scoped, 'A1', skill, 'largest', 'box')
            if not q:
                raise ValueError(f'A1 标注参考无法执行：{sample["id"]}')
            label = target['label']
            target_text = f'图中最大的{label}'
            if skill == 1:
                title = f'建立数据与标签的对应：为{target_text}画一个框，并把正确类别关联到这个框。'
                rule = '本图是原始数据，框表示其中一个对象，类别说明这个对象是什么；只提交指定对象的一个带标签框。'
                explanation = f'本题练习原图、对象区域与类别的对应。参考框关联的类别是“{label}”；只有类别或只有框都不构成完整对象标注。'
                hints = ['先分清整张原图与题目指定的对象。', '用一个框表示这个对象，避免把相邻对象合并。', '最后检查所选类别是否确实关联在这个对象框上。']
            elif skill == 2:
                title = f'完成目标检测产物：本题同时需要“是什么”和“在哪里”。请为{target_text}提交一个矩形框与类别。'
                rule = '这是单对象检测练习，输出一个带类别的矩形；整图分类标签不能替代对象位置，不需要描绘多边形轮廓。'
                explanation = '本题用实际产物区分检测与分类、分割：检测结果须同时包含对象位置和类别，框来自该图官方参考。'
                hints = ['先确认本题需要位置和类别两项信息。', '选择矩形框作为本题指定的空间表示。', '检查是否既有完整对象范围，又有对应类别。']
            elif skill == 3:
                title = f'练习与标准答案对照：本题已保存该图的官方参考。请先独立框出{target_text}并选择类别，提交后根据反馈核对。'
                rule = '只标指定的一个对象。本题参考依据为此图的 COCO 官方标注；独立完成后比较对象、类别和边界，不把个人猜测当作新的参考。'
                explanation = f'此题的标准答案由该图已有官方标注选取，包含“{label}”类别与目标框。对照反馈时要分别检查目标选取、类别和位置；参考并非模型现场生成。'
                hints = ['先按题目指定范围独立观察，不猜测标准坐标。', '确认选中的是指定类别中的最大对象。', '检查类别和四周边界，提交后再以反馈定位差异。']
            elif skill == 4:
                title = f'完成当前标注步骤：任务说明已确认、图片已导入，你负责标注阶段。现在请框出{target_text}并选择类别。'
                rule = '本练习阶段为准备→标注→自检→审核；当前只需完成本图指定对象的标注，保存前检查框与标签，不能把保存视为审核通过。'
                explanation = '本题把画框放在明确的工作阶段：准备已完成，当前产物是带类别的对象框。提交标注不等于完成审核或对外交接。'
                hints = ['先定位作业目前所处的标注阶段。', '完成该阶段要求的对象框和标签。', '保存前自检范围与类别，区分标注产出和审核结论。']
            else:
                title = f'按授权对象范围操作：本练习只授权标注{target_text}。请为这个对象画框并选择类别，不额外记录画面中的其他信息。'
                rule = f'本题授权用途仅为指定{label}对象的框选练习；其他对象与人物身份信息均不在记录范围。'
                explanation = '只提交获授权对象的类别与框，不因看见其他信息就扩大记录用途。观察得到的信息也应按任务范围处理，不额外识别或记录人物身份。'
                hints = ['先读清本题明确授权的对象与用途。', '只定位指定对象，不为无关人物或物体增加记录。', '提交前核对是否只有任务要求的一个对象框。']
            q.update(id=f'A1-AUTH-S{skill}-I{sample["id"]}', title=title,
                     project_rule=rule, explanation=explanation, hint=hints,
                     a1_curriculum_revision=CURRICULUM_REVISION,
                     authored_concept=f'A1-S{skill}:visual-application',
                     skill_rationale={1: '将原图、对象区域和类别建立正确关联。',
                                      2: '用框与类别实际完成目标检测产物。',
                                      3: '独立标注后依据固定来源参考核对结果。',
                                      4: '在给定工作阶段内完成对应的标注产物。',
                                      5: '执行本题明确的授权对象和处理用途范围。'}[skill])
            result.append(q)
    return result


def generate_pool(version=1):
    """Build 65 A1 questions, with 13 per skill and no repeated source image."""
    from .catalog import levels
    from .factory import validate, validate_visual_layout

    choices = {f'A1-S{i}': [] for i in range(1, 6)}
    visuals = {sid: [] for sid in choices}
    for q in authored_choices():
        choices[q['skill_id']].append(q)
    for q in authored_visuals():
        visuals[q['skill_id']].append(q)
    pool = {}
    for lv in levels('A1'):
        if lv['mode'] == 'course':
            sid = lv['skill_id']
            questions = visuals[sid][:2] + choices[sid][:5]
        elif lv['mode'] == 'job':
            questions = ([visuals[f'A1-S{i}'][j] for j in (2, 3) for i in range(1, 6)] +
                         [choices[f'A1-S{i}'][j] for j in (5, 6) for i in range(1, 6)])
        else:
            questions = [visuals[f'A1-S{i}'][j] for j in (4, 5) for i in range(1, 6)]
        pool[lv['id']] = copy.deepcopy(questions)
        for index, question in enumerate(pool[lv['id']], 1):
            question['id'] = f'{lv["id"]}-V{version}-Q{index}'
            question['instruction'] = ('先观察，再判断。需要帮助时可以向小基要一点提示。'
                                       if lv['mode'] == 'course' else '按本题任务说明独立完成作答。')
    validate(pool, 'A1')
    validate_visual_layout(pool, 'A1')
    return pool
