// Test cancellation and sound preferences without requiring a speaker or changing accounts.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import ts from 'typescript'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = await readFile(path.join(root, 'src/audio.ts'), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const results = []
const deferred = () => {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

function player(options = {}) {
  const events = [], exports = {}
  class AudioContext {
    state = 'suspended'
    destination = {}
    async resume() {
      events.push({ type: 'resume' })
      if (options.resumeFails) throw new Error('blocked')
      this.state = 'running'
    }
    async decodeAudioData(data) {
      if (options.decodeFails) throw new Error('unsupported codec')
      return { path: data.path }
    }
    createBufferSource() {
      const entry = { type: 'start', path: '' }
      return {
        buffer: null, onended: null,
        connect() {}, disconnect() {},
        start() { entry.path = this.buffer.path; events.push(entry) },
        stop() { events.push({ type: 'stop', path: this.buffer?.path }) },
      }
    }
  }
  const context = vm.createContext({
    exports,
    window: options.noAudio ? {} : { AudioContext },
    async fetch(clipPath) {
      events.push({ type: 'fetch', path: clipPath })
      if (options.gate) await options.gate.promise
      return {
        ok: !options.fetchFails,
        async arrayBuffer() { return { path: clipPath } },
      }
    },
  })
  vm.runInContext(compiled, context)
  return { api: exports, events }
}

async function check(name, test) {
  await test()
  results.push({ name, passed: true })
  console.log(`PASS ${name}`)
}

await check('six bundled WAV files match manifest and have PCM headers and audible samples', async () => {
  const base = path.join(root, 'public/audio/encouragement')
  const manifest = JSON.parse(await readFile(path.join(base, 'manifest.json'), 'utf8'))
  assert.equal(manifest.clips.length, 6)
  for (const clip of manifest.clips) {
    const data = await readFile(path.join(base, clip.file))
    assert.equal(createHash('sha256').update(data).digest('hex'), clip.sha256)
    assert.equal(data.toString('ascii', 0, 4), 'RIFF')
    assert.equal(data.toString('ascii', 8, 12), 'WAVE')
    assert.equal(data.readUInt16LE(20), 1) // PCM
    assert.equal(data.readUInt16LE(22), 1) // mono
    assert.equal(data.readUInt32LE(24), 24000)
    assert.equal(data.readUInt16LE(34), 16)
    assert.ok(clip.rms > 0.01)
    assert.ok(clip.duration_seconds > 0.5 && clip.duration_seconds < 8)
    assert.ok(source.includes(`/audio/encouragement/${clip.file}`))
  }
})

await check('no playback before user unlock; unlock does not speak', async () => {
  const { api, events } = player()
  assert.equal(await api.playEncouragement(), 'unavailable')
  assert.equal(await api.unlockEncouragementAudio(), true)
  assert.equal(events.filter(e => e.type === 'start').length, 0)
})

await check('six phrases rotate and wrap; only one sound is active; clips are cached', async () => {
  const { api, events } = player()
  await api.unlockEncouragementAudio()
  for (let index = 0; index < 7; index++) assert.equal(await api.playEncouragement(), 'played')
  assert.deepEqual(events.filter(e => e.type === 'start').map(e => e.path),
    [1, 2, 3, 4, 5, 6, 1].map(i => `/audio/encouragement/correct-0${i}.wav`))
  assert.equal(events.filter(e => e.type === 'stop').length, 6)
  assert.equal(events.filter(e => e.type === 'fetch').length, 6)
})

await check('muting stops current audio and blocks both unlock and future rewards', async () => {
  const { api, events } = player()
  await api.unlockEncouragementAudio()
  await api.playEncouragement()
  api.setEncouragementEnabled(false)
  assert.equal(api.getEncouragementEnabled(), false)
  assert.equal(await api.playEncouragement(), 'muted')
  assert.equal(await api.unlockEncouragementAudio(), false)
  assert.equal(events.filter(e => e.type === 'start').length, 1)
  assert.equal(events.filter(e => e.type === 'stop').length, 1)
  api.setEncouragementEnabled(true)
  assert.equal(await api.playEncouragement(), 'played')
})

await check('leaving a question cancels audio waiting for download/decode', async () => {
  const gate = deferred(), { api, events } = player({ gate })
  await api.unlockEncouragementAudio()
  const pending = api.playEncouragement()
  api.stopEncouragementAudio()
  gate.resolve()
  assert.equal(await pending, 'cancelled')
  assert.equal(events.filter(e => e.type === 'start').length, 0)
})

await check('muting while loading prevents delayed sound', async () => {
  const gate = deferred(), { api, events } = player({ gate })
  await api.unlockEncouragementAudio()
  const pending = api.playEncouragement()
  api.setEncouragementEnabled(false)
  gate.resolve()
  assert.equal(await pending, 'muted')
  assert.equal(events.filter(e => e.type === 'start').length, 0)
})

await check('a second reward supersedes the first pending reward', async () => {
  const gate = deferred(), { api, events } = player({ gate })
  await api.unlockEncouragementAudio()
  const first = api.playEncouragement(), second = api.playEncouragement()
  gate.resolve()
  assert.equal(await first, 'cancelled')
  assert.equal(await second, 'played')
  assert.equal(events.filter(e => e.type === 'start').length, 1)
})

for (const failure of ['fetchFails', 'decodeFails', 'resumeFails', 'noAudio']) {
  await check(`${failure} returns unavailable without speaking or throwing`, async () => {
    const { api, events } = player({ [failure]: true })
    await api.unlockEncouragementAudio()
    assert.equal(await api.playEncouragement(), 'unavailable')
    assert.equal(events.filter(e => e.type === 'start').length, 0)
  })
}

const componentSources = {}
async function component(name, options = {}) {
  const text = await readFile(path.join(root, `src/views/${name}.vue`), 'utf8')
  componentSources[name] = createHash('sha256').update(text).digest('hex')
  const descriptor = parse(text).descriptor
  const setup = compileScript(descriptor, { id: `voice-test-${name}` }).content
  const js = ts.transpileModule(setup, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const exports = {}, events = [], unmount = []
  const route = vue.reactive({ params: { id: 'run-old' }, query: {} })
  const services = {
    vue: { ...vue, onMounted() {}, onBeforeUnmount(callback) { unmount.push(callback) } },
    'vue-router': { useRoute: () => route, useRouter: () => ({ push() {}, replace() {} }) },
    '../api': {
      async post(url, payload) {
        events.push({ type: 'post', url, payload })
        return options.response ? await options.response.promise : { result: { correct: true } }
      },
      async api(url) { return url.startsWith('/runs/') ? trainingRun('run-new') : { skill_score: 10, answer_count: 1 } },
    },
    '../store': {
      state: vue.reactive({ user: { voice: true } }),
      notify() {}, toggleVoice() {}, prepareEncouragement() {},
      async encourage() { events.push({ type: 'reward' }); return options.reward ? await options.reward.promise : 'played' },
      async refreshDashboard() { return options.dashboard ? await options.dashboard.promise : {} },
    },
    '../audio': { stopEncouragementAudio() { events.push({ type: 'stop' }) } },
    '../scores': { formatSkillScore: String },
  }
  vm.runInNewContext(js, {
    exports,
    require(name) { return services[name] || {} },
    setInterval, clearInterval,
  })
  const state = exports.default.setup({}, { expose() {} })
  return { state, events, route, unmount: () => unmount.forEach(callback => callback()) }
}

function trainingRun(id = 'run-old', mode = 'course') {
  return { id, mode, ability_id: 'A1', status: 'active', answers: {}, questions: [
    { id: 'q-old-1', title: 'first', type: 'choice' }, { id: 'q-old-2', title: 'second', type: 'choice' },
  ] }
}

await check('training response after unmount cannot play; submitted answer is snapshotted; busy blocks switching', async () => {
  const response = deferred(), page = await component('Training', { response })
  page.state.run.value = trainingRun()
  page.state.answer.value = { value: 'original' }
  const pending = page.state.submit()
  page.state.go(1)
  assert.equal(page.state.index.value, 0)
  page.state.answer.value.value = 'later edit'
  page.unmount()
  response.resolve({ result: { correct: true } })
  await pending
  assert.equal(page.events.find(e => e.type === 'post').payload.answer.value, 'original')
  assert.equal(page.events.filter(e => e.type === 'reward').length, 0)
  assert.equal(page.state.feedback.value, undefined)
})

await check('changing training route rejects old grading response', async () => {
  const response = deferred(), page = await component('Training', { response })
  page.state.run.value = trainingRun()
  const pending = page.state.submit()
  page.route.params.id = 'run-new'
  await vue.nextTick()
  response.resolve({ result: { correct: true } })
  await pending
  assert.equal(page.state.run.value.id, 'run-new')
  assert.equal(Object.keys(page.state.run.value.answers).length, 0)
  assert.equal(page.events.filter(e => e.type === 'reward').length, 0)
  page.unmount()
})

await check('late playback status cannot be written onto the next question', async () => {
  const reward = deferred(), page = await component('Training', { reward })
  page.state.run.value = trainingRun()
  await page.state.submit()
  page.state.go(1)
  reward.resolve('played')
  await Promise.resolve()
  await Promise.resolve()
  assert.equal(page.state.audioNotice.value, '')
  assert.equal(page.state.index.value, 1)
  page.unmount()
})

await check('batch completion awaiting dashboard cannot reward after exit', async () => {
  const response = deferred(), dashboard = deferred(), page = await component('Training', { response, dashboard })
  page.state.run.value = trainingRun('run-old', 'job')
  const pending = page.state.finish()
  response.resolve({ ...trainingRun('run-old', 'job'), status: 'completed', report: { passed: true } })
  await Promise.resolve()
  await Promise.resolve()
  page.unmount()
  dashboard.resolve({})
  await pending
  assert.equal(page.events.filter(e => e.type === 'reward').length, 0)
})

await check('onboarding response after exit cannot advance steps or play', async () => {
  const response = deferred(), page = await component('Onboarding', { response })
  page.state.run.value = trainingRun()
  page.state.step.value = 6
  const pending = page.state.submitIndependent()
  page.unmount()
  response.resolve({ result: { correct: true } })
  await pending
  assert.equal(page.state.step.value, 6)
  assert.equal(page.events.filter(e => e.type === 'reward').length, 0)
})

await check('correct onboarding response rewards after step transition; next step stops it', async () => {
  const page = await component('Onboarding')
  page.state.run.value = trainingRun()
  page.state.step.value = 5
  await page.state.submitGuide()
  assert.equal(page.state.step.value, 6)
  assert.equal(page.state.busy.value, false)
  assert.equal(page.events.filter(e => e.type === 'reward').length, 1)
  assert.equal(page.events.at(-1).type, 'reward')
  page.state.step.value = 7
  assert.equal(page.events.at(-1).type, 'stop')
  page.unmount()
})

const evidence = {
  checked_at: new Date().toISOString(),
  audio_module_sha256: createHash('sha256').update(source).digest('hex'),
  component_sha256: componentSources,
  scope: 'Node VM playback state machine with fake Web Audio/fetch and compiled real Vue component lifecycle with deferred API responses; real bundled WAV bytes/manifest. Actual decoding additionally verified by build script via soundfile. This is not browser or speaker acceptance.',
  results,
}
await writeFile(path.join(root, 'docs/voice-playback-tests.json'), JSON.stringify(evidence, null, 2) + '\n')
console.log(`${results.length} checks passed`)
