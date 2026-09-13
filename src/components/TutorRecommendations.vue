<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from './Icon.vue'

const props = defineProps<{ resources: any[] }>()
const router = useRouter()
const starting = ref(''), error = ref('')
let controller: AbortController | undefined, disposed = false
const recommendations = computed(() => {
  const seen = new Set<string>()
  return props.resources.filter(resource => {
    if (resource.resource_type !== 'level' || !/^A(?:[1-9]|10)-(?:L[1-5]|JOB|RACE)$/.test(resource.level_id || '')
      || resource.id !== `level:${resource.level_id}` || seen.has(resource.level_id)) return false
    seen.add(resource.level_id)
    return true
  }).slice(0, 3)
})
function modeName(mode: string) { return mode === 'job' ? '岗关' : mode === 'competition' ? '赛关' : '课关' }
async function start(resource: any) {
  if (starting.value || disposed) return
  starting.value = resource.level_id
  error.value = ''
  controller = new AbortController()
  try {
    const run = await api('/runs/start', {
      method: 'POST', body: JSON.stringify({ level_id: resource.level_id }), signal: controller.signal,
    })
    if (!disposed) await router.push('/train/' + run.id)
  } catch (cause) {
    if (!disposed) error.value = (cause as Error).message
  } finally {
    if (!disposed) starting.value = ''
  }
}
onBeforeUnmount(() => { disposed = true; controller?.abort() })
</script>

<template>
  <section v-if="recommendations.length" class="tutor-recommendations" aria-label="相关题目推荐">
    <div class="recommendations-heading"><Icon name="BookOpen" :size="16"/><b>接着练一练</b><span>相关关卡</span></div>
    <div class="recommendation-list">
      <button v-for="resource in recommendations" :key="resource.id" type="button"
        class="practice-card" :disabled="!!starting" :aria-busy="starting === resource.level_id"
        :aria-label="`开始练习：${resource.ability_name} · ${resource.title}（${modeName(resource.mode)}）`"
        @click="start(resource)">
        <span class="practice-icon" :class="resource.color"><Icon :name="resource.icon || 'BookOpen'" :size="23"/></span>
        <span class="practice-info"><small>{{resource.ability_name}} · {{modeName(resource.mode)}}</small><strong>{{resource.title}}</strong></span>
        <span class="practice-action">{{starting === resource.level_id ? '准备中…' : '开始练习'}}<Icon :name="starting === resource.level_id ? 'LoaderCircle' : 'ArrowRight'" :class="{spin: starting === resource.level_id}" :size="16"/></span>
      </button>
    </div>
    <p v-if="error" class="practice-error" role="alert">{{error}}</p>
  </section>
</template>

<style scoped>
.tutor-recommendations{margin-top:18px;padding-top:15px;border-top:1px solid #e5e8ef}
.recommendations-heading{display:flex;align-items:center;gap:7px;margin-bottom:10px;color:#38425a;font-size:13px}
.recommendations-heading b{font-weight:650}.recommendations-heading>span{margin-left:auto;color:#777f90;font-size:11px}
.recommendation-list{display:grid;gap:8px}
.practice-card{display:flex;align-items:center;gap:12px;width:100%;min-width:0;padding:13px;border:1px solid #dce2ee;border-bottom-width:3px;border-radius:14px;background:#fff;text-align:left;color:#273249;transition:border-color .16s,background .16s}
.practice-card:hover:not(:disabled){background:#f8faff;border-color:#a8b9e5}
.practice-card:focus-visible{outline:3px solid #4165db;outline-offset:3px}
.practice-card:disabled{cursor:wait;opacity:.65}
.practice-icon{display:grid;place-items:center;flex:0 0 44px;height:44px;border-radius:12px;background:#eef0fb;color:#7258b4}
.practice-icon.orange,.practice-icon.yellow{background:#fff2df;color:#a56b18}.practice-icon.lime{background:#eaf6e6;color:#4b7a34}.practice-icon.blue{background:#eaf1ff;color:#4165db}.practice-icon.pink{background:#faeafa;color:#a4509f}
.practice-info{display:flex;flex:1;min-width:0;flex-direction:column;gap:4px}
.practice-info small{color:#6c7383;font-size:11px;line-height:1.5}.practice-info strong{font-size:14px;line-height:1.5;overflow-wrap:anywhere}
.practice-action{display:flex;align-items:center;gap:5px;flex-shrink:0;color:#315fe9;font-size:12px;font-weight:600}
.practice-error{margin:9px 0 0;color:#b32c3c;font-size:12px;line-height:1.6}
@media(max-width:480px){.practice-card{gap:9px;padding:10px;flex-wrap:wrap}.practice-icon{flex-basis:36px;height:36px;border-radius:10px}.practice-info small{font-size:10px}.practice-action{flex-basis:100%;justify-content:flex-end}.recommendations-heading>span{display:none}}
@media(prefers-reduced-motion:reduce){.practice-card{transition:none}}
</style>
