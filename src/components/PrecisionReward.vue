<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import lottie from 'lottie-web/build/player/lottie_light'
import Icon from './Icon.vue'

const emit=defineEmits<{done:[]}>()
const container=ref<HTMLElement>()
const staticCheck=ref(false)
let timer:ReturnType<typeof setTimeout>|undefined
let animation:ReturnType<typeof lottie.loadAnimation>|undefined
let finished=false

function finish(){
  if(finished)return
  finished=true
  clearTimeout(timer)
  emit('done')
}

onMounted(()=>{
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches
  staticCheck.value=reduced
  if(!reduced&&container.value){
    try{
      animation=lottie.loadAnimation({container:container.value,renderer:'svg',loop:false,autoplay:true,path:'/animations/success-checkmark.json'})
      animation.addEventListener('complete',finish)
      animation.addEventListener('data_failed',()=>{staticCheck.value=true})
    }catch{staticCheck.value=true}
  }
  timer=setTimeout(finish,reduced?850:1700)
})
onBeforeUnmount(()=>{finished=true;clearTimeout(timer);animation?.destroy()})
</script>

<template>
  <div class="precision-reward" role="status" aria-live="polite" aria-label="精准标注，交并比超过百分之九十">
    <div class="precision-symbol" aria-hidden="true">
      <div v-show="!staticCheck" ref="container" class="precision-lottie"></div>
      <Icon v-if="staticCheck" name="Check" :size="110"/>
    </div>
  </div>
</template>

<style scoped>
.precision-reward{position:fixed;inset:0;z-index:140;pointer-events:none;display:grid;place-items:center;background:transparent}
.precision-symbol{display:grid;place-items:center;width:168px;height:168px;border-radius:50%;background:#fff;color:#38a169}
.precision-lottie{width:100%;height:100%;background:transparent}
.precision-lottie :deep(svg){display:block;background:transparent}
@media(max-width:760px){.precision-symbol{width:144px;height:144px}}
</style>
