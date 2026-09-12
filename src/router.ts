import { createRouter, createWebHistory } from 'vue-router'
import { loadUser, state } from './store'
import Login from './views/Login.vue'
import Home from './views/Home.vue'
const router = createRouter({ history: createWebHistory(), routes: [
  {path:'/login',component:Login}, {path:'/',component:Home},
  {path:'/onboarding',component:()=>import('./views/Onboarding.vue')},
  {path:'/skills',component:()=>import('./views/Skills.vue')},
  {path:'/skills/:id',component:()=>import('./views/Module.vue')},
  {path:'/train/:id',component:()=>import('./views/Training.vue')},
  {path:'/profile',component:()=>import('./views/Profile.vue')},
  {path:'/tasks',component:()=>import('./views/Tasks.vue')},
  {path:'/jobs',component:()=>import('./views/Jobs.vue')},
  {path:'/jobs/:roleId',component:()=>import('./views/JobDetail.vue')},
  {path:'/jobs/:roleId/tasks/:taskId',component:()=>import('./views/JobLearning.vue')},
  {path:'/jobs/:roleId/learn/:learningId',component:()=>import('./views/JobLearning.vue')},
  {path:'/:pathMatch(.*)*',redirect:'/'}
], scrollBehavior: () => ({top:0}) })
router.beforeEach(async to => { if (!state.ready) await loadUser(); if (!state.user && to.path !== '/login') return '/login'; if (state.user && !state.user.onboarding && !['/onboarding','/login'].includes(to.path)) return '/onboarding'; if (state.user && to.path === '/login') return state.user.onboarding?'/':'/onboarding' })
export default router
