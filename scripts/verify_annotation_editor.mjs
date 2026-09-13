// Geometry and actual Vue setup tests. Pointer events use a bounded surface stub;
// browser hit testing and rendering are verified separately in the live UI.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import ts from 'typescript'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const plain = value => JSON.parse(JSON.stringify(value))
const transpile = text => ts.transpileModule(text, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
const geometry = {}
vm.runInNewContext(transpile(await readFile(path.join(root, 'src/components/annotationGeometry.ts'), 'utf8')), { exports: geometry })
const descriptor = parse(await readFile(path.join(root, 'src/components/AnnotationCanvas.vue'), 'utf8')).descriptor
const source = transpile(compileScript(descriptor, { id: 'annotation-editor-test' }).content)
let total = 0
async function check(name, action) { await action(); total++; console.log(`PASS ${name}`) }
function near(actual, expected) {
  assert.equal(actual.length, expected.length)
  actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) < 1e-9, `${plain(actual)} != ${expected}`))
}
const initialBoxes = () => [{ box: [.1, .2, .4, .5], label: '人' }, { box: [.15, .3, .25, .2], label: '车' }]
function editor(overrides = {}) {
  const events = [], exports = {}, captures = new Set()
  const props = vue.reactive({ question: { id: 'q1', type: 'box', labels: ['人', '车'] }, modelValue: {}, disabled: false, standard: undefined, ...overrides })
  vm.runInNewContext(source, { exports, require: name => name === 'vue' ? vue : name === './annotationGeometry' ? geometry : {} })
  const scope = vue.effectScope()
  const state = scope.run(() => exports.default.setup(props, { expose() {}, emit(name, value) {
    events.push({ name, value: plain(value) })
    if (name === 'update:modelValue') props.modelValue = plain(value)
  } }))
  state.surface.value = { getBoundingClientRect: () => ({ left: 100, top: 50, width: 1000, height: 500 }), focus() {}, setPointerCapture: id => captures.add(id), hasPointerCapture: id => captures.has(id), releasePointerCapture: id => captures.delete(id) }
  return { props, state, events, scope, captures }
}
const pointer = (x, y, extras = {}) => ({ pointerId: 1, button: 0, isPrimary: true, clientX: 100 + x * 1000, clientY: 50 + y * 500, preventDefault() {}, ...extras })
const key = (value, extras = {}) => ({ key: value, preventDefault() {}, target: null, ...extras })

await check('all eight resize handles preserve each opposing edge and all untouched axes', () => {
  const original = [.2, .3, .4, .4]
  const expected = { n: [.2, .4, .4, .3], ne: [.2, .4, .5, .3], e: [.2, .3, .5, .4], se: [.2, .3, .5, .5], s: [.2, .3, .4, .5], sw: [.3, .3, .3, .5], w: [.3, .3, .3, .4], nw: [.3, .4, .3, .3] }
  for (const [handle, box] of Object.entries(expected)) near(geometry.resizeBox(original, handle, .1, .1), box)
  near(original, [.2, .3, .4, .4])
})
await check('resize cannot flip, vanish, or exceed any image boundary', () => {
  for (const handle of ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw']) {
    for (const delta of [-100, 100]) {
      const [x, y, width, height] = geometry.resizeBox([.2, .3, .4, .4], handle, delta, delta)
      assert.ok(x >= 0 && y >= 0 && width >= .003 - 1e-9 && height >= .003 - 1e-9)
      assert.ok(x + width <= 1 + 1e-9 && y + height <= 1 + 1e-9)
    }
  }
  near(geometry.moveBox([.2, .3, .4, .4], 100, -100), [.6, 0, .4, .4])
  near(geometry.drawBox([.7, .8], [-2, -3]), [0, 0, .7, .8])
})
await check('drawing inside an existing box commits one independent new object only on pointerup', async () => {
  const test = editor({ modelValue: { boxes: initialBoxes() } }), { state, props, events } = test
  state.setTool('draw'); state.down(pointer(.25, .35), 0); state.move(pointer(.35, .45))
  assert.equal(events.length, 0); assert.deepEqual(plain(props.modelValue.boxes), initialBoxes())
  state.up(pointer(.35, .45)); await vue.nextTick()
  assert.equal(events.length, 1); assert.equal(props.modelValue.boxes.length, 3)
  assert.deepEqual(plain(props.modelValue.boxes.slice(0, 2)), initialBoxes()); near(props.modelValue.boxes[2].box, [.25, .35, .1, .1])
  assert.equal(state.selected.value, 2); assert.equal(state.tool.value, 'select'); assert.equal(test.captures.size, 0)
  test.scope.stop()
})
await check('frame-level label selection never leaks to another frame or a newly drawn object', async () => {
  const { state, props, scope } = editor({ modelValue: { boxes: initialBoxes() } })
  state.selectBox(1); state.chooseLabel('人'); await vue.nextTick()
  assert.deepEqual(plain(props.modelValue.boxes.map(box => box.label)), ['人', '人'])
  state.selectBox(0); state.chooseLabel('车'); await vue.nextTick()
  assert.deepEqual(plain(props.modelValue.boxes.map(box => box.label)), ['车', '人']); assert.equal(state.activeLabel.value, '车')
  state.setTool('draw'); assert.equal(state.activeLabel.value, '')
  state.down(pointer(.6, .1)); state.up(pointer(.8, .3)); await vue.nextTick()
  assert.equal(props.modelValue.boxes[2].label, ''); assert.equal(state.selected.value, 2)
  state.undo(); await vue.nextTick(); assert.equal(props.modelValue.boxes.length, 2)
  scope.stop()
})
await check('overlapping-object selection changes only the chosen frame; drag undo restores the entire action', async () => {
  const { state, props, events, scope } = editor({ modelValue: { boxes: initialBoxes() } })
  state.selectBox(0); state.down(pointer(.2, .3), 0); state.move(pointer(.3, .4)); state.move(pointer(.4, .5)); state.up(pointer(.4, .5)); await vue.nextTick()
  assert.equal(events.length, 1); near(props.modelValue.boxes[0].box, [.3, .4, .4, .5]); assert.deepEqual(plain(props.modelValue.boxes[1]), initialBoxes()[1])
  state.undo(); await vue.nextTick(); assert.deepEqual(plain(props.modelValue.boxes), initialBoxes())
  scope.stop()
})
await check('each of the eight component handles resizes only its selected object', async () => {
  for (const handle of ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw']) {
    const { state, props, events, scope } = editor({ modelValue: { boxes: initialBoxes() } })
    state.selectBox(1); state.down(pointer(.3, .4), 1, handle); state.up(pointer(.35, .45)); await vue.nextTick()
    assert.equal(events.length, 1); assert.deepEqual(plain(props.modelValue.boxes[0]), initialBoxes()[0])
    near(props.modelValue.boxes[1].box, geometry.resizeBox(initialBoxes()[1].box, handle, .05, .05))
    scope.stop()
  }
})
await check('cancel, Escape, lost capture and unrelated fingers do not commit partial geometry', async () => {
  const { state, props, events, scope } = editor({ modelValue: { boxes: initialBoxes() } })
  state.selectBox(0); state.down(pointer(.2, .3), 0); state.move(pointer(.4, .5)); state.cancelDrag(pointer(.4, .5))
  assert.equal(events.length, 0); assert.deepEqual(plain(props.modelValue.boxes), initialBoxes())
  state.down(pointer(.2, .3), 0); state.move(pointer(.4, .5)); state.keydown(key('Escape')); state.up(pointer(.4, .5))
  assert.equal(events.length, 0)
  state.down(pointer(.2, .3), 0); state.move(pointer(.8, .8, { pointerId: 2 })); state.up(pointer(.8, .8, { pointerId: 2 })); state.cancelDrag()
  assert.equal(events.length, 0)
  state.down(pointer(.2, .3, { button: 2 }), 0); state.up(pointer(.4, .5)); assert.equal(events.length, 0)
  scope.stop()
})
await check('standard answer alone enforces read-only on every pointer, keyboard, label and destructive operation', async () => {
  const { state, props, events, scope } = editor({ modelValue: { boxes: initialBoxes() } })
  state.selectBox(1); state.changeBoxLabel(1, '人'); await vue.nextTick()
  const before = plain(props.modelValue), count = events.length
  state.down(pointer(.2, .3), 1); state.move(pointer(.4, .5))
  props.standard = initialBoxes(); await vue.nextTick()
  assert.equal(state.readOnly.value, true); assert.equal(state.preview.value, null)
  state.up(pointer(.4, .5)); state.setTool('draw'); state.selectBox(0); state.chooseLabel('车'); state.changeBoxLabel(0, '车'); state.clearAllBoxes(); state.remove(); state.undo(); state.closePolygon()
  for (const value of ['Delete', 'Backspace', 'ArrowLeft', 'r', 'v', 'Enter']) state.keydown(key(value))
  state.keydown(key('z', { ctrlKey: true })); state.down(pointer(.2, .3)); state.up(pointer(.4, .5))
  assert.equal(events.length, count); assert.deepEqual(plain(props.modelValue), before)
  scope.stop()
})
await check('onboarding standard-answer assist keeps drawing and labeling enabled', async () => {
  const { state, props, scope } = editor({ modelValue: { boxes: [] }, standard: initialBoxes(), standardAssist: true })
  assert.equal(state.showingStandard.value, true); assert.equal(state.readOnly.value, false)
  state.down(pointer(.55, .1)); state.up(pointer(.8, .35)); await vue.nextTick()
  assert.equal(props.modelValue.boxes.length, 1)
  state.chooseLabel('人'); await vue.nextTick(); assert.equal(props.modelValue.boxes[0].label, '人')
  scope.stop()
})
await check('native label input keys are not stolen; selected-frame arrow keys remain independent', async () => {
  const { state, props, events, scope } = editor({ modelValue: { boxes: initialBoxes() } })
  state.selectBox(1)
  state.keydown(key('Delete', { target: { closest: () => true } })); assert.equal(events.length, 0)
  state.keydown(key('ArrowLeft', { shiftKey: true })); await vue.nextTick()
  near(props.modelValue.boxes[1].box, [.14, .3, .25, .2]); assert.deepEqual(plain(props.modelValue.boxes[0]), initialBoxes()[0])
  scope.stop()
})
await check('single-box onboarding remount selects its label; clearing all boxes can be undone', async () => {
  const { state, props, scope } = editor({ modelValue: { boxes: initialBoxes().slice(0, 1) }, guide: true })
  assert.equal(state.selected.value, 0); assert.equal(state.activeLabel.value, '人')
  state.chooseLabel('车'); await vue.nextTick(); assert.equal(props.modelValue.boxes[0].label, '车')
  state.clearAllBoxes(); await vue.nextTick(); assert.equal(props.modelValue.boxes.length, 0); assert.equal(state.tool.value, 'draw')
  state.undo(); await vue.nextTick(); assert.equal(props.modelValue.boxes[0].label, '车')
  scope.stop()
})
await check('polygon drawing, close, undo, label and clear work; standard viewing rejects all mutations', async () => {
  const { state, props, events, scope } = editor({ question: { id: 'polygon', type: 'polygon', labels: ['轮廓'] } })
  for (const point of [[.1, .1], [.8, .1], [.8, .8]]) { state.down(pointer(...point)); await vue.nextTick() }
  state.closePolygon(); assert.equal(state.closed.value, true)
  state.undo(); await vue.nextTick(); assert.equal(state.poly.value.length, 2); assert.equal(state.closed.value, false)
  state.down(pointer(.8, .8)); await vue.nextTick(); state.chooseLabel('轮廓'); await vue.nextTick()
  props.standard = { polygon: [[.1, .1], [.8, .1], [.8, .8]], label: '轮廓' }; await vue.nextTick()
  const count = events.length
  state.down(pointer(.2, .8)); state.closePolygon(); state.remove(); state.undo(); state.chooseLabel('别的标签')
  assert.equal(events.length, count); assert.equal(props.modelValue.points.length, 3); assert.equal(props.modelValue.label, '轮廓')
  scope.stop()
})
await check('find-only emits normalized spot coordinates without drawing or saving', () => {
  const { state, events, scope } = editor({ findOnly: true })
  state.down(pointer(.4, .7)); assert.equal(events.length, 1); assert.equal(events[0].name, 'spot'); near(events[0].value, [.4, .7]); assert.equal(state.draft.value, null)
  scope.stop()
})
console.log(`${total} annotation editor checks passed`)
