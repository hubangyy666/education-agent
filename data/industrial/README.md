# 智基 A6 工业表面缺陷小样本

2026-09-10 从官方 ViCoS 服务器提取 KolektorSDD 子集：**10 张缺陷正例、2 张无缺陷负例，以及每张图对应的官方像素掩码**。来源页面说明这些图像和标注由 Kolektor Group 提供，拍摄于真实工业环境。原数据包含 399 张图像，其中 52 张有缺陷。[ViCoS 官方数据页](https://www.vicos.si/resources/kolektorsdd/)

## 文件

- `samples/`：12 张原始 JPG + 12 张原始 BMP GT，文件字节保持不变。
- `manifest.industrial.positive.json`：10 张正例，适用于现有 `image_question` 的非空 targets 要求。
- `manifest.industrial.negative.json`：2 张负例，targets 为空，需使用“无缺陷”分类或空目标判分流程。
- `manifest.industrial.json`：完整 12 条兼容记录。
- `contact-sheet.png`：人工核对用缺陷区域裁剪与官方 mask 并排图。只有这张预览图经过裁剪缩放，训练 JPG 未改变。
- `download-provenance.json`：官方 archive URL、各次字节范围、下载量、每个原始文件 SHA-256、GT 像素数。
- `golden-validation.json`：10 张正例均通过当前生产框和 Polygon 判分器。
- `mask-reconstruction-validation.json`：10 个派生 Polygon 在原分辨率像素中心重建，均与官方二值 mask 达到 IoU=1.0。
- `collect_ksdd.py`、`verify_subset.py`：可复现的采集与验证代码。

## 许可和署名

官方数据页明确授权 **CC BY-NC-SA 4.0**。允许符合条款的共享与改编，要求署名、链接许可、说明改动、非商业使用；改编内容以相同许可共享。商业用途需另行联系权利人。[官方许可说明](https://www.vicos.si/resources/kolektorsdd/)、[CC BY-NC-SA 4.0 条款摘要](https://creativecommons.org/licenses/by-nc-sa/4.0/)

建议随 A6 素材展示以下署名：

> KolektorSDD，图像与标注由 Kolektor Group d.o.o. 提供，ViCoS Lab 发布。CC BY-NC-SA 4.0。智基由原始像素掩码派生外轮廓和紧致边界框；原始图像与掩码保持不变。

引用论文：Domen Tabernik, Samo Šela, Jure Skvarč, Danijel Skočaj. *Segmentation-Based Deep-Learning Approach for Surface-Defect Detection*. Journal of Intelligent Manufacturing, 2019. [DOI](https://doi.org/10.1007/s10845-019-01476-x)

## GT 派生与接入

官方标注为二元缺陷掩码，不提供独立“裂纹/划痕”子类别，因此所有正例的 label 忠实命名为“表面缺陷”。目标区域从 mask 非零像素的连通外轮廓提取；box 使用该区域紧致包围框；坐标按原图宽高归一化。所有选中正例均只有一个外轮廓、没有孔洞。记录明确带有 `annotation_origin`，没有把本地派生的框或 Polygon 伪称为原档自带格式。

记录还带有 `dataset: KolektorSDD` 与 `ability_ids: [A6]`。接入时按此字段限定为 A6 的工业样本。现有工厂对 targets 取 max；负例应使用单独逻辑，不能传入该 max 路径。

官方压缩包地址由数据页下载链接重定向获得：`https://data.vicos.si/datasets/KSDD/KolektorSDD.zip`。完整包为 101,831,129 字节，未整包下载。本脚本使用公开服务器支持的 HTTP Range，仅提取选中条目及目录，采集运行传输了 **3,266,496 字节**；每个选中 ZIP 条目均核对 CRC32，再保存 SHA-256。不使用第三方镜像。

所有文件仅写入本临时目录，没有修改项目、数据库或对象存储。资料足以提供真实 A6 图像训练；是否发布到商业场景需遵照上述非商业许可。
