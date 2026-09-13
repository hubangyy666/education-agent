<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, post } from '../api'
import { encourage, encouragePrecision, notify, prepareEncouragement, refreshDashboard } from '../store'
import { stopEncouragementAudio } from '../audio'
import Icon from '../components/Icon.vue'
import QuestionInput from '../components/QuestionInput.vue'
import PrecisionReward from '../components/PrecisionReward.vue'

const route=useRoute(),router=useRouter()
const items=ref<any[]>([]),item=ref<any>(),answer=ref<any>({}),feedback=ref<any>()
const loading=ref(true),busy=ref(false),error=ref(''),precisionReward=ref(false)
const showStandard=ref(false),standardAnswer=ref<any>(),retryRevision=ref(0)
let alive=true,viewRevision=0
const isCurrent=(revision:number)=>alive&&revision===viewRevision
function invalidateView(){viewRevision++;stopEncouragementAudio();precisionReward.value=false;showStandard.value=false;standardAnswer.value=undefined}
const isAnnotation=computed(()=>['box','polygon'].includes(item.value?.question.type))
const canViewStandard=computed(()=>isAnnotation.value&&!!feedback.value?.can_view_standard)
const validAnswer=computed(()=>{const q=item.value?.question;if(!q)return false;if(q.type==='box')return answer.value.boxes?.length&&answer.value.boxes.every((b:any)=>b.label);if(q.type==='polygon')return answer.value.points?.length>=3&&answer.value.label;if(q.type==='entity')return answer.value.start!==undefined&&answer.value.label;return !!answer.value.value})
const modeName=(mode:string)=>mode==='job'?'岗关':mode==='competition'?'赛关':'课关'
async function load(){
  const revision=viewRevision,id=route.params.id;loading.value=true;error.value='';feedback.value=undefined;answer.value={};item.value=undefined
  try{if(id){const detail=await api('/mistakes/'+id);if(!isCurrent(revision))return;item.value=detail;answer.value=JSON.parse(JSON.stringify(detail.latest_review_answer||{}));feedback.value=['box','polygon'].includes(detail.question.type)&&detail.feedback?{...detail.feedback,wrong_attempts:detail.wrong_attempts||0,can_view_standard:detail.can_view_standard===true}:undefined}else{const list=await api('/mistakes');if(isCurrent(revision))items.value=list}}
  catch(e){if(isCurrent(revision))error.value=(e as Error).message}finally{if(isCurrent(revision))loading.value=false}
}
async function submit(){
  if(!item.value||busy.value||feedback.value||showStandard.value||!validAnswer.value)return
  prepareEncouragement();const revision=viewRevision,id=item.value.id,question=item.value.question;busy.value=true;error.value=''
  try{const response=await post(`/mistakes/${id}/answer`,{answer:JSON.parse(JSON.stringify(answer.value))});if(!isCurrent(revision))return;feedback.value={...response.result,wrong_attempts:response.wrong_attempts||0,can_view_standard:response.can_view_standard===true};item.value.review_attempts=response.review_attempts;item.value.review_correct=response.result.correct;const precise=['box','polygon'].includes(question.type)&&typeof response.result.iou==='number'&&response.result.iou>.9;if(precise){precisionReward.value=true;void encouragePrecision()}else if(response.result.correct)void encourage()}
  catch(e){if(isCurrent(revision))error.value=(e as Error).message}finally{if(isCurrent(revision))busy.value=false}
}
async function viewStandard(){
  if(busy.value||!canViewStandard.value)return
  const revision=viewRevision;busy.value=true;error.value=''
  try{const result=await api(`/mistakes/${item.value.id}/standard-answer`);if(!isCurrent(revision))return;standardAnswer.value=result.standard_answer;showStandard.value=true;stopEncouragementAudio();precisionReward.value=false}
  catch(e){if(isCurrent(revision))error.value=(e as Error).message}finally{if(isCurrent(revision))busy.value=false}
}
function retry(){if(busy.value||!feedback.value)return;invalidateView();retryRevision.value++;feedback.value=undefined;error.value='';answer.value=item.value?.question.type==='box'?{boxes:[]}:item.value?.question.type==='polygon'?{points:[],label:''}:{}}
async function remove(){if(!item.value||busy.value)return;const revision=viewRevision,id=item.value.id;busy.value=true;try{await api(`/mistakes/${id}`,{method:'DELETE'});if(!isCurrent(revision))return;notify('已将题目移出错题本。');await refreshDashboard();if(isCurrent(revision))await router.push('/profile/mistakes')}catch(e){if(isCurrent(revision))error.value=(e as Error).message}finally{if(isCurrent(revision))busy.value=false}}
onMounted(load)
onBeforeUnmount(()=>{alive=false;invalidateView()})
watch(()=>route.params.id,()=>{invalidateView();busy.value=false;void load()})
</script>

<template><div class="content-width mistakes-page"><PrecisionReward v-if="precisionReward" @done="precisionReward=false"/><header class="section-heading"><div><span class="eyebrow">回到错误发生的地方，再认真做一次</span><h1>我的错题本</h1><p class="muted">重新作答只用于复习，不会改变技能分。</p></div><RouterLink to="/profile" class="btn outline small"><Icon name="ArrowLeft" :size="16"/>返回我的成长</RouterLink></header><div v-if="error" class="error-message" role="alert">{{error}}</div><div v-if="loading" class="loading-state"><Icon name="LoaderCircle" class="spin"/>正在整理错题…</div><template v-else-if="item"><div class="mistake-detail-head"><button class="text-button" @click="router.push('/profile/mistakes')"><Icon name="ArrowLeft" :size="16"/>全部错题</button><span class="pill" :class="item.mode==='job'?'orange':'purple'">{{modeName(item.mode)}}</span><span>{{item.ability_id}} · {{item.skill_id}}</span><span>累计答错 {{item.wrong_count}} 次</span></div><section class="mistake-practice"><h2>{{item.question.title}}</h2><p class="mistake-note"><Icon name="ShieldCheck" :size="16"/>本页作答保存在错题复习记录中，不进入正式训练计分。</p><QuestionInput :key="item.id+':'+retryRevision" :question="item.question" v-model="answer" :disabled="!!feedback||busy||showStandard" :standard="isAnnotation?(showStandard?standardAnswer:undefined):feedback?.standard_answer"/><div v-if="isAnnotation&&feedback" class="standard-answer-controls"><button v-if="canViewStandard&&!showStandard" class="btn outline small" :disabled="busy" @click="viewStandard"><Icon name="ScanEye" :size="17"/>{{busy?'加载中…':'查看标准答案'}}</button><p v-if="showStandard" role="status"><Icon name="LockKeyhole" :size="16"/>正在查看标准答案，标注已锁定。点击“再试一次”后清空并重新标注。</p><p v-else-if="!canViewStandard">本题连续答错 {{feedback.wrong_attempts||0}} 次；答对或连续答错 3 次后，可自行查看标准答案。</p></div><div v-if="feedback" class="answer-feedback" :class="{correct:feedback.correct}"><Icon :name="feedback.correct?'Check':'Lightbulb'" :size="25"/><div><b>{{feedback.correct?'这次答对了！':'还不完全对，再想一想。'}}</b><p>{{feedback.feedback}}</p><span v-if="feedback.iou!==null">当前交并比 {{(feedback.iou*100).toFixed(1)}}%</span></div></div><div class="mistake-actions"><button v-if="feedback&&(!feedback.correct||isAnnotation)" class="btn green" :disabled="busy" @click="retry"><Icon name="RotateCcw" :size="17"/>再试一次</button><button v-else-if="!feedback" class="btn green" :disabled="busy||!validAnswer" @click="submit">{{busy?'保存中…':'检查答案'}}<Icon name="Check" :size="17"/></button><button class="btn outline danger" :disabled="busy" @click="remove"><Icon name="Trash2" :size="17"/>移出错题本</button></div></section></template><template v-else><section v-if="items.length" class="mistake-list"><RouterLink v-for="entry in items" :key="entry.id" :to="'/profile/mistakes/'+entry.id"><span class="mistake-type"><Icon :name="entry.question.image?'ScanLine':entry.question.type==='entity'?'TextCursorInput':'FileCheck2'" :size="21"/></span><div><span><b>{{entry.ability_id}}</b> · {{modeName(entry.mode)}} · {{entry.skill_id}}</span><h2>{{entry.question.title}}</h2><small>累计答错 {{entry.wrong_count}} 次<template v-if="entry.review_attempts"> · 已复习 {{entry.review_attempts}} 次</template></small></div><span v-if="entry.review_correct" class="pill lime"><Icon name="Check" :size="14"/>复习已答对</span><Icon name="ChevronRight" :size="19"/></RouterLink></section><section v-else class="mistake-empty"><span><Icon name="CheckCheck" :size="42"/></span><h2>错题本现在是空的</h2><p>正式课关、岗关和赛关中答错的题会自动收集到这里。</p><RouterLink to="/skills" class="btn green">去练习技能<Icon name="ArrowRight" :size="17"/></RouterLink></section></template></div></template>

<style scoped>.standard-answer-controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:18px 0}.standard-answer-controls p{display:flex;align-items:center;gap:7px;color:#697568;font-size:13px;margin:0;line-height:1.8}.standard-answer-controls p svg{flex-shrink:0}</style>
