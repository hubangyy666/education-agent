<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import Icon from './Icon.vue'
import { speak } from '../store'
const props=withDefaults(defineProps<{floating?:boolean;runId?:string;questionId?:string;disabled?:boolean}>(),{floating:false,disabled:false})
const open=ref(false),input=ref(''),busy=ref(false),error=ref('');const messages=ref<any[]>([]);const list=ref<HTMLElement>();let controller:AbortController|undefined
watch(()=>props.questionId,()=>{controller?.abort();busy.value=false;messages.value=[];error.value=''})
onBeforeUnmount(()=>controller?.abort())
async function scroll(){await nextTick();list.value?.scrollTo({top:list.value.scrollHeight,behavior:'smooth'})}
async function send(text?:string){
  const message=(text||input.value).trim();if(!message||busy.value||props.disabled)return
  open.value=true;input.value='';error.value='';messages.value.push({role:'user',text:message});busy.value=true
  const reply:any={role:'assistant',text:'',sources:[],provider:''};messages.value.push(reply);controller=new AbortController();const activeController=controller;await scroll()
  try{
    const response=await fetch('/api/ai/chat',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({message,mode:props.runId?'QUESTION_TUTOR':'GENERAL_TUTOR',run_id:props.runId,question_id:props.questionId,history:messages.value.slice(0,-2).map(m=>({role:m.role,text:m.text}))})})
    if(!response.ok){const e=await response.json();throw new Error(e.detail||'暂时无法回复，请再试一次。')}
    const reader=response.body!.getReader();const decoder=new TextDecoder();let buffer=''
    while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const frames=buffer.split('\n\n');buffer=frames.pop()||'';for(const frame of frames){const event=frame.match(/event: (\w+)/)?.[1];const raw=frame.match(/data: (.+)/)?.[1];if(!raw)continue;const data=JSON.parse(raw);if(event==='token')reply.text+=data.text;if(event==='done')Object.assign(reply,data)}messages.value=[...messages.value];await scroll()}
    if(controller===activeController)speak(reply.text)
  }catch(e){if(controller===activeController&&(e as Error).name!=='AbortError')error.value=(e as Error).message}finally{if(controller===activeController)busy.value=false}
}
defineExpose({send})
</script>
<template>
<div :class="['tutor',{'tutor-floating':floating,'is-open':open}]">
  <button v-if="floating" class="mentor-launch" :disabled="disabled" @click="open=!open" aria-label="向小基提问"><span v-if="!open">需要一点提示？</span><img src="/mentor.png" alt="小基，AI 学习导师"/><span class="mentor-launch-close" v-if="open"><Icon name="X" :size="16"/></span></button>
  <section v-if="open" class="tutor-chat" aria-label="AI 学习导师"><header><div class="tutor-avatar"><img src="/mentor.png" alt=""/></div><div><b>小基 · 你的学习导师</b><small>{{runId?'一起观察，自己找到答案':'数据标注岗位知识答疑'}}</small></div><button class="icon-button" aria-label="收起对话" @click="open=false"><Icon name="X" :size="18"/></button></header><div class="chat-messages" ref="list" aria-live="polite"><div v-if="!messages.length" class="chat-welcome"><p>你好！我会陪你一起学会数据标注。</p><p>{{runId?'告诉我你卡在哪里，我们一步一步来看。':'可以问我标注规范，也可以一起规划接下来的学习。'}}</p></div><div v-for="(m,i) in messages" :key="i" class="chat-message" :class="m.role"><div class="message-text">{{m.text || '正在查找相关资料…'}}</div><small v-if="m.role==='assistant' && m.text" class="ai-label">{{m.provider==='deepseek'?'AI 生成内容':'课程与知识库提示'}}</small><small v-if="m.notice" class="model-notice">{{m.notice}}</small><div v-if="m.sources?.length" class="chat-sources"><a v-for="s in m.sources" :key="s.id" :href="s.source_url" target="_blank" rel="noopener noreferrer"><Icon name="BookOpen" :size="12"/>{{s.title}}</a></div></div><div v-if="error" class="error-message" role="alert">{{error}}</div></div><div class="chat-disclaimer">回答用于学习参考，项目规则以正式规范为准。</div></section>
  <form v-if="!floating||open" class="tutor-composer" @submit.prevent="send()"><div class="tutor-input-row"><input v-model="input" :disabled="disabled" aria-label="向小基提问" :placeholder="runId?'这道题，有哪里不明白？':'想学点什么，或者哪里需要帮助？'" maxlength="1500" @focus="open=true"><button :disabled="busy||disabled||!input.trim()" aria-label="发送问题"><Icon :name="busy?'LoaderCircle':'ArrowRight'" :class="{spin:busy}"/></button></div><div v-if="!messages.length" class="question-chips"><button type="button" @click="send(runId?'给我一点提示':'什么是 IoU？')">{{runId?'给我一点提示':'什么是 IoU？'}}</button><button type="button" @click="send(runId?'这道题应该注意哪里？':'我下一步应该学什么？')">{{runId?'应该注意哪里？':'下一步学什么？'}}</button><button v-if="!floating" type="button" @click="send('工业缺陷标注需要注意什么？')">工业缺陷标注</button></div></form>
</div>
</template>
