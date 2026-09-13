/** Pre-rendered neural voice encouragement. User preference is persisted by the API. */
const clips = [
  '/audio/encouragement/correct-01.wav',
  '/audio/encouragement/correct-02.wav',
  '/audio/encouragement/correct-03.wav',
  '/audio/encouragement/correct-04.wav',
  '/audio/encouragement/correct-05.wav',
  '/audio/encouragement/correct-06.wav',
] as const
const precisionClip = '/audio/precision/congratulations.wav'

export type EncouragementPlayback = 'played' | 'muted' | 'unavailable' | 'cancelled'

let enabled = true
let context: AudioContext | undefined
let source: AudioBufferSourceNode | undefined
let revision = 0
let nextClip = 0
const buffers = new Map<string, Promise<AudioBuffer>>()

function audioContext(): AudioContext | undefined {
  if (typeof window === 'undefined') return undefined
  if (!context || context.state === 'closed') {
    const AudioContextClass = window.AudioContext ||
      (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioContextClass) return undefined
    try { context = new AudioContextClass() } catch { return undefined }
    buffers.clear()
  }
  return context
}

function loadClip(audio: AudioContext, path: string): Promise<AudioBuffer> {
  const existing = buffers.get(path)
  if (existing) return existing
  const pending = fetch(path)
    .then(response => {
      if (!response.ok) throw new Error('Encouragement audio unavailable')
      return response.arrayBuffer()
    })
    .then(data => audio.decodeAudioData(data))
    .catch(error => { buffers.delete(path); throw error })
  buffers.set(path, pending)
  return pending
}

export function getEncouragementEnabled(): boolean { return enabled }

export function setEncouragementEnabled(value: boolean): void {
  enabled = value
  if (!enabled) stopEncouragementAudio()
}

/** Call synchronously from a submit/start/sound-toggle click, before awaiting the API. */
export async function unlockEncouragementAudio(): Promise<boolean> {
  if (!enabled) return false
  const audio = audioContext()
  if (!audio) return false
  try {
    // resume() must be requested while user activation is still available.
    await audio.resume()
    if (audio.state !== 'running') return false
    // Cache a real local clip without playing any greeting or instruction.
    void loadClip(audio, clips[nextClip % clips.length]).catch(() => undefined)
    void loadClip(audio, precisionClip).catch(() => undefined)
    return true
  } catch { return false }
}

/** Stop both current playback and any playback still waiting for a download/decode. */
export function stopEncouragementAudio(): void {
  revision++
  if (source) {
    try { source.stop() } catch { /* It may already have ended. */ }
    source.disconnect()
    source = undefined
  }
}

/** Only call after the deterministic grader confirms a correct answer. */
export async function playEncouragement(_kind: 'correct' = 'correct'): Promise<EncouragementPlayback> {
  return playClip(clips[nextClip % clips.length], true)
}

/** A downloaded CC0 human voice recording, distinct from ordinary neural encouragement. */
export async function playPrecisionReward(): Promise<EncouragementPlayback> {
  return playClip(precisionClip, false)
}

async function playClip(path: string, rotate: boolean): Promise<EncouragementPlayback> {
  if (!enabled) return 'muted'
  stopEncouragementAudio()
  const currentRevision = revision
  const audio = audioContext()
  if (!audio || audio.state !== 'running') return 'unavailable'
  try {
    const buffer = await loadClip(audio, path)
    if (!enabled) return 'muted'
    if (currentRevision !== revision) return 'cancelled'
    if (audio.state !== 'running') return 'unavailable'
    const nextSource = audio.createBufferSource()
    nextSource.buffer = buffer
    nextSource.connect(audio.destination)
    nextSource.onended = () => {
      nextSource.disconnect()
      if (source === nextSource) source = undefined
    }
    source = nextSource
    nextSource.start()
    if (rotate) nextClip = (nextClip + 1) % clips.length
    return 'played'
  } catch {
    // Existing result text remains visible. A missing asset never affects grading.
    return currentRevision === revision ? 'unavailable' : 'cancelled'
  }
}
