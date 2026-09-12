<script setup lang="ts">
import { ref, watch } from 'vue'
import Icon from './Icon.vue'
const props=defineProps<{photo:any,industrial?:boolean}>()
const failed=ref(false)
watch(()=>props.photo.url,()=>failed.value=false)
</script>
<template><figure class="jp-photo" :class="{'jp-industrial-photo':industrial}"><a v-if="!failed" :href="photo.url" target="_blank" rel="noopener noreferrer" class="jp-photo-frame" aria-label="打开原始工作图片"><img :src="photo.url" :alt="photo.caption" @error="failed=true"/><span><Icon name="Maximize2" :size="15"/>查看原图</span></a><div v-else class="jp-photo-error" role="alert">图片暂时无法加载。<button @click="failed=false">重试</button></div><figcaption><b>{{photo.type||'真实工作样本'}}</b><p>{{photo.caption}}</p><small>{{photo.credit}} · {{photo.license}}</small><a :href="photo.source_url" target="_blank" rel="noopener noreferrer">原始来源<Icon name="ArrowUpRight" :size="13"/></a></figcaption></figure></template>
