import router from './router'
import { api,post } from './api'
import { state } from './store'

export function registerLearningTools(){
 const context=(document as any).modelContext
 if(!context?.registerTool)return
 const lifecycle=new AbortController()
 const register=(tool:any)=>Promise.resolve(context.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{})
 const empty={type:'object',properties:{},additionalProperties:false}
 const requireUser=()=>{if(!state.user)throw new Error('请先登录');if(!state.user.onboarding)throw new Error('请先完成新手引导')}
 const checkEmpty=(input:any)=>{if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).length)throw new Error('不接受参数')}
 void register({name:'get_learning_progress',title:'读取学习进度',description:'读取当前已登录学习者的实际技能分（正确率乘10）、完成关数与推荐，不改变记录。',inputSchema:empty,annotations:{readOnlyHint:true,untrustedContentHint:true},async execute(input:any){checkEmpty(input);requireUser();const d=await api('/dashboard');return {goal:d.user.goal,recommendation:d.recommendation,completed_levels:d.completed_levels,abilities:d.abilities.map((a:any)=>({id:a.id,name:a.name,skill_score:a.skill_score,answer_count:a.answer_count,correct_count:a.correct_count,completed:a.completed}))}}})
 void register({name:'open_skill_map',title:'打开技能地图',description:'导航到智基A1至A10技能地图，不开始或提交训练。',inputSchema:empty,annotations:{readOnlyHint:false},async execute(input:any){checkEmpty(input);requireUser();await router.push('/skills');return {path:router.currentRoute.value.path}}})
 void register({name:'start_training',title:'开始一个训练关卡',description:'创建或继续任意课程、岗位任务或竞赛，并打开训练页面。竞赛会立即开始倒计时。不会自动作答或提交。',inputSchema:{type:'object',properties:{level_id:{type:'string',pattern:'^A(?:[1-9]|10)-(?:L[1-5]|JOB|RACE)$'}},required:['level_id'],additionalProperties:false},annotations:{readOnlyHint:false},async execute(input:any){requireUser();if(!input||typeof input.level_id!=='string'||!/^A(?:[1-9]|10)-(?:L[1-5]|JOB|RACE)$/.test(input.level_id)||Object.keys(input).some(k=>k!=='level_id'))throw new Error('无效关卡编号');const r=await post('/runs/start',{level_id:input.level_id});await router.push('/train/'+r.id);return {run_id:r.id,mode:r.mode,status:r.status,deadline:r.deadline,path:router.currentRoute.value.path}}})
 if(import.meta.hot)import.meta.hot.dispose(()=>lifecycle.abort())
 window.addEventListener('pagehide',()=>lifecycle.abort(),{once:true})
}
