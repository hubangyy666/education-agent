<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import JobArtwork from '../components/JobArtwork.vue'
import JobTile from '../components/JobTile.vue'
const data=ref<any>(), error=ref(''), search=ref('')
const roles=computed(()=> (data.value?.roles||[]).filter((r:any)=>[r.title,r.summary,r.industry,...r.tasks.map((t:any)=>t.title)].join(' ').includes(search.value.trim())))
async function load(){error.value='';try{data.value=await api('/jobs')}catch(e){error.value=(e as Error).message}}
onMounted(load)
</script>
<template>
  <div class="content-width jp-page">
    <header class="jp-heading"><div><h1>岗位学习路径</h1><p>认识真实岗位，跟着典型任务学会工作。</p></div><label class="jp-search"><Icon name="Search" :size="19"/><input v-model="search" type="search" placeholder="想了解什么岗位？" aria-label="搜索岗位或任务"/></label></header>
    <h2 class="jp-list-title">探索你的岗位方向 <span v-if="data">4 个岗位 · 8 项典型任务</span></h2>
    <div v-if="error" class="jp-state" role="alert"><p>{{error}}</p><button class="btn outline" @click="load">重新加载</button></div>
    <div v-else-if="!data" class="jp-state" role="status">正在加载岗位…</div>
    <div v-else-if="!roles.length" class="jp-state"><Icon name="Search" :size="32"/><h3>没有找到对应的岗位或任务</h3><button class="btn outline" @click="search=''">查看全部岗位</button></div>
    <section v-for="role in roles" :key="role.id" class="jp-path" :class="'jp-'+role.color" :aria-label="role.title">
      <header class="jp-path-heading"><RouterLink :to="'/jobs/'+role.id" class="jp-role-art" :aria-label="'了解'+role.title"><JobArtwork :kind="role.id"/></RouterLink><div><span class="jp-eyebrow">{{role.industry}}</span><RouterLink :to="'/jobs/'+role.id"><h2>{{role.title}}</h2></RouterLink><p>{{role.summary}}</p></div><RouterLink :to="'/jobs/'+role.id" class="jp-round-link" :aria-label="'查看'+role.title+'简介'"><Icon name="ArrowRight" :size="21"/></RouterLink></header>
      <div class="jp-strip">
        <JobTile :to="'/jobs/'+role.id" label="认识这个岗位" hint="岗位简介" :kind="role.id" caption="工作情境与日常职责"/>
        <JobTile v-for="(task,i) in role.tasks" :key="task.id" :to="`/jobs/${role.id}/tasks/${task.id}`" :label="task.title" :hint="'典型任务 '+String(Number(i)+1).padStart(2,'0')" :icon="task.tile_icon" :caption="`${task.steps.length} 个步骤 · 约 ${task.duration_minutes} 分钟`" :done="task.status==='completed'"/>
        <JobTile :to="{path:'/jobs/'+role.id,hash:'#role-skills'}" label="相关知识与技能" hint="关联训练" icon="Layers3" caption="找到对应技能，动手练习"/>
      </div>
    </section>
    <p class="jp-footer-note">岗位内容结合公开行业资料与专业教学标准编写，资料来源可在岗位和任务详情中查看。</p>
  </div>
</template>
