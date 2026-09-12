<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import Icon from './Icon.vue'
const props=withDefaults(defineProps<{floating?:boolean;stage?:boolean;runId?:string;questionId?:string;disabled?:boolean;nudge?:string}>(),{floating:false,stage:false,disabled:false,nudge:''})
const emit=defineEmits<{openChange:[value:boolean]}>()
const open=ref(false),input=ref(''),busy=ref(false),error=ref('');const messages=ref<any[]>([]);const list=ref<HTMLElement>();let controller:AbortController|undefined
const launchNudge=computed(()=>props.nudge||'需要一点提示吗？')
function setOpen(value:boolean){open.value=value;emit('openChange',value)}
function handleEscape(event:KeyboardEvent){if(event.key==='Escape'&&props.stage&&open.value)setOpen(false)}
function cleanText(text:string){return (text||'').replaceAll('**','').replaceAll('`','').replace(/\n{3,}/g,'\n\n')}
const announcement=computed(()=>busy.value?'小基正在整理回答':cleanText([...messages.value].reverse().find(m=>m.role==='assistant')?.text||''))
function uniqueSources(sources:any[]=[]){const seen=new Set<string>();return sources.filter(s=>{const key=`${s.id||''}|${s.source_url||''}`;if(!s.source_url||seen.has(key))return false;seen.add(key);return true})}
function uniqueResources(resources:any[]=[]){const seen=new Set<string>();return resources.filter(r=>{if(!r.url||seen.has(r.id))return false;seen.add(r.id);return true})}
function providerLabel(provider:string){return provider==='deepseek'?'AI 生成说明':props.runId?'课程与题目事实提示':'平台提示'}
watch(()=>props.questionId,()=>{controller?.abort();busy.value=false;messages.value=[];error.value=''})
onMounted(()=>window.addEventListener('keydown',handleEscape))
onBeforeUnmount(()=>{controller?.abort();window.removeEventListener('keydown',handleEscape)})
async function scroll(){await nextTick();list.value?.scrollTo({top:list.value.scrollHeight,behavior:'smooth'})}
async function send(text?:string,hintRequest=false){
  const message=(text||input.value).trim();if(!message||busy.value||props.disabled)return
  setOpen(true);input.value='';error.value='';messages.value.push({role:'user',text:message});busy.value=true
  const reply:any={role:'assistant',text:'',sources:[],resources:[],provider:''};messages.value.push(reply);controller=new AbortController();const activeController=controller;await scroll()
  try{
    const response=await fetch('/api/ai/chat',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({message,mode:props.runId?'QUESTION_TUTOR':'GENERAL_TUTOR',run_id:props.runId,question_id:props.questionId,hint_request:hintRequest,history:messages.value.slice(0,-2).map(m=>({role:m.role,text:m.text}))})})
    if(!response.ok){const e=await response.json();throw new Error(e.detail||'暂时无法回复，请再试一次。')}
    const reader=response.body!.getReader();const decoder=new TextDecoder();let buffer=''
    while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const frames=buffer.split('\n\n');buffer=frames.pop()||'';for(const frame of frames){const event=frame.match(/event: (\w+)/)?.[1];const raw=frame.match(/data: (.+)/)?.[1];if(!raw)continue;const data=JSON.parse(raw);if(event==='token')reply.text+=data.text;if(event==='done')Object.assign(reply,data)}messages.value=[...messages.value];await scroll()}
  }catch(e){if(controller===activeController&&(e as Error).name!=='AbortError')error.value=(e as Error).message}finally{if(controller===activeController)busy.value=false}
}
defineExpose({send})
</script>
<template>
<div :class="['tutor',{'tutor-floating':floating,'tutor-stage':stage,'is-open':open,'has-messages':messages.length}]">
  <button v-if="floating" class="mentor-launch" :class="{'has-nudge':launchNudge&&!open}" :disabled="disabled" @click="setOpen(!open)" aria-label="向小基提问" :aria-expanded="open"><span v-if="!open" class="mentor-nudge" :class="{periodic:!nudge}" :role="nudge?'status':undefined" :aria-live="nudge?'polite':undefined" :aria-hidden="!nudge">{{launchNudge}}</span><img src="/mentor-v2.png" alt="小基，AI 学习导师"/></button>
  <button v-if="stage&&open" class="tutor-stage-close" type="button" aria-label="关闭 AI 学习导师" @click="setOpen(false)"><Icon name="X" :size="20"/></button>
  <section v-if="stage&&open&&!messages.length" class="tutor-stage-intro" aria-labelledby="tutor-stage-title">
    <h2 id="tutor-stage-title">今天想一起解决什么？</h2>
    <div class="tutor-stage-orbit">
      <img src="/mentor-v2.png" alt="小基，AI 学习导师"/>
      <button type="button" @click="send('什么是 IoU？')"><Icon name="ScanLine" :size="17"/>理解 IoU</button>
      <button type="button" @click="send('工业缺陷标注需要注意什么？')"><Icon name="SearchCheck" :size="17"/>工业缺陷标注</button>
      <button type="button" @click="send('我下一步应该学什么？')"><Icon name="Waypoints" :size="17"/>规划下一步</button>
      <button type="button" @click="send('怎样检查标注是否符合规范？')"><Icon name="ClipboardCheck" :size="17"/>检查标注规范</button>
    </div>
  </section>
  <section v-if="open&&(!stage||messages.length)" class="tutor-chat" aria-label="AI 学习导师">
    <header><div class="tutor-avatar"><img src="/mentor-v2.png" alt=""/></div><div><b>小基 · 你的学习导师</b><small>{{runId?'一起观察，自己找到答案':'数据标注岗位知识答疑'}}</small></div><button v-if="!stage" class="icon-button" aria-label="收起对话" @click="setOpen(false)"><Icon name="X" :size="18"/></button></header>
    <span class="sr-only" role="status" aria-live="polite">{{announcement}}</span>
    <div class="chat-messages" ref="list">
      <div v-if="!messages.length" class="chat-welcome"><p>你好！我会陪你一起学会数据标注。</p><p>{{runId?'告诉我你卡在哪里，我们一步一步来看。':'可以问我标注规范，也可以一起规划接下来的学习。'}}</p></div>
      <div v-for="(m,i) in messages" :key="i" class="chat-message" :class="m.role">
        <div class="message-text">{{cleanText(m.text) || '正在查找相关资料…'}}</div>
        <small v-if="m.role==='assistant' && m.text" class="ai-label">{{providerLabel(m.provider)}}</small>
        <small v-if="m.notice" class="model-notice">{{m.notice}}</small>
        <details v-if="uniqueSources(m.sources).length" class="chat-sources"><summary>查看回答依据（{{uniqueSources(m.sources).length}}）</summary><a v-for="s in uniqueSources(m.sources)" :key="`${s.id}|${s.source_url}`" :href="s.source_url" target="_blank" rel="noopener noreferrer"><Icon name="BookOpen" :size="12"/>{{s.title}}</a></details>
        <details v-if="uniqueResources(m.resources).length" class="chat-sources"><summary>查看平台学习资源（{{uniqueResources(m.resources).length}}）</summary><a v-for="r in uniqueResources(m.resources)" :key="r.id" :href="r.url" :target="r.url.startsWith('http')?'_blank':undefined" rel="noopener noreferrer"><Icon name="BookOpen" :size="12"/>{{r.title}}</a></details>
        <div v-if="m.role==='assistant'&&i===messages.length-1&&m.suggestions?.length" class="tutor-followups"><button v-for="suggestion in m.suggestions" :key="suggestion" type="button" :disabled="busy" @click="send(suggestion)">{{suggestion}}</button></div>
      </div>
      <div v-if="error" class="error-message" role="alert">{{error}}</div>
    </div>
    <div class="chat-disclaimer">AI 负责讲解，题目事实与判定以系统记录为准。</div>
  </section>
  <form v-if="!floating||open" class="tutor-composer" @submit.prevent="send()"><div class="tutor-input-row"><input v-model="input" :disabled="disabled" aria-label="向小基提问" :placeholder="runId?'这道题，有哪里不明白？':stage&&open?'输入其他问题…':'有什么需要帮助的？'" maxlength="1500" @focus="setOpen(true)"><button :disabled="busy||disabled||!input.trim()" aria-label="发送问题"><Icon :name="busy?'LoaderCircle':'ArrowRight'" :class="{spin:busy}"/></button></div><div v-if="!messages.length&&(!stage||!open)" class="question-chips"><button type="button" @click="send(runId?'给我一点提示':'什么是 IoU？',!!runId)">{{runId?'给我一点提示':'什么是 IoU？'}}</button><button type="button" @click="send(runId?'这道题应该注意哪里？':'我下一步应该学什么？')">{{runId?'应该注意哪里？':'下一步学什么？'}}</button><button v-if="!floating" type="button" @click="send('工业缺陷标注需要注意什么？')">工业缺陷标注</button></div></form>
</div>
</template>

<style scoped>
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.chat-sources{margin-top:9px}.chat-sources summary{cursor:pointer;color:#72578e;font-size:13px}.chat-sources a{margin-top:6px}
.tutor-followups{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.tutor-followups button{padding:5px 9px;border:1px solid #dfd5eb;border-radius:14px;background:#fff;color:#694b85;font-size:12px;text-align:left}.tutor-followups button:disabled{opacity:.55}
</style>
