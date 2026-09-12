<script setup lang="ts">
import { computed,nextTick,ref,onMounted,onBeforeUnmount,watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import { api,post } from '../api'
import { notify } from '../store'
import Icon from '../components/Icon.vue'
import { formatSkillScore, skillScore } from '../scores'
const route=useRoute(),router=useRouter(),data=ref<any>(),error=ref(''),busy=ref(''),update=ref<any>(),requesting=ref(false),pollError=ref('');let poll:ReturnType<typeof setTimeout>|undefined,generation=0
const updating=computed(()=>requesting.value||update.value?.status==='running')
const jobReturn=computed(()=>typeof route.query.taskId==='string'&&typeof route.query.roleId==='string'?`/jobs/${encodeURIComponent(route.query.roleId)}/tasks/${encodeURIComponent(route.query.taskId)}`:typeof route.query.jobLearning==='string'&&typeof route.query.roleId==='string'?`/jobs/${encodeURIComponent(route.query.roleId)}/learn/${encodeURIComponent(route.query.jobLearning)}`:typeof route.query.roleId==='string'?`/jobs/${encodeURIComponent(route.query.roleId)}`:'')
async function focusSkill(){await nextTick();if(typeof route.query.skill==='string')document.getElementById('skill-'+route.query.skill)?.scrollIntoView({block:'center',behavior:'smooth'})}
watch(()=>route.query.skill,focusSkill)
async function load(focus=true){
  const current=generation,aid=String(route.params.id)
  try{const result=await api('/abilities/'+aid);if(current!==generation)return
    data.value=result;update.value=result.update;error.value=''
    if(focus)await focusSkill()
    if(update.value?.status==='running')schedulePoll()
  }catch(e){if(current===generation)error.value=(e as Error).message}
}
watch(()=>route.params.id,()=>{generation++;clearTimeout(poll);data.value=undefined;update.value=undefined;error.value='';pollError.value='';requesting.value=false;load()});onMounted(()=>load());onBeforeUnmount(()=>{generation++;clearTimeout(poll)})
async function start(level:any){if(busy.value||updating.value)return;busy.value=level.id;try{const run=await post('/runs/start',{level_id:level.id});router.push({path:'/train/'+run.id,query:route.query})}catch(e){notify((e as Error).message,'error')}finally{busy.value=''}}
async function refresh(){
  if(updating.value)return
  const current=generation,aid=String(route.params.id);requesting.value=true;pollError.value=''
  try{const result=await post(`/abilities/${aid}/refresh`);if(current!==generation)return;update.value=result;schedulePoll()}
  catch(e){if(current!==generation)return;notify((e as Error).message,'error');await load(false)}
  finally{if(current===generation)requesting.value=false}
}
function schedulePoll(){clearTimeout(poll);poll=setTimeout(pollUpdate,1000)}
async function pollUpdate(){
  const current=generation,aid=String(route.params.id)
  try{const result=await api(`/abilities/${aid}/refresh`);if(current!==generation)return
    update.value=result;pollError.value=''
    if(result.status==='running')schedulePoll()
    else if(result.status==='completed'){notify(`题集 V${result.version} 已发布，进入关卡即可练习新版题目。`);await load(false)}
  }catch(e){if(current!==generation)return;pollError.value='暂时无法读取进度，正在重新连接。';schedulePoll()}
}
</script>
<template><div class="content-width module-page"><header class="module-toolbar"><RouterLink to="/skills" class="back-link"><Icon name="ArrowLeft" :size="18"/>返回技能地图</RouterLink><button class="btn outline small" :disabled="updating||!!busy" @click="refresh"><Icon name="RefreshCw" :size="16" :class="{spin:update?.status==='running'}"/>{{requesting?'正在提交…':update?.status==='running'?`更新中 ${update.progress}%`:'更新题目'}}</button></header><div v-if="jobReturn" class="job-return-banner"><span>正在学习岗位关联技能<span v-if="route.query.skill"> · {{route.query.skill}}</span></span><RouterLink :to="jobReturn"><Icon name="ArrowLeft" :size="15"/>返回岗位任务</RouterLink></div><div v-if="error" class="error-message">{{error}}</div><div v-if="update?.status==='running'" class="update-banner" role="status"><div><Icon name="RefreshCw" class="spin"/>{{update.stage}}<b>{{update.progress}}%</b></div><div class="progress-line"><span :style="{width:update.progress+'%'}"></span></div></div><div v-if="pollError" class="error-message" role="status">{{pollError}}</div><div v-if="update?.status==='failed'" class="error-message" role="alert">更新未完成：{{update.stage}}。当前题集 V{{data?.version}} 仍可练习，点击“更新题目”可重试。</div><div v-if="update?.status==='completed'" class="update-banner" role="status"><div><Icon name="Check"/>已发布 V{{update.version}} 题集<span v-if="update.new_question_count!=null"> · 新增 {{update.new_question_count}} 道，共 {{update.question_count}} 道</span></div><small>进入关卡使用新版题目，已有训练记录和成绩保留。</small></div><div v-if="data" class="module-layout"><aside class="module-info"><div class="module-icon" :class="data.color"><Icon :name="data.icon" :size="72"/></div><span class="eyebrow">{{data.id}} · 能力训练</span><h1>{{data.name}}</h1><p>{{data.description}}</p><div class="course-meta"><span><Icon name="Layers3" :size="17"/>7 个关卡 · 全部开放</span><span><Icon name="Shapes" :size="17"/>55 道练习</span></div><div class="module-mastery"><span>技能分<b>{{formatSkillScore(data.skill_score)}} / 10 分</b></span><div class="progress-line"><span :style="{width:skillScore(data.skill_score)*10+'%'}"></span></div></div><p class="score-explanation">{{data.answer_count?`已判定 ${data.answer_count} 题，答对 ${data.correct_count} 题`:"暂无答题记录"}} · 正确率 × 10</p><div class="mode-legend"><span><b class="pill purple">课</b>分步学会</span><span><b class="pill orange">岗</b>整包实战</span><span><b class="pill lime">赛</b>限时挑战</span></div><small class="version-note">题集版本 {{data.version}} · 完成记录独立保留</small></aside><section class="level-path" aria-label="关卡路径"><div v-for="(level,i) in data.levels" :key="level.id" :id="level.mode==='course'?'skill-'+level.skill_id:level.id" class="level-step" :class="{'job-skill-highlight':route.query.skill===level.skill_id&&level.mode==='course',current:!level.completed,completed:level.completed}" :style="{'--shift': [0,-48,42,-24,36,-18,0][Number(i)]+'px'}"><div class="level-connector" v-if="Number(i)<data.levels.length-1"></div><div class="level-section-caption" v-if="i===0||level.mode!=='course'"><b>{{level.mode==='course'?'第 1 阶段':level.mode==='job'?'第 2 阶段':'最终挑战'}}</b><span>{{level.mode==='course'?'理解与练习':level.mode==='job'?'岗位实战':'技能竞赛'}}</span></div><button class="level-hit" :disabled="!!busy||updating" @click="start(level)" :aria-label="`${level.name}，${level.completed?'已完成，可再次训练':'开始训练'}`"><span class="level-coin"><Icon :name="busy===level.id?'LoaderCircle':level.completed?'Check':level.mode==='job'?'BriefcaseBusiness':level.mode==='competition'?'Trophy':'BookOpen'" :size="30" :class="{spin:busy===level.id}"/></span><span class="level-name"><strong>{{level.name}}</strong><small>{{level.completed?`已完成 · 最佳成绩 ${Math.round(level.best_score)} 分`:`${level.count} 道练习 · 约 ${level.minutes} 分钟`}}</small><small v-if="level.mode==='course'">技能分 {{formatSkillScore(level.skill_score)}} / 10 分</small></span><span v-if="!level.completed" class="level-go"><Icon name="Play" :size="15"/></span></button></div></section></div></div></template>

<style scoped>
.score-explanation{font-size:12px!important;line-height:1.7}.course-meta{flex-wrap:wrap;gap:12px}.update-banner small{display:block;margin-top:10px;line-height:1.6}
</style>
