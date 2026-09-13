<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { state, logout } from './store'
import Icon from './components/Icon.vue'
const route = useRoute(); const router = useRouter()
const menuOpen=ref(false)
const immersive = computed(() => ['/login','/onboarding','/train'].some(p => route.path.startsWith(p)))
async function signOut() { await logout(); router.push('/login') }
</script>
<template>
  <div class="app-shell" :class="{immersive}">
    <header v-if="!immersive" class="site-header"><div class="header-inner">
      <RouterLink to="/" class="brand"><img src="/favicon.svg" alt=""><span>智基<span class="brand-dot">.</span></span></RouterLink>
      <nav v-if="state.user?.role!=='admin'" aria-label="主要导航">
        <RouterLink to="/" exact-active-class="active"><Icon name="Home"/><span>首页</span></RouterLink>
        <RouterLink to="/skills" :class="{active:route.path.startsWith('/skills')}"><Icon name="Network"/><span>技能</span></RouterLink>
        <RouterLink to="/jobs" :class="{active:route.path.startsWith('/jobs')}"><Icon name="BriefcaseBusiness"/><span>岗位</span></RouterLink>
        <RouterLink to="/profile" :class="{active:route.path.startsWith('/profile')}"><Icon name="UserRound"/><span>我的</span></RouterLink>
      </nav>
      <nav v-else aria-label="管理端导航"><RouterLink to="/admin" active-class="active"><Icon name="ShieldCheck"/><span>后台管理</span></RouterLink></nav>
      <div class="header-actions"><RouterLink v-if="state.user?.role!=='admin'" to="/profile" class="energy" aria-label="累计完成题数"><b>{{state.dashboard?.total_count || 0}}</b><Icon name="Zap"/></RouterLink><span v-else class="admin-identity"><Icon name="ShieldCheck" :size="17"/>{{state.user?.name}}</span><button class="icon-button" aria-label="打开菜单" @click="menuOpen=!menuOpen"><Icon name="Menu"/></button><div v-if="menuOpen" class="header-menu"><RouterLink v-if="state.user?.role!=='admin'" to="/profile" @click="menuOpen=false"><Icon name="Settings2"/>学习设置</RouterLink><button @click="menuOpen=false;signOut()"><Icon name="LogOut"/>退出登录</button></div></div>
    </div></header>
    <main class="main-surface"><RouterView/></main>
    <Transition name="toast"><div v-if="state.toast" class="toast-message" :class="state.toastKind" role="status"><Icon :name="state.toastKind==='error'?'CircleHelp':'Check'"/>{{state.toast}}</div></Transition>
  </div>
</template>
