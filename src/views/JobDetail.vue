<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import JobArtwork from '../components/JobArtwork.vue'
import JobTile from '../components/JobTile.vue'
import JobPhoto from '../components/JobPhoto.vue'
const route=useRoute(),data=ref<any>(),error=ref('')
const role=computed(()=>data.value?.role)
const skills=computed(()=>{const seen=new Set<string>();return (role.value?.tasks.flatMap((t:any)=>t.skills)||[]).filter((s:any)=>{if(seen.has(s.skill_id))return false;seen.add(s.skill_id);return true})})
async function focus(){await nextTick();if(route.hash)document.getElementById(route.hash.slice(1))?.scrollIntoView({block:'start'})}
async function load(){data.value=undefined;error.value='';try{data.value=await api('/jobs/'+route.params.roleId);await focus()}catch(e){error.value=(e as Error).message}}
onMounted(load);watch(()=>route.params.roleId,load);watch(()=>route.hash,focus)
</script>
<template>
  <div class="content-width jp-page" :class="'jp-'+(role?.color||'blue')">
    <RouterLink to="/jobs" class="jp-back"><Icon name="ArrowLeft" :size="17"/>全部岗位</RouterLink>
    <div v-if="error" class="jp-state" role="alert"><p>{{error}}</p><button class="btn outline" @click="load">重新加载</button></div><div v-else-if="!role" class="jp-state" role="status">正在加载岗位…</div>
    <template v-else>
      <header class="jp-role-heading"><JobArtwork :kind="role.id"/><div><span class="jp-eyebrow">{{role.industry}}</span><h1>{{role.title}}</h1><p>{{role.summary}}</p></div></header>
      <section class="jp-path"><div class="jp-section-heading"><h2>典型工作任务</h2><span>选择一项任务，直接开始阅读</span></div><div class="jp-strip jp-task-strip"><JobTile v-for="(task,i) in role.tasks" :key="task.id" :to="`/jobs/${role.id}/tasks/${task.id}`" :label="task.title" :hint="'任务 '+String(Number(i)+1).padStart(2,'0')" :icon="task.tile_icon" :caption="`详细讲解 · ${task.duration_minutes} 分钟`" :done="task.status==='completed'"/><div class="jp-strip-note"><Icon name="BookOpen" :size="26"/><h3>先理解工作，再动手实践</h3><p>每个任务都包含工作场景、真实样图、操作步骤与检查规范，按自己的节奏逐步学习。</p></div></div></section>
      <section class="jp-overview"><div><span class="jp-eyebrow">认识岗位</span><h2>这份工作，具体做什么？</h2><p>{{role.scenario}}</p><h3>日常职责</h3><ul class="jp-list"><li v-for="item in role.responsibilities" :key="item">{{item}}</li></ul></div><JobPhoto v-if="role.image?.url" :photo="role.image" :industrial="role.id==='industrial'"/></section>
      <div class="jp-info-grid"><section class="jp-info jp-blue"><span class="jp-info-symbol"><Icon name="FileCheck2" :size="25"/></span><h3>需要交付什么</h3><ul class="jp-list"><li v-for="item in role.deliverables" :key="item">{{item}}</li></ul></section><section class="jp-info jp-purple"><span class="jp-info-symbol"><Icon name="Users" :size="25"/></span><h3>和谁一起工作</h3><ul class="jp-list"><li v-for="item in role.collaboration" :key="item">{{item}}</li></ul></section><section class="jp-info jp-orange"><span class="jp-info-symbol"><Icon name="GraduationCap" :size="25"/></span><h3>对应专业方向</h3><div v-for="major in role.majors" :key="major.code"><p>{{major.name}}<br/><small>专业代码 {{major.code}}</small></p></div><p>围绕数据采集、标注、审核与交付，理解岗位中的具体工作要求。</p></section></div>
      <section id="role-skills" class="jp-knowledge-section"><div class="jp-section-heading"><h2>相关知识与技能</h2><span>点击进入对应技能训练</span></div><div class="jp-skill-grid"><RouterLink v-for="skill in skills" :key="skill.skill_id" :to="{path:'/skills/'+skill.ability_id,query:{skill:skill.skill_id,roleId:role.id}}"><span class="jp-skill-symbol"><Icon name="Layers3" :size="22"/></span><div><small>{{skill.skill_id}}</small><h3>{{skill.title||skill.reason}}</h3></div><Icon name="ChevronRight" :size="18"/></RouterLink></div></section>
      <details class="jp-sources"><summary>岗位资料与参考来源 <span>{{data.sources.length}} 项</span></summary><a v-for="source in data.sources" :key="source.id" :href="source.url" target="_blank" rel="noopener noreferrer"><span><b>{{source.title}}</b><small>{{source.publisher}} · {{source.summary}}</small></span><Icon name="ArrowUpRight" :size="16"/></a></details>
    </template>
  </div>
</template>
