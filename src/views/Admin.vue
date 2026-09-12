<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, post } from '../api'
import { notify, state } from '../store'
import Icon from '../components/Icon.vue'

const loading=ref(true),error=ref(''),tab=ref<'accounts'|'knowledge'>('accounts')
const users=ref<any[]>([]),knowledge=ref<any>({built_in:[],custom:[],scope_options:[]})
const accountOpen=ref(false),knowledgeOpen=ref(false),saving=ref(false)
const account=ref({username:'',name:'',password:'',role:'student'})
const base=ref({name:'',purpose:'',scope:'GENERAL',content:''})
const accountCounts=computed(()=>({students:users.value.filter(user=>user.role==='student').length,admins:users.value.filter(user=>user.role==='admin').length}))

async function load(){
  loading.value=true;error.value=''
  try{[users.value,knowledge.value]=await Promise.all([api('/admin/users'),api('/admin/knowledge-bases')])}
  catch(e){error.value=(e as Error).message}
  finally{loading.value=false}
}
async function createAccount(){
  saving.value=true
  try{const created=await post('/admin/users',account.value);users.value.push(created);account.value={username:'',name:'',password:'',role:'student'};accountOpen.value=false;notify('账号已创建。')}
  catch(e){notify((e as Error).message,'error')}
  finally{saving.value=false}
}
async function removeAccount(user:any){
  if(!confirm(`确认删除账号“${user.username}”及其学习记录吗？此操作不可恢复。`))return
  try{await api(`/admin/users/${encodeURIComponent(user.username)}`,{method:'DELETE'});users.value=users.value.filter(item=>item.username!==user.username);notify('账号已删除。')}
  catch(e){notify((e as Error).message,'error')}
}
async function createKnowledge(){
  saving.value=true
  try{const created=await post('/admin/knowledge-bases',base.value);knowledge.value.custom.unshift(created);base.value={name:'',purpose:'',scope:'GENERAL',content:''};knowledgeOpen.value=false;notify(`知识库已添加，并拆分为 ${created.knowledge_count} 条检索知识。`)}
  catch(e){notify((e as Error).message,'error')}
  finally{saving.value=false}
}
onMounted(load)
</script>

<template><div class="content-width admin-page">
  <header class="admin-heading"><div><span class="eyebrow">智基 · 管理控制台</span><h1>后台管理</h1><p>管理平台账号，并查看 AI 导师实际检索的知识范围。</p></div><span class="admin-login"><Icon name="ShieldCheck" :size="18"/>当前管理者：{{state.user?.username}}</span></header>
  <div v-if="error" class="error-message" role="alert">{{error}} <button class="text-button" @click="load">重新加载</button></div>
  <div v-else-if="loading" class="loading-state"><Icon name="LoaderCircle" class="spin"/>正在读取管理数据…</div>
  <template v-else>
    <nav class="admin-tabs" aria-label="后台管理分类"><button :class="{active:tab==='accounts'}" @click="tab='accounts'"><Icon name="Users"/>账号管理</button><button :class="{active:tab==='knowledge'}" @click="tab='knowledge'"><Icon name="FolderOpen"/>知识库管理</button></nav>
    <section v-if="tab==='accounts'" class="admin-section">
      <div class="admin-section-title"><div><h2>平台账号</h2><p>学习者首次登录进入新手教学；管理者登录后直接进入本管理端。</p></div><button class="btn dark small" @click="accountOpen=true"><Icon name="Plus" :size="17"/>添加账号</button></div>
      <div class="admin-stats"><article><Icon name="Users"/><span>用户账号</span><b>{{accountCounts.students}}</b></article><article><Icon name="ShieldCheck"/><span>管理者账号</span><b>{{accountCounts.admins}}</b></article></div>
      <div class="admin-table-wrap"><table class="admin-table"><thead><tr><th>账号</th><th>显示名称</th><th>账号类型</th><th>创建时间</th><th>操作</th></tr></thead><tbody><tr v-for="user in users" :key="user.username"><td><b>{{user.username}}</b></td><td>{{user.name}}</td><td><span class="role-pill" :class="user.role">{{user.role==='admin'?'管理者':'用户'}}</span></td><td>{{new Date(user.created_at).toLocaleDateString('zh-CN')}}</td><td><button class="delete-account" :disabled="user.username===state.user?.username" :title="user.username===state.user?.username?'不能删除当前账号':'删除账号'" @click="removeAccount(user)"><Icon name="Trash2" :size="17"/>删除</button></td></tr></tbody></table></div>
    </section>
    <section v-else class="admin-section">
      <div class="admin-section-title"><div><h2>目前使用的知识库</h2><p>原知识库已按通用知识和 A1–A10 能力拆分。下方每张卡片都说明它负责回答什么。</p></div><button class="btn dark small" @click="knowledgeOpen=true"><Icon name="Plus" :size="17"/>添加知识库</button></div>
      <div class="knowledge-notice"><Icon name="CircleHelp" :size="20"/><p><b>知识库有什么用？</b> AI 导师会先按当前问题和能力范围检索这里的知识，再组织回答。管理者新增的内容会保存到 PostgreSQL/pgvector，并立即加入所选范围的检索；请只录入已经核对的资料。</p></div>
      <h3 class="admin-subtitle">原知识库拆分</h3><div class="knowledge-grid"><article v-for="item in knowledge.built_in" :key="item.id"><div class="knowledge-card-top"><span>{{item.scope}}</span><small>{{item.knowledge_count}} 条知识</small></div><h3>{{item.name}}</h3><p>{{item.purpose}}</p><footer><Icon name="Database" :size="15"/>{{item.source}} · 正在使用</footer></article></div>
      <template v-if="knowledge.custom.length"><h3 class="admin-subtitle">管理者新增</h3><div class="knowledge-grid custom"><article v-for="item in knowledge.custom" :key="item.id"><div class="knowledge-card-top"><span>{{item.scope_name||item.scope}}</span><small>{{item.knowledge_count}} 条知识</small></div><h3>{{item.name}}</h3><p>{{item.purpose}}</p><footer><Icon name="Check" :size="15"/>已加入导师检索</footer></article></div></template>
    </section>
  </template>

  <div v-if="accountOpen" class="modal-backdrop" @click.self="accountOpen=false"><form class="modal-card admin-form" @submit.prevent="createAccount"><div class="modal-title"><h2>添加平台账号</h2><button type="button" class="icon-button" aria-label="关闭" @click="accountOpen=false"><Icon name="X"/></button></div><label for="admin-username">登录账号</label><input id="admin-username" v-model.trim="account.username" required minlength="3" maxlength="40" pattern="[A-Za-z0-9_]+" placeholder="字母、数字或下划线"><label for="admin-name">显示名称</label><input id="admin-name" v-model.trim="account.name" required maxlength="40"><label for="admin-password">初始密码</label><input id="admin-password" v-model="account.password" type="password" required minlength="6" maxlength="128" autocomplete="new-password"><label for="admin-role">账号类型</label><select id="admin-role" v-model="account.role"><option value="student">用户账号</option><option value="admin">管理者账号</option></select><div class="modal-actions"><button type="button" class="btn outline" @click="accountOpen=false">取消</button><button class="btn green" :disabled="saving">{{saving?'创建中…':'确认创建'}}</button></div></form></div>
  <div v-if="knowledgeOpen" class="modal-backdrop" @click.self="knowledgeOpen=false"><form class="modal-card admin-form knowledge-form" @submit.prevent="createKnowledge"><div class="modal-title"><h2>添加知识库</h2><button type="button" class="icon-button" aria-label="关闭" @click="knowledgeOpen=false"><Icon name="X"/></button></div><p class="settings-note">内容会按段落拆分、生成向量，并用于所选范围内的 AI 导师检索。</p><label for="base-name">知识库名称</label><input id="base-name" v-model.trim="base.name" required minlength="2" maxlength="80" placeholder="例如：校内视觉标注项目规范"><label for="base-purpose">用途说明</label><textarea id="base-purpose" v-model.trim="base.purpose" required minlength="5" maxlength="300" rows="3" placeholder="告诉其他管理者：这个知识库解决什么问题、在什么场景使用"></textarea><label for="base-scope">适用范围</label><select id="base-scope" v-model="base.scope"><option v-for="scope in knowledge.scope_options" :key="scope.value" :value="scope.value">{{scope.label}}</option></select><small class="scope-help">{{knowledge.scope_options.find((item:any)=>item.value===base.scope)?.purpose}}</small><label for="base-content">知识内容</label><textarea id="base-content" v-model.trim="base.content" required minlength="20" maxlength="20000" rows="8" placeholder="输入已经核对的知识、规范或项目说明"></textarea><div class="modal-actions"><button type="button" class="btn outline" @click="knowledgeOpen=false">取消</button><button class="btn green" :disabled="saving">{{saving?'正在处理…':'保存并加入检索'}}</button></div></form></div>
</div></template>
