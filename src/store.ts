import { reactive, watch } from 'vue'
import { api, post } from './api'
import { setEncouragementEnabled, unlockEncouragementAudio, playEncouragement, stopEncouragementAudio } from './audio'
export interface User { username: string; name: string; role: 'student' | 'admin'; onboarding: boolean; goal: string; daily_goal: number; voice: boolean }
export const state = reactive({ user: null as User | null, ready: false, dashboard: null as any, toast: '', toastKind: 'success', voiceSaving: false })
watch(() => state.user?.voice, enabled => setEncouragementEnabled(Boolean(enabled)), { immediate: true, flush: 'sync' })
let toastTimer: ReturnType<typeof setTimeout>
export function notify(message: string, kind = 'success') { state.toast = message; state.toastKind = kind; clearTimeout(toastTimer); toastTimer = setTimeout(() => state.toast = '', 4800) }
export async function loadUser() { try { state.user = await api('/auth/me') } catch { state.user = null } state.ready = true }
export async function refreshDashboard() { state.dashboard = await api('/dashboard'); return state.dashboard }
export async function logout() { await post('/auth/logout'); state.user = null; state.dashboard = null }
export function prepareEncouragement() { if (state.user?.voice) void unlockEncouragementAudio() }
export function encourage() { return state.user?.voice ? playEncouragement('correct') : Promise.resolve('muted' as const) }
export async function toggleVoice() {
  if (!state.user || state.voiceSaving) return
  const user = state.user, previous = user.voice
  user.voice = !previous
  if (user.voice) prepareEncouragement(); else stopEncouragementAudio()
  state.voiceSaving = true
  try { const result = await post<User>('/profile/voice', { voice: user.voice }); if (state.user?.username === user.username) state.user = result }
  catch (e) { if (state.user?.username === user.username) state.user.voice = previous; notify((e as Error).message, 'error') }
  finally { state.voiceSaving = false }
}
