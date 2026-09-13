// Real Vue setup logic with controlled API responses; browser gestures are verified separately.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

const standard=[{box:[.2,.2,.3,.4],label:'行人'}]
const clone=value=>JSON.parse(JSON.stringify(value))
const question={id:'q1',type:'box',labels:['行人','狗']}
function run(){return {id:'run1',mode:'course',ability_id:'A4',status:'active',server_time:new Date().toISOString(),questions:[question],answers:{q1:{boxes:standard}},question_feedback:{q1:{correct:false,wrong_attempts:3,can_view_standard:true}}}}
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
async function page(name,options={}){
  const source=await readFile(new URL(`../src/views/${name}.vue`,import.meta.url),'utf8')
  const script=compileScript(parse(source).descriptor,{id:'annotation-flow'}).content
  const js=ts.transpileModule(script,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const exports={},calls=[],unmount=[],route=vue.reactive({params:{id:'run1'},query:{}})
  const imports={vue:{...vue,onMounted(){},onBeforeUnmount(fn){unmount.push(fn)}},'vue-router':{useRoute:()=>route,useRouter:()=>({push(){},replace(){}})},'../api':{
    async api(url){calls.push(url);if(url.endsWith('/standard-answer'))return options.gate?options.gate.promise:{standard_answer:clone(standard)};if(url.startsWith('/runs/'))return run();if(url.startsWith('/mistakes/'))return {id:'m1',question,latest_review_answer:{boxes:standard},feedback:{correct:false},wrong_attempts:3,can_view_standard:true};return {}},
    async post(url){calls.push(url);return {result:{correct:false},wrong_attempts:3,can_view_standard:true}}
  },'../store':{state:vue.reactive({user:{voice:true}}),prepareEncouragement(){},encourage(){},encouragePrecision(){},toggleVoice(){},notify(){},refreshDashboard(){}},'../audio':{stopEncouragementAudio(){}},'../scores':{formatSkillScore:String}}
  vm.runInNewContext(js,{exports,require:name=>imports[name]||{},setInterval,clearInterval})
  const state=exports.default.setup({},{expose(){}})
  return {state,calls,route,unmount(){unmount.forEach(fn=>fn())}}
}

let passed=0
async function check(name,fn){await fn();passed++;console.log('PASS '+name)}
await check('course restores failed answer eligibility without requesting or showing standard',async()=>{
  const p=await page('Training');await p.state.load()
  assert.equal(p.state.feedback.value.wrong_attempts,3);assert.equal(p.state.canViewStandard.value,true)
  assert.equal(p.state.showStandard.value,false);assert.equal(p.calls.some(x=>x.endsWith('/standard-answer')),false);p.unmount()
})
for(const name of ['Training','Mistakes']){
  await check(`${name}: first and second errors cannot request standard`,async()=>{
    const p=await page(name);if(name==='Training')p.state.run.value=run();else p.state.item.value={id:'m1',question}
    for(const wrong_attempts of [1,2]){p.state.feedback.value={correct:false,wrong_attempts,can_view_standard:false};await p.state.viewStandard()}
    assert.equal(p.calls.length,0);assert.equal(p.state.showStandard.value,false);p.unmount()
  })
  await check(`${name}: explicit viewing blocks submit; retry clears learner and reference geometry`,async()=>{
    const p=await page(name);if(name==='Training')p.state.run.value=run();else p.state.item.value={id:'m1',question}
    p.state.answer.value={boxes:clone(standard)};p.state.feedback.value={correct:true,can_view_standard:true}
    await p.state.viewStandard();assert.equal(p.state.showStandard.value,true);assert.deepEqual(clone(p.state.standardAnswer.value),standard)
    await p.state.submit();assert.equal(p.calls.length,1)
    p.state.retry();assert.equal(p.state.showStandard.value,false);assert.equal(p.state.standardAnswer.value,undefined);assert.equal(p.state.answer.value.boxes.length,0)
    assert.ok(!p.state.feedback.value);assert.ok(!p.state.validAnswer.value);p.unmount()
  })
  await check(`${name}: response arriving after exit cannot show an old reference`,async()=>{
    const gate=deferred(),p=await page(name,{gate});if(name==='Training')p.state.run.value=run();else p.state.item.value={id:'m1',question}
    p.state.feedback.value={correct:false,can_view_standard:true,wrong_attempts:3};const request=p.state.viewStandard()
    assert.equal(p.state.busy.value,true);p.unmount();gate.resolve({standard_answer:standard});await request
    assert.equal(p.state.showStandard.value,false);assert.equal(p.state.standardAnswer.value,undefined)
  })
}
await check('mistake detail restores independent review evidence without autoloading standard',async()=>{
  const p=await page('Mistakes');await p.state.load();assert.equal(p.state.feedback.value.wrong_attempts,3);assert.equal(p.state.canViewStandard.value,true);assert.equal(p.state.showStandard.value,false);p.unmount()
})
await check('onboarding retry returns to independent drawing and clears all reference state',async()=>{
  const p=await page('Onboarding');p.state.run.value={questions:[question,question]};p.state.step.value=6;p.state.answer.value={boxes:standard};p.state.feedback.value={correct:true};p.state.showStandard.value=true;p.state.standardAnswer.value=standard
  p.state.retryIndependent();assert.equal(p.state.step.value,5);assert.equal(p.state.answer.value.boxes.length,0);assert.equal(p.state.showStandard.value,false);assert.equal(p.state.standardAnswer.value,undefined);p.unmount()
})
await check('onboarding reload restores independent answer and three errors without revealing standard',async()=>{
  const p=await page('Onboarding'),saved=run();saved.questions=[{id:'guide',type:'box'},question]
  p.state.restoreRun(saved);assert.equal(p.state.step.value,6);assert.equal(p.state.feedback.value.wrong_attempts,3)
  assert.deepEqual(clone(p.state.answer.value),{boxes:standard});assert.equal(p.state.showStandard.value,false);assert.equal(p.calls.length,0);p.unmount()
})
console.log(`${passed} annotation flow checks passed`)
