<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, post } from '../api'
import { state } from '../store'
import Icon from '../components/Icon.vue'
import JobTile from '../components/JobTile.vue'
import JobPhoto from '../components/JobPhoto.vue'
const route=useRoute(),router=useRouter(),data=ref<any>(),learning=ref<any>(),error=ref(''),actionError=ref(''),busy=ref(false),selected=ref(0),evidence=ref(''),run=ref<any>(),saved=ref('')
let loadId=0
const task=computed(()=>data.value?.task),role=computed(()=>data.value?.role),steps=computed(()=>task.value?.steps||[])
const step=computed(()=>steps.value[selected.value]),progress=computed(()=>learning.value?.progress||{}),record=computed(()=>progress.value[step.value?.id]||{})
const unlocked=computed(()=>steps.value.slice(0,selected.value).every((s:any)=>progress.value[s.id]?.completed))
const validEvidence=computed(()=>{const s=evidence.value.replace(/[\s\p{P}\p{S}]/gu,'');return s.length>=15&&new Set(s).size>=7})
const canSave=computed(()=>unlocked.value&&validEvidence.value&&!busy.value&&(step.value?.kind!=='practice'||run.value?.report?.passed))
const stepIcons=['BookOpen','ClipboardList','ScanLine','FileCheck2']
const stepHints=['理解工作','准备操作','动手实践','检查与复盘']
function skillUrl(s:any){return {path:'/skills/'+s.ability_id,query:{skill:s.skill_id,roleId:role.value.id,taskId:task.value.id}}}
function draftKey(){return `job-draft:${state.user?.username}:${role.value?.id}:${task.value?.id}:${step.value?.id}`}
function restoreDraft(){evidence.value=sessionStorage.getItem(draftKey())||'';actionError.value='';saved.value=''}
watch(evidence,()=>{if(task.value)sessionStorage.setItem(draftKey(),evidence.value)})
watch(selected,restoreDraft)
async function load(){const id=++loadId;error.value='';data.value=undefined;learning.value=undefined;run.value=undefined;selected.value=0
  try{
    if(route.params.learningId){const old=await api('/job-learning/'+route.params.learningId);if(id===loadId)await router.replace(`/jobs/${old.role_id}/tasks/${old.task_id}`);return}
    const result=await api(`/jobs/${route.params.roleId}/tasks/${route.params.taskId}`);if(id!==loadId)return;data.value=result;learning.value=result.learning
    if(result.learning){const pending=result.task.steps.findIndex((s:any)=>!result.learning.progress[s.id]?.completed);selected.value=pending<0?result.task.steps.length-1:pending}restoreDraft()
    const runId=result.learning?.progress?.practice?.run_id;if(runId)run.value=await api('/runs/'+runId)
  }catch(e){if(id===loadId)error.value=(e as Error).message}
}
async function enroll(){if(!learning.value)learning.value=await post(`/jobs/${role.value.id}/tasks/${task.value.id}/enroll`,{});return learning.value}
async function selectStep(index:number){selected.value=index;await nextTick();document.getElementById('task-step-detail')?.scrollIntoView({block:'start',behavior:'smooth'})}
async function submitStep(){if(!canSave.value)return;busy.value=true;actionError.value='';try{const l=await enroll();learning.value=await post(`/job-learning/${l.id}/steps/${step.value.id}`,{evidence:evidence.value,run_id:record.value.run_id});sessionStorage.removeItem(draftKey());saved.value='本步骤记录已保存。'}catch(e){actionError.value=(e as Error).message}finally{busy.value=false}}
async function startPractice(){if(busy.value||!unlocked.value)return;busy.value=true;actionError.value='';try{const l=await enroll();const result=await post(`/job-learning/${l.id}/steps/${step.value.id}/start`,{});await router.push({path:'/train/'+result.id,query:{roleId:role.value.id,taskId:task.value.id}})}catch(e){actionError.value=(e as Error).message}finally{busy.value=false}}
onMounted(load);watch(()=>[route.params.roleId,route.params.taskId,route.params.learningId].join('/'),load)
</script>
<template>
  <div class="content-width jp-page jp-lesson-page" :class="'jp-'+(role?.color||'blue')">
    <RouterLink :to="'/jobs/'+route.params.roleId" class="jp-back"><Icon name="ArrowLeft" :size="17"/>返回岗位</RouterLink>
    <div v-if="error" class="jp-state" role="alert"><p>{{error}}</p><button class="btn outline" @click="load">重新加载</button></div><div v-else-if="!task" class="jp-state" role="status">正在加载任务讲解…</div>
    <template v-else>
      <header class="jp-lesson-heading"><span class="jp-eyebrow">{{role.title}} · 典型工作任务</span><h1>{{task.title}}</h1><p>{{task.summary}}</p><div class="jp-meta"><span><Icon name="Clock3" :size="16"/>约 {{task.duration_minutes}} 分钟</span><span><Icon name="BookOpen" :size="16"/>{{steps.length}} 个步骤</span><span>{{task.difficulty}}</span></div></header>
      <nav class="jp-anchor-nav" aria-label="任务内容"><a href="#task-scenario">工作情境</a><a href="#task-steps">操作讲解</a><a href="#task-standards">规范与检查</a><a href="#task-skills">知识与技能</a></nav>
      <section id="task-scenario" class="jp-overview jp-task-overview"><div><span class="jp-eyebrow">从工作现场开始</span><h2>这项任务发生在什么场景？</h2><p>{{task.work_scenario}}</p><h3>具体要做什么</h3><p>{{task.description}}</p><div class="jp-deliverable"><Icon name="FolderOpen" :size="21"/><div><b>完成后，要交付</b><ul class="jp-list"><li v-for="item in task.deliverables" :key="item">{{item}}</li></ul></div></div></div><JobPhoto v-if="task.image" :photo="task.image" :industrial="role.id==='industrial'"/></section>
      <section id="task-steps" class="jp-step-section"><div class="jp-section-heading"><div><span class="jp-eyebrow">一步一步，理解操作</span><h2>这项任务怎么完成？</h2></div><span>点击步骤查看详细讲解</span></div><div class="jp-strip jp-step-strip"><JobTile v-for="(s,i) in steps" :key="s.id" :label="s.title" :hint="'步骤 '+String(Number(i)+1).padStart(2,'0')" :icon="stepIcons[Number(i)]" :caption="stepHints[Number(i)]" :active="selected===Number(i)" :done="progress[s.id]?.completed" @select="selectStep(Number(i))"/></div>
        <article v-if="step" id="task-step-detail" class="jp-step-detail"><div class="jp-step-number">{{String(selected+1).padStart(2,'0')}}</div><div class="jp-step-copy"><span class="jp-eyebrow">{{stepHints[selected]}}</span><h2>{{step.title}}</h2><p class="jp-step-lead">{{step.instruction}}</p><ol class="jp-explanation"><li v-for="item in step.explanation" :key="item.title"><h3>{{item.title}}</h3><p>{{item.text}}</p></li></ol><div class="jp-takeaway"><Icon name="Lightbulb" :size="22"/><div><b>做完这一步，检查一下</b><p>{{step.output}}</p></div></div>
          <details class="jp-practice-record" :key="step.id" :open="step.kind==='practice'"><summary>{{step.kind==='practice'?'动手训练与操作记录':'记录本步骤的学习过程'}}<span>{{record.completed?'已保存':learning?`${learning.percent}% 已完成`:'可保存到你的学习记录'}}</span></summary>
            <p v-if="!unlocked" class="jp-record-note">讲解可以自由阅读。若要保存训练进度，请先完成前面步骤的学习记录。</p>
            <template v-if="step.kind==='practice'"><p>完成本任务的 5 道互动练习，提交后查看反馈和训练报告。</p><div v-if="run?.report" class="jp-run-summary"><b>{{Math.round(run.report.score)}} 分 · {{run.report.passed?'训练通过':'还需练习'}}</b><p>{{run.report.criteria}}</p></div><div class="jp-practice-actions"><button v-if="!record.completed&&!run?.report?.passed" class="jp-primary" :disabled="busy||!unlocked" @click="startPractice"><Icon name="Play" :size="17"/>{{busy?'正在准备…':run?.status==='completed'?'重新训练':run?'继续训练':'开始互动训练'}}</button><RouterLink v-if="record.run_id" :to="{path:'/train/'+record.run_id,query:{roleId:role.id,taskId:task.id}}" class="jp-text-link">{{run?.status==='completed'?'查看训练报告':'打开训练记录'}}<Icon name="ArrowUpRight" :size="16"/></RouterLink></div></template>
            <p v-if="record.completed" class="jp-saved-evidence">{{record.evidence}}</p><form v-else @submit.prevent="submitStep"><label for="task-evidence">{{step.kind==='practice'?'写下你的操作与自检过程':'结合上面的讲解，写下你的理解'}}</label><textarea id="task-evidence" v-model="evidence" :disabled="busy||!unlocked" rows="4" maxlength="4000" placeholder="说明你做了什么、依据哪项要求，以及需要注意的问题（至少 15 个有效字符）。"/><small>文字记录用于复盘，实际操作结果以训练报告为准。</small><button type="submit" class="jp-primary" :disabled="!canSave">{{busy?'正在保存…':'保存本步骤记录'}}<Icon name="Check" :size="17"/></button><p v-if="step.kind==='practice'&&!run?.report?.passed" class="jp-record-note">通过互动训练后，可以保存本步骤的操作记录。</p></form><p v-if="actionError" class="error-message" role="alert">{{actionError}}</p><p v-if="saved" role="status">{{saved}}</p>
          </details><button v-if="selected<steps.length-1" class="jp-next-step" @click="selectStep(selected+1)">阅读下一步：{{steps[selected+1].title}}<Icon name="ArrowRight" :size="18"/></button>
        </div></article>
      </section>
      <section id="task-standards"><div class="jp-section-heading"><h2>做得规范，也要交得清楚</h2></div><div class="jp-info-grid"><section class="jp-info jp-blue"><span class="jp-info-symbol"><Icon name="ClipboardList" :size="24"/></span><h3>操作规范</h3><ul class="jp-list"><li v-for="s in task.norms" :key="s">{{s}}</li></ul></section><section class="jp-info jp-orange"><span class="jp-info-symbol"><Icon name="ShieldCheck" :size="24"/></span><h3>质量要求</h3><ul class="jp-list"><li v-for="s in task.quality" :key="s">{{s}}</li></ul></section><section class="jp-info jp-green"><span class="jp-info-symbol"><Icon name="FileCheck2" :size="24"/></span><h3>考核方式</h3><ul class="jp-list"><li v-for="s in task.assessment" :key="s">{{s}}</li></ul></section></div></section>
      <section id="task-skills" class="jp-knowledge-section"><div class="jp-section-heading"><div><span class="jp-eyebrow">把操作和原理连起来</span><h2>相关知识与技能</h2></div><span>点击进入对应技能训练</span></div><div class="jp-knowledge-list"><RouterLink v-for="(k,i) in task.knowledge" :key="k.title" :to="skillUrl(k)"><span>{{String(Number(i)+1).padStart(2,'0')}}</span><div><h3>{{k.title}}</h3><p>{{k.description}}</p><small>{{k.skill_id}} · 学习对应技能</small></div><Icon name="ArrowUpRight" :size="20"/></RouterLink></div><div class="jp-skill-grid"><RouterLink v-for="skill in task.skills" :key="skill.skill_id" :to="skillUrl(skill)"><span class="jp-skill-symbol"><Icon name="Layers3" :size="22"/></span><div><small>{{skill.skill_id}}</small><h3>{{skill.title}}</h3><p>{{skill.reason}}</p></div><Icon name="ChevronRight" :size="18"/></RouterLink></div></section>
      <details class="jp-sources"><summary>任务资料与延伸阅读 <span>{{data.sources.length}} 项</span></summary><p>结合 {{role.industry}} 的工作流程与 {{role.majors.map((m:any)=>m.name).join('、')}} 专业要求编写。任务讲解为固定内容，可随时回看。</p><a v-for="source in data.sources" :key="source.id" :href="source.url" target="_blank" rel="noopener noreferrer"><span><b>{{source.title}}</b><small>{{source.publisher}} · {{source.summary}}</small></span><Icon name="ArrowUpRight" :size="16"/></a></details>
    </template>
  </div>
</template>
