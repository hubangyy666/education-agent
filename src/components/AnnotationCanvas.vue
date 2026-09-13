<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Icon from './Icon.vue'
import { cloneBoxes, drawBox, moveBox, resizeBox, replaceBox } from './annotationGeometry'
import type { AnnotationBox, ResizeHandle } from './annotationGeometry'

const props = withDefaults(defineProps<{ question: any; modelValue: any; guide?: boolean; findOnly?: boolean; labelsVisible?: boolean; disabled?: boolean; standard?: any }>(), { guide: false, findOnly: false, labelsVisible: true, disabled: false })
const emit = defineEmits(['update:modelValue', 'spot'])
const surface = ref<HTMLElement>(), selected = ref(-1), label = ref(''), tool = ref<'draw' | 'select'>('draw')
const draft = ref<number[] | null>(null), preview = ref<number[] | null>(null), poly = ref<number[][]>([]), closed = ref(false), zoom = ref(1), imageError = ref(false)
const history = ref<any[]>([])
const boxes = computed<AnnotationBox[]>(() => props.modelValue?.boxes || [])
const isPolygon = computed(() => props.question.type === 'polygon')
// A standard answer is always a viewing state, even if a caller forgets disabled.
const showingStandard = computed(() => props.standard !== undefined && props.standard !== null)
const readOnly = computed(() => props.disabled || showingStandard.value)
const activeLabel = computed(() => isPolygon.value ? label.value : boxes.value[selected.value]?.label ?? label.value)
const displayBoxes = computed(() => preview.value && drag ? replaceBox(boxes.value, drag.index, preview.value) : boxes.value)
const orderedBoxes = computed(() => displayBoxes.value.map((box, index) => ({ ...box, index })).sort((a, b) => Number(a.index === selected.value) - Number(b.index === selected.value)))
const selectedBox = computed(() => displayBoxes.value[selected.value]?.box)
const canUndo = computed(() => history.value.length > 0)
const handles: { id: ResizeHandle; title: string; x: number; y: number }[] = [
  { id: 'nw', title: '左上角', x: 0, y: 0 }, { id: 'n', title: '上边界', x: .5, y: 0 },
  { id: 'ne', title: '右上角', x: 1, y: 0 }, { id: 'e', title: '右边界', x: 1, y: .5 },
  { id: 'se', title: '右下角', x: 1, y: 1 }, { id: 's', title: '下边界', x: .5, y: 1 },
  { id: 'sw', title: '左下角', x: 0, y: 1 }, { id: 'w', title: '左边界', x: 0, y: .5 },
]
type Drag = { pointerId: number; action: 'draw' | 'move' | 'resize'; index: number; start: number[]; original: number[]; before: AnnotationBox[]; handle?: ResizeHandle }
let drag: Drag | null = null
const snapshot = (value: any) => JSON.parse(JSON.stringify(value))

watch(() => props.question.id, () => {
  cancelDrag(); selected.value = -1; label.value = ''; poly.value = []; closed.value = false
  zoom.value = 1; imageError.value = false; history.value = []; tool.value = 'draw'
})
watch(() => props.modelValue, value => {
  if (isPolygon.value) {
    poly.value = (value?.points || []).map((point: number[]) => [...point])
    label.value = value?.label || ''
    if (!poly.value.length) closed.value = false
    else if (readOnly.value) closed.value = poly.value.length >= 3
  } else {
    if (selected.value >= boxes.value.length) selected.value = -1
  }
}, { immediate: true })
// A guided label step remounts with the box from the preceding drawing step.
if (!isPolygon.value && boxes.value.length === 1) { selected.value = 0; tool.value = 'select' }
watch(readOnly, value => { if (value) cancelDrag() })

function coord(event: PointerEvent) {
  const bounds = surface.value!.getBoundingClientRect()
  return [Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)), Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height))]
}
function save(value: any, previous = props.modelValue || {}) {
  if (readOnly.value || JSON.stringify(previous) === JSON.stringify(value)) return
  history.value.push(snapshot(previous))
  emit('update:modelValue', snapshot(value))
}
function setTool(value: 'draw' | 'select') {
  if (readOnly.value) return
  cancelDrag(); tool.value = value
  if (value === 'draw') selected.value = -1
  surface.value?.focus({ preventScroll: true })
}
function selectBox(index: number, focus = true) {
  if (readOnly.value || !boxes.value[index]) return
  cancelDrag(); selected.value = index; tool.value = 'select'
  if (focus) surface.value?.focus({ preventScroll: true })
}
function down(event: PointerEvent, index = -1, handle?: ResizeHandle) {
  if (readOnly.value || drag || event.button !== 0 || event.isPrimary === false) return
  event.preventDefault()
  surface.value?.focus({ preventScroll: true })
  const point = coord(event)
  if (props.findOnly) { emit('spot', point); return }
  if (isPolygon.value) {
    if (closed.value) return
    const points = [...poly.value, point]
    save({ points, label: label.value }); poly.value = points
    return
  }
  if (tool.value === 'select' && index < 0) { selected.value = -1; return }
  const action = tool.value === 'draw' ? 'draw' : handle ? 'resize' : 'move'
  const targetIndex = action === 'draw' ? -1 : index
  if (action !== 'draw' && !boxes.value[targetIndex]) return
  selected.value = targetIndex
  drag = { pointerId: event.pointerId, action, index: targetIndex, start: point, original: targetIndex < 0 ? [] : [...boxes.value[targetIndex].box], before: cloneBoxes(boxes.value), handle }
  if (action === 'draw') draft.value = [...point, 0, 0]
  surface.value?.setPointerCapture(event.pointerId)
}
function move(event: PointerEvent) {
  if (!drag || drag.pointerId !== event.pointerId || readOnly.value) return
  const point = coord(event), dx = point[0] - drag.start[0], dy = point[1] - drag.start[1]
  if (drag.action === 'draw') draft.value = drawBox(drag.start, point)
  else preview.value = drag.action === 'move' ? moveBox(drag.original, dx, dy) : resizeBox(drag.original, drag.handle!, dx, dy)
}
function up(event: PointerEvent) {
  if (!drag || drag.pointerId !== event.pointerId) return
  if (readOnly.value) { cancelDrag(); return }
  move(event)
  const current = drag
  if (current.action === 'draw' && draft.value && draft.value[2] > .003 && draft.value[3] > .003) {
    save({ boxes: [...current.before, { box: [...draft.value], label: label.value }] }, { boxes: current.before })
    selected.value = current.before.length; tool.value = 'select'
  } else if (current.action !== 'draw' && preview.value) {
    save({ boxes: replaceBox(current.before, current.index, preview.value) }, { boxes: current.before })
  }
  cancelDrag()
}
function cancelDrag(event?: PointerEvent) {
  if (event && drag && event.pointerId !== drag.pointerId) return
  const pointerId = drag?.pointerId
  drag = null; draft.value = null; preview.value = null
  if (pointerId !== undefined && surface.value?.hasPointerCapture(pointerId)) surface.value.releasePointerCapture(pointerId)
}
function chooseLabel(value: string) {
  if (readOnly.value) return
  if (isPolygon.value) {
    save({ points: poly.value, label: value }); label.value = value
  } else if (selected.value >= 0 && boxes.value[selected.value]) changeBoxLabel(selected.value, value)
  else label.value = value
}
function changeBoxLabel(index: number, value: string) {
  if (readOnly.value || !boxes.value[index]) return
  selectBox(index, false)
  save({ boxes: boxes.value.map((box, i) => ({ box: [...box.box], label: i === index ? value : box.label })) })
}
function remove() {
  if (readOnly.value) return
  cancelDrag()
  if (isPolygon.value) { save({ points: [], label: label.value }); poly.value = []; closed.value = false }
  else if (selected.value >= 0) {
    save({ boxes: boxes.value.filter((_, index) => index !== selected.value) })
    selected.value = -1
    if (boxes.value.length <= 1) tool.value = 'draw'
  }
}
function clearAllBoxes() {
  if (readOnly.value || isPolygon.value || !boxes.value.length) return
  cancelDrag(); save({ boxes: [] }); selected.value = -1; label.value = ''; tool.value = 'draw'
}
function undo() {
  if (readOnly.value) return
  if (drag) { cancelDrag(); return }
  if (!history.value.length) return
  const previous = history.value.pop()
  emit('update:modelValue', snapshot(previous))
  if (isPolygon.value) { poly.value = previous?.points || []; label.value = previous?.label || ''; closed.value = false }
  else { selected.value = -1; tool.value = previous?.boxes?.length ? 'select' : 'draw' }
}
function closePolygon() {
  if (readOnly.value || closed.value || poly.value.length < 3) return
  closed.value = true; emit('update:modelValue', { points: snapshot(poly.value), label: label.value })
}
function keydown(event: KeyboardEvent) {
  if (readOnly.value || props.findOnly) return
  const target = event.target as HTMLElement | null
  if (target?.closest('input, select, textarea, [contenteditable="true"]')) return
  const key = event.key.toLowerCase()
  if (key === 'escape') { event.preventDefault(); cancelDrag(); return }
  if (key === 'z' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); undo(); return }
  if (drag) return
  if (key === 'delete' || key === 'backspace') { event.preventDefault(); remove(); return }
  if (key === 'enter' && isPolygon.value) { event.preventDefault(); closePolygon(); return }
  if (!isPolygon.value && !event.ctrlKey && !event.metaKey) {
    if (key === 'r' || key === 'v') { event.preventDefault(); setTool(key === 'r' ? 'draw' : 'select'); return }
    if (selected.value >= 0 && ['arrowleft', 'arrowright', 'arrowup', 'arrowdown'].includes(key)) {
      const box = boxes.value[selected.value]
      if (!box) return
      event.preventDefault()
      const delta = event.shiftKey ? .01 : .002
      save({ boxes: replaceBox(boxes.value, selected.value, moveBox(box.box, key === 'arrowleft' ? -delta : key === 'arrowright' ? delta : 0, key === 'arrowup' ? -delta : key === 'arrowdown' ? delta : 0)) })
    }
  }
}
const polygonPoints = computed(() => poly.value.map(point => `${point[0] * 1000},${point[1] * 1000}`).join(' '))
const standardBoxes = computed<AnnotationBox[]>(() => Array.isArray(props.standard) ? props.standard : props.standard?.boxes || [])
const standardPolygon = computed(() => (props.standard?.polygon || props.standard?.points || []).map((point: number[]) => `${point[0] * 1000},${point[1] * 1000}`).join(' '))
</script>

<template>
  <div class="annotation-component" @keydown="keydown">
    <div v-if="!findOnly" class="annotation-toolbar">
      <div class="tool-group drawing-tools">
        <button v-if="!isPolygon" type="button" class="tool-button tool-with-text" :class="{ active: tool === 'select' }" :disabled="readOnly" :aria-pressed="tool === 'select'" aria-label="选择工具" @click="setTool('select')"><Icon name="MousePointer2" :size="18"/><span>选择</span></button>
        <button type="button" class="tool-button tool-with-text" :class="{ active: isPolygon || tool === 'draw' }" :disabled="readOnly" :aria-label="isPolygon ? '多边形工具' : '矩形工具'" :aria-pressed="isPolygon || tool === 'draw'" @click="setTool('draw')"><Icon :name="isPolygon ? 'Shapes' : 'SquareDashed'" :size="18"/><span>{{ isPolygon ? '多边形' : '画框' }}</span></button>
      </div>
      <div class="tool-group canvas-actions">
        <button type="button" class="tool-button" :disabled="readOnly || !canUndo" @click="undo" aria-label="撤销"><Icon name="RotateCcw" :size="17"/></button>
        <button type="button" class="tool-button" :disabled="readOnly || (isPolygon ? !poly.length : selected < 0)" @click="remove" aria-label="删除选中标注"><Icon name="Trash2" :size="17"/></button>
        <button v-if="!isPolygon" type="button" class="tool-button clear-all-boxes" :disabled="readOnly || !boxes.length" @click="clearAllBoxes" aria-label="清空所有标注框"><Icon name="Eraser" :size="16"/><span>清空所有框</span></button>
        <span class="tool-divider"></span>
        <button type="button" class="tool-button" :disabled="zoom <= 1" @click="zoom = Math.max(1, zoom - .25)" aria-label="缩小"><Icon name="ZoomOut" :size="18"/></button><span class="zoom-label">{{ Math.round(zoom * 100) }}%</span><button type="button" class="tool-button" :disabled="zoom >= 2" @click="zoom = Math.min(2, zoom + .25)" aria-label="放大"><Icon name="ZoomIn" :size="18"/></button>
      </div>
    </div>
    <div v-if="showingStandard" class="standard-view-note" role="status"><Icon name="LockKeyhole" :size="15"/>正在查看标准答案 · 绿色虚线为标准标注，查看期间不能修改</div>
    <div class="canvas-scroll">
      <div ref="surface" class="annotation-surface" :class="{ finding: findOnly, readonly: readOnly, 'drawing-mode': tool === 'draw', 'select-mode': tool === 'select' }" tabindex="0" role="application" :aria-label="findOnly ? '点击图片中任务要求的目标' : readOnly ? '图像标注画布，只读' : '图像标注画布；画框工具新增标注，选择工具移动，八个控制点调整边界'" :style="{ aspectRatio: question.width + '/' + question.height, width: zoom * 100 + '%', maxWidth: zoom * 490 * question.width / question.height + 'px', minWidth: '0', margin: '0 auto' }" @pointermove="move" @pointerup="up" @pointercancel="cancelDrag" @lostpointercapture="cancelDrag">
        <img :src="question.image" alt="本题待标注图像" draggable="false" @error="imageError = true">
        <div v-if="imageError" class="image-error">图片加载失败，请刷新后重试。</div>
        <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" class="annotation-overlay" @pointerdown="down($event)">
          <rect v-if="guide && question.guide_box" class="guide-box" :x="question.guide_box[0] * 1000" :y="question.guide_box[1] * 1000" :width="question.guide_box[2] * 1000" :height="question.guide_box[3] * 1000"/>
          <template v-for="box in orderedBoxes" :key="box.index">
            <rect class="user-box" :class="{ selected: selected === box.index, 'answer-comparison': showingStandard }" :data-box-index="box.index" :x="box.box[0] * 1000" :y="box.box[1] * 1000" :width="box.box[2] * 1000" :height="box.box[3] * 1000" @pointerdown.stop="down($event, box.index)"/>
            <text v-if="!showingStandard || box.label" :x="box.box[0] * 1000 + 7" :y="Math.max(25, box.box[1] * 1000 - 9)" class="box-label">{{ box.index + 1 }}{{ labelsVisible && box.label ? ' · ' + box.label : '' }}</text>
          </template>
          <rect v-if="draft" class="user-box draft" :x="draft[0] * 1000" :y="draft[1] * 1000" :width="draft[2] * 1000" :height="draft[3] * 1000"/>
          <polygon v-if="isPolygon && closed" class="user-polygon" :points="polygonPoints"/><polyline v-else-if="isPolygon" class="user-polyline" :points="polygonPoints"/>
          <circle v-for="(point, index) in poly" :key="index" :cx="point[0] * 1000" :cy="point[1] * 1000" r="5" class="poly-dot"/>
          <template v-if="showingStandard && question.type === 'box'">
            <g v-for="(box, index) in standardBoxes" :key="index" class="standard-annotation">
              <rect class="standard-box" :x="box.box[0] * 1000" :y="box.box[1] * 1000" :width="box.box[2] * 1000" :height="box.box[3] * 1000"/>
              <text class="standard-box-label" :x="box.box[0] * 1000 + 7" :y="Math.min(982, box.box[1] * 1000 + 28)">标准 {{ index + 1 }}{{ box.label ? ' · ' + box.label : '' }}</text>
            </g>
          </template>
          <polygon v-if="showingStandard && question.type === 'polygon'" class="standard-polygon" :points="standardPolygon"/>
        </svg>
        <template v-if="selectedBox && tool === 'select' && !readOnly && !isPolygon && !findOnly">
          <button v-for="handle in handles" :key="handle.id" type="button" class="box-resize-handle" :class="'handle-' + handle.id" :data-handle="handle.id" :aria-label="`调整第 ${selected + 1} 个标注框的${handle.title}`" :style="{ left: (selectedBox[0] + selectedBox[2] * handle.x) * 100 + '%', top: (selectedBox[1] + selectedBox[3] * handle.y) * 100 + '%' }" @pointerdown.stop="down($event, selected, handle.id)"><span></span></button>
        </template>
      </div>
    </div>
    <div v-if="isPolygon && !closed && !readOnly" class="polygon-controls"><span>已放置 {{ poly.length }} 个点</span><button class="btn small outline" :disabled="poly.length < 3" @click="closePolygon">闭合多边形<Icon name="Check" :size="15"/></button></div>
    <div v-if="!isPolygon && !findOnly && boxes.length" class="annotation-objects" aria-label="标注对象列表">
      <div class="objects-heading"><b>标注对象</b><span>{{ readOnly ? '已提交 ' + boxes.length + ' 个框' : '点击编号选中重叠框，分别设置标签' }}</span></div>
      <div v-for="(box, index) in boxes" :key="index" class="annotation-object" :class="{ selected: selected === index }">
        <button type="button" class="object-select" :disabled="readOnly" :aria-label="`选择第 ${index + 1} 个标注框`" :aria-pressed="selected === index" @click="selectBox(index)"><span class="object-number">{{ index + 1 }}</span><span>标注框 {{ index + 1 }}</span><Icon v-if="selected === index" name="Check" :size="15"/></button>
        <select v-if="labelsVisible" :value="box.label" :disabled="readOnly" :aria-label="`第 ${index + 1} 个标注框标签`" @change="changeBoxLabel(index, ($event.target as HTMLSelectElement).value)"><option value="">请选择标签</option><option v-for="option in question.labels" :key="option" :value="option">{{ option }}</option></select>
      </div>
    </div>
    <div v-if="labelsVisible && !findOnly" class="annotation-labels"><label>{{ isPolygon ? '选择标签' : selected >= 0 ? `框 ${selected + 1} 的标签` : '新框标签' }}</label><div><button v-for="option in question.labels" :key="option" :disabled="readOnly" class="label-chip" :class="{ selected: activeLabel === option }" @click="chooseLabel(option)"><span></span>{{ option }}<Icon v-if="activeLabel === option" name="Check" :size="13"/></button></div><span class="annotation-count">{{ isPolygon ? poly.length + ' 个顶点' : boxes.length + ' 个标注框' }}</span></div>
    <div v-if="!findOnly" class="canvas-caption"><span>{{ showingStandard ? '绿色虚线：标准答案；蓝色实线：你的标注。当前只能查看。' : guide ? '虚线框是操作引导；选中框后拖动四边或四角调整。' : isPolygon ? '按顺序点击边界，完成后闭合多边形。' : tool === 'draw' ? '拖动新增独立框，可在已有框内画框。R 画框 · V 选择 · Ctrl+Z 撤销' : '点击框或对象编号选择；拖动四边、四角调整，方向键微调。新增框请点“画框”。' }}</span><a :href="question.source_url" target="_blank" rel="noopener noreferrer">素材来源<Icon name="ArrowUpRight" :size="12"/></a></div>
  </div>
</template>

<style scoped>
.box-label{fill:#175ccc;stroke:white;stroke-width:4px;paint-order:stroke;stroke-linejoin:round}
.annotation-toolbar{min-height:48px;height:auto;gap:8px;flex-wrap:wrap;padding-block:7px}.drawing-tools{gap:5px}.tool-with-text{width:auto;min-width:64px;padding-inline:9px;gap:5px}.tool-with-text span{font-size:13px;white-space:nowrap}.canvas-actions{flex-wrap:wrap}.annotation-surface{touch-action:none}.annotation-surface.select-mode{cursor:default}.annotation-surface.drawing-mode{cursor:crosshair}.annotation-surface.readonly,.annotation-surface.readonly .user-box{cursor:default}.annotation-surface.drawing-mode .user-box,.guide-box,.box-label,.standard-annotation,.standard-polygon,.draft,.poly-dot,.user-polygon,.user-polyline{pointer-events:none}.annotation-surface.select-mode .user-box{pointer-events:all;cursor:move}.annotation-surface .user-box{stroke:#3974d5;stroke-width:2;vector-effect:non-scaling-stroke;fill:rgba(57,116,213,.04)}.annotation-surface .user-box.selected{stroke:#175ccc;stroke-width:2.5;fill:rgba(57,116,213,.09)}.annotation-surface .user-box.answer-comparison{stroke-width:1.5;fill:none}.annotation-surface.readonly .user-box{pointer-events:none}.box-resize-handle{position:absolute;z-index:2;width:24px;height:24px;padding:5px;display:flex;align-items:center;justify-content:center;transform:translate(-50%,-50%);border:0;background:transparent;touch-action:none}.box-resize-handle span{display:block;width:12px;height:12px;flex-shrink:0;background:white;border:2px solid #175ccc;border-radius:2px;box-shadow:0 1px 3px #0002;pointer-events:none}.box-resize-handle:hover span,.box-resize-handle:focus-visible span{background:#dceaff}.handle-n,.handle-s{cursor:ns-resize}.handle-e,.handle-w{cursor:ew-resize}.handle-nw,.handle-se{cursor:nwse-resize}.handle-ne,.handle-sw{cursor:nesw-resize}.standard-view-note{display:flex;align-items:center;gap:7px;padding:10px 14px;background:#f3faf4;color:#2e653c;font-size:13px;line-height:1.6}.standard-view-note svg{flex-shrink:0}.annotation-surface .standard-box,.annotation-surface .standard-polygon{fill:rgba(29,150,76,.06);stroke:#159447;stroke-width:3;stroke-dasharray:8 5;vector-effect:non-scaling-stroke}.standard-box-label{font-size:23px;font-weight:700;fill:#116d33;paint-order:stroke;stroke:white;stroke-width:4px;stroke-linejoin:round}.annotation-objects{padding:12px 14px;background:#fff;border-top:1px solid #e9eaf0;display:grid;gap:7px;max-height:230px;overflow:auto}.objects-heading{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:3px;font-size:13px}.objects-heading b{color:#39414f;font-weight:600}.objects-heading>span{font-size:12px;color:#737c89}.annotation-object{display:flex;align-items:center;gap:12px;min-width:0;padding:5px 8px;border:1px solid #e6eaf0;border-radius:7px}.annotation-object.selected{border-color:#7fa6e4;background:#f5f8ff}.object-select{display:flex;align-items:center;gap:9px;flex:1;min-width:0;text-align:left;font-size:13px;padding:3px 0;color:#374355}.object-select>svg{color:#2868c7;margin-left:auto}.object-number{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:5px;background:#edf2fa;color:#2868c7;font-size:12px;font-weight:600;flex-shrink:0}.annotation-object select{width:140px;max-width:50%;font:inherit;font-size:13px;color:#374355;border:1px solid #dce2eb;border-radius:5px;background:white;padding:6px 8px}.annotation-object select:disabled{background:#f6f7f9;color:#627083}.annotation-labels>label{white-space:nowrap}.canvas-caption{gap:14px;line-height:1.7}.canvas-caption>a{flex-shrink:0}.box-resize-handle:focus-visible,.object-select:focus-visible,.annotation-object select:focus-visible{outline:2px solid #3974d5;outline-offset:2px}@media(max-width:600px){.annotation-toolbar{justify-content:flex-start}.drawing-tools{flex:1}.canvas-actions{gap:3px}.tool-with-text{min-width:55px;padding-inline:6px}.annotation-objects{padding:10px}.canvas-caption{flex-wrap:wrap}.standard-view-note{font-size:12px}.annotation-labels{flex-wrap:wrap}}
</style>
