import { reactive } from 'vue'
import { api, post } from './api'
export interface User { username: string; name: string; onboarding: boolean; goal: string; daily_goal: number; voice: boolean }
export const state = reactive({ user: null as User | null, ready: false, dashboard: null as any, toast: '', toastKind: 'success' })
let toastTimer: ReturnType<typeof setTimeout>
export function notify(message: string, kind = 'success') { state.toast = message; state.toastKind = kind; clearTimeout(toastTimer); toastTimer = setTimeout(() => state.toast = '', 4800) }
export async function loadUser() { try { state.user = await api('/auth/me') } catch { state.user = null } state.ready = true }
export async function refreshDashboard() { state.dashboard = await api('/dashboard'); return state.dashboard }
export async function logout() { await post('/auth/logout'); state.user = null; state.dashboard = null }
export function speak(text: string) { if (state.user?.voice && 'speechSynthesis' in window) { speechSynthesis.cancel(); const speech = new SpeechSynthesisUtterance(text); speech.lang = 'zh-CN'; speech.rate = 1.05; speechSynthesis.speak(speech) } }
