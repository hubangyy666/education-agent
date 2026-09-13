import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

const source = await readFile(new URL('../src/components/Tutor.vue', import.meta.url), 'utf8')
const descriptor = parse(source).descriptor
const script = compileScript(descriptor, { id: 'tutor-entry' }).content
const js = ts.transpileModule(script, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
const cleanups = [], timers = []
const exports = {}
const props = vue.reactive({ floating: true, stage: false, runId: 'run1', questionId: 'q1', disabled: false, nudge: '', initialNudge: '有疑问就来找我哦' })
const mockVue = { ...vue, onMounted(fn) { fn() }, onBeforeUnmount(fn) { cleanups.push(fn) } }
const fakeWindow = { addEventListener() {}, removeEventListener() {} }
function fakeSetTimeout(fn, delay) { const timer = { fn, delay, cancelled: false }; timers.push(timer); return timer }
function fakeClearTimeout(timer) { timer.cancelled = true }
vm.runInNewContext(js, { exports, require: name => name === 'vue' ? mockVue : {}, window: fakeWindow, setTimeout: fakeSetTimeout, clearTimeout: fakeClearTimeout })
const state = exports.default.setup(props, { expose() {}, emit() {} })

assert.equal(state.initialNudgeVisible.value, true)
assert.equal(state.launchNudge.value, '有疑问就来找我哦')
assert.equal(timers.length, 1)
assert.equal(timers[0].delay, 2000)
timers[0].fn()
await vue.nextTick()
assert.equal(state.initialNudgeVisible.value, false)
assert.equal(state.launchNudge.value, '需要一点提示吗？')
cleanups.forEach(fn => fn())
assert.equal(timers[0].cancelled, true)

const css = await readFile(new URL('../src/training-tutor.css', import.meta.url), 'utf8')
assert.match(css, /\.tutor-floating \.mentor-launch > img,[\s\S]*?width: 96px;[\s\S]*?height: 96px;/)

// Render the actual training template across modes with controlled component imports.
const training = parse(await readFile(new URL('../src/views/Training.vue', import.meta.url), 'utf8')).descriptor
const template = compileTemplate({ source: training.template.content, filename: 'Training.vue', id: 'training-tutor-entry' })
assert.deepEqual(template.errors, [])
const renderExports = {}
vm.runInNewContext(ts.transpileModule(template.code, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
  exports: renderExports, require: () => ({ ...vue, resolveComponent: name => name }),
})
const nodes = node => [node, ...(Array.isArray(node?.children) ? node.children.flatMap(nodes) : [])]
for (const mode of ['course', 'job', 'competition']) {
  for (const phase of ['active', 'intro', 'finished']) {
    const q = { id: 'q1', type: 'choice', title: '题目' }
    const context = {
      run: { id: 'run1', ability_id: 'A1', questions: [q], answers: {} }, q, mode,
      batch: mode !== 'course', intro: phase === 'intro', finished: phase === 'finished',
      tutorOpen: true, state: { user: { voice: false } }, report: { results: [], score: 0 },
      completedQuestionCount: 0, index: 0, feedback: undefined,
    }
    const tree = renderExports.render(context, [])
    const expected = mode === 'course' && phase === 'active'
    assert.equal(nodes(tree).filter(node => node?.type === 'Tutor').length, Number(expected), `${mode}/${phase}: tutor visibility`)
    assert.equal(tree.props.class.includes('tutor-panel-open'), expected, `${mode}/${phase}: panel space`)
  }
}

// A reused route must clear the previous course's expanded panel before loading another run.
const route = vue.reactive({ params: { id: 'run1' }, query: {} }), trainingExports = {}
const trainingImports = {
  vue: { ...vue, onMounted() {}, onBeforeUnmount() {} },
  'vue-router': { useRoute: () => route, useRouter: () => ({}) },
  '../api': { api: () => new Promise(() => {}) },
  '../audio': { stopEncouragementAudio() {} },
}
const trainingScript = compileScript(training, { id: 'training-tutor-route' }).content
vm.runInNewContext(ts.transpileModule(trainingScript, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
  exports: trainingExports, require: name => trainingImports[name] || {},
})
const scope = vue.effectScope()
const trainingState = scope.run(() => trainingExports.default.setup({}, { expose() {} }))
trainingState.tutorOpen.value = true
route.params.id = 'run2'
await vue.nextTick()
assert.equal(trainingState.tutorOpen.value, false)
scope.stop()
console.log('12 tutor entry checks passed')
