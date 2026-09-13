// Compile the real Vue setup and templates and exercise their rendered events.
// The host tree, API, router and SSE stream are controlled substitutes, not browser/live proof.
// This script only reports to stdout; it does not write evidence files or database records.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

const clone = value => JSON.parse(JSON.stringify(value))
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function hostNode(type, text = '') {
  return {
    type, tagName: type.toUpperCase(), text, props: {}, children: [], parent: null,
    addEventListener() {}, removeEventListener() {},
    setAttribute(key, value) { this.props[key] = value },
    removeAttribute(key) { delete this.props[key] },
    scrollTo() {}, get scrollHeight() { return 100 },
  }
}
const renderer = vue.createRenderer({
  createElement: hostNode,
  createText: text => hostNode('#text', text),
  createComment: text => hostNode('#comment', text),
  setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.text = text; node.children = [] },
  parentNode: node => node.parent,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  patchProp: (node, key, previous, value) => { node.props[key] = value },
  insert(node, parent, anchor = null) {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    node.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
  },
  remove(node) {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    node.parent = null
  },
  insertStaticContent(content, parent, anchor) {
    const node = hostNode('#static', content)
    node.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
    return [node, node]
  },
})
// v-model's real update directive checks focus even with a custom renderer.
const previousDocument = globalThis.document
globalThis.document = { activeElement: null }
const all = node => [node, ...node.children.flatMap(all)]
const byClass = (root, name) => all(root).filter(node => String(node.props.class || '').split(/\s+/).includes(name))
const visibleText = node => node.type === '#comment' ? '' : String(node.text || '') + node.children.map(visibleText).join('')
const cards = root => byClass(root, 'practice-card')
const settle = async () => { await new Promise(resolve => setImmediate(resolve)); await vue.nextTick() }

const compiled = new Map()
async function component(name, imports, globals = {}) {
  if (!compiled.has(name)) {
    const source = await readFile(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')
    const script = compileScript(parse(source).descriptor, { id: `verify-${name}`, inlineTemplate: true }).content
    compiled.set(name, ts.transpileModule(script, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText)
  }
  const exports = {}
  vm.runInNewContext(compiled.get(name), {
    exports, AbortController, TextDecoder, console,
    window: { addEventListener() {}, removeEventListener() {} },
    require(key) {
      if (key === 'vue') return vue
      if (key in imports) return imports[key]
      throw new Error(`Uncontrolled import: ${key}`)
    },
    ...globals,
  }, { filename: `${name}.vue` })
  return exports.default
}
const Icon = { default: { props: ['name', 'size'], setup: () => () => vue.h('span') } }
async function mount(name, props = {}, options = {}) {
  const calls = [], navigations = [], root = hostNode('root')
  const imports = {
    './Icon.vue': Icon,
    '../api': { api(path, init) {
      calls.push({ path, ...init })
      return options.api ? options.api(path, init) : Promise.resolve({ id: 'actual-run-id' })
    } },
    'vue-router': { useRouter: () => ({ push(path) { navigations.push(path); return Promise.resolve() } }) },
  }
  if (name === 'Tutor') imports['./TutorRecommendations.vue'] = { default: await component('TutorRecommendations', imports) }
  const target = await component(name, imports, { fetch: options.fetch })
  const app = renderer.createApp(target, props)
  const instance = app.mount(root)
  return { root, calls, navigations, instance, unmount: () => app.unmount() }
}

const detection = {
  id: 'level:A4-L3', resource_type: 'level', level_id: 'A4-L3',
  ability_name: '目标检测与定位', title: '边界控制', mode: 'course',
  icon: 'ScanLine', color: 'purple', url: '/skills/A4?level=A4-L3',
}
const job = { ...detection, id: 'level:A4-JOB', level_id: 'A4-JOB', title: '企业试标 · 批量任务', mode: 'job' }
const race = { ...detection, id: 'level:A4-RACE', level_id: 'A4-RACE', title: '能力挑战 · 限时赛', mode: 'competition' }
const fourth = { ...detection, id: 'level:A4-L4', level_id: 'A4-L4', title: '多目标' }
const ability = { id: 'ability:A4', resource_type: 'ability', title: '目标检测与定位课程', url: '/skills/A4' }
const invalid = [
  { ...detection, level_id: 'A4-L99', id: 'level:A4-L99' },
  { ...detection, level_id: 'A11-L1', id: 'level:A11-L1' },
  { ...detection, id: 'level:A4-L2' },
]
function stream() {
  const queue = [], waiters = []
  const deliver = value => waiters.length ? waiters.shift()(value) : queue.push(value)
  return {
    response: { ok: true, body: { getReader: () => ({ read: () => queue.length ? Promise.resolve(queue.shift()) : new Promise(resolve => waiters.push(resolve)) }) } },
    event(name, payload) { deliver({ done: false, value: new TextEncoder().encode(`event: ${name}\ndata: ${JSON.stringify(payload)}\n\n`) }) },
    end() { deliver({ done: true }) },
  }
}
let passed = 0
async function check(name, action) { await action(); passed++; console.log(`PASS ${name}`) }

try {
  await check('rendered cards reject invalid IDs and non-level resources, deduplicate, and cap at three', async () => {
    const page = await mount('TutorRecommendations', { resources: [ability, ...invalid, detection, detection, job, race, fourth] })
    assert.equal(cards(page.root).length, 3)
    assert.deepEqual(cards(page.root).map(visibleText).map(text => ['课关', '岗关', '赛关'].find(mode => text.includes(mode))), ['课关', '岗关', '赛关'])
    assert.match(cards(page.root)[0].props['aria-label'], /目标检测与定位.*边界控制/)
    assert.equal(page.calls.length, 0)
    page.unmount()
  })
  await check('unrelated or invalid-only resources render no recommendation section', async () => {
    const page = await mount('TutorRecommendations', { resources: [ability, ...invalid] })
    assert.equal(byClass(page.root, 'tutor-recommendations').length, 0)
    page.unmount()
  })
  await check('click posts the precise selected level and navigates using the returned run ID', async () => {
    const page = await mount('TutorRecommendations', { resources: [detection, job] })
    await cards(page.root)[1].props.onClick()
    assert.equal(page.calls.length, 1)
    assert.equal(page.calls[0].path, '/runs/start')
    assert.equal(page.calls[0].method, 'POST')
    assert.deepEqual(JSON.parse(page.calls[0].body), { level_id: 'A4-JOB' })
    assert.equal(page.calls[0].signal.aborted, false)
    assert.deepEqual(page.navigations, ['/train/actual-run-id'])
    page.unmount()
  })
  await check('rapid double-click creates one run and disables every card until completion', async () => {
    const gate = deferred(), page = await mount('TutorRecommendations', { resources: [detection, job] }, { api: () => gate.promise })
    const first = cards(page.root)[0].props.onClick()
    const second = cards(page.root)[1].props.onClick()
    await vue.nextTick()
    assert.equal(page.calls.length, 1)
    assert.ok(cards(page.root).every(card => card.props.disabled === true))
    assert.equal(cards(page.root)[0].props['aria-busy'], true)
    assert.match(visibleText(cards(page.root)[0]), /准备中/)
    gate.resolve({ id: 'single-run' })
    await Promise.all([first, second])
    await vue.nextTick()
    assert.deepEqual(page.navigations, ['/train/single-run'])
    assert.ok(cards(page.root).every(card => card.props.disabled === false))
    page.unmount()
  })
  await check('failed start keeps answer cards, shows an accessible error, and supports a successful retry', async () => {
    let attempt = 0
    const page = await mount('TutorRecommendations', { resources: [detection] }, { api: async () => {
      if (++attempt === 1) throw new Error('学习服务暂时不可用')
      return { id: 'retry-run' }
    } })
    await cards(page.root)[0].props.onClick(); await vue.nextTick()
    assert.equal(page.navigations.length, 0)
    assert.equal(cards(page.root).length, 1)
    assert.equal(cards(page.root)[0].props.disabled, false)
    const alert = byClass(page.root, 'practice-error')[0]
    assert.equal(alert.props.role, 'alert')
    assert.match(visibleText(alert), /学习服务暂时不可用/)
    await cards(page.root)[0].props.onClick(); await vue.nextTick()
    assert.equal(page.calls.length, 2)
    assert.equal(byClass(page.root, 'practice-error').length, 0)
    assert.deepEqual(page.navigations, ['/train/retry-run'])
    page.unmount()
  })
  await check('unmount aborts the request and a late success cannot navigate or start another run', async () => {
    const gate = deferred(), page = await mount('TutorRecommendations', { resources: [detection] }, { api: () => gate.promise })
    const handler = cards(page.root)[0].props.onClick
    const pending = handler()
    page.unmount()
    assert.equal(page.calls[0].signal.aborted, true)
    gate.resolve({ id: 'late-run' }); await pending; await handler()
    assert.equal(page.navigations.length, 0)
    assert.equal(page.calls.length, 1)
  })
  for (const inQuestion of [false, true]) {
    await check(`${inQuestion ? 'question' : 'homepage'} Tutor renders SSE completion with the correct recommendation boundary`, async () => {
      const events = stream(), requests = []
      const page = await mount('Tutor', inQuestion ? { runId: 'existing-run', questionId: 'q1' } : { stage: true }, {
        fetch: async (path, init) => { requests.push({ path, body: JSON.parse(init.body) }); return events.response },
      })
      const send = page.instance.send('什么是 IoU？')
      await settle()
      assert.equal(requests.length, 1)
      assert.equal(requests[0].path, '/api/ai/chat')
      assert.equal(requests[0].body.mode, inQuestion ? 'QUESTION_TUTOR' : 'GENERAL_TUTOR')
      assert.equal(requests[0].body.hint_request, false)
      assert.deepEqual(clone(requests[0].body.history), [])
      events.event('token', { text: 'IoU 衡量两个区域的重合程度。' })
      await settle()
      assert.match(visibleText(page.root), /IoU 衡量两个区域的重合程度/)
      assert.equal(cards(page.root).length, 0)
      events.event('done', {
        text: 'IoU 是交集面积除以并集面积。', provider: 'deepseek',
        resources: [detection, detection, ability], sources: [], suggestions: ['怎样调整边界？'],
      })
      await settle()
      assert.equal(cards(page.root).length, inQuestion ? 0 : 1)
      assert.match(visibleText(page.root), /IoU 是交集面积除以并集面积/)
      const resourceDetails = byClass(page.root, 'chat-sources').find(node => visibleText(node).includes('查看平台学习资源'))
      assert.ok(resourceDetails)
      assert.equal(resourceDetails.type, 'details')
      assert.ok(!resourceDetails.props.open)
      assert.match(visibleText(resourceDetails), /目标检测与定位课程/)
      assert.equal(all(resourceDetails).filter(node => node.type === 'a').length, inQuestion ? 2 : 1)
      assert.match(visibleText(page.root), /怎样调整边界/)
      events.end(); await send; await vue.nextTick()
      assert.equal(page.calls.length, 0)
      if (!inQuestion) {
        await cards(page.root)[0].props.onClick()
        assert.deepEqual(JSON.parse(page.calls[0].body), { level_id: 'A4-L3' })
        assert.deepEqual(page.navigations, ['/train/actual-run-id'])
      }
      page.unmount()
    })
  }
  console.log(`${passed} tutor recommendation component checks passed`)
} finally {
  if (previousDocument === undefined) delete globalThis.document
  else globalThis.document = previousDocument
}
