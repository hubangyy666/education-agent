<script setup lang="ts">
import { ref,onMounted } from 'vue'
import { api } from '../api'
import SkillMap from '../components/SkillMap.vue'
import Icon from '../components/Icon.vue'
const abilities=ref<any[]>([]),error=ref('')
onMounted(async()=>{try{abilities.value=await api('/abilities')}catch(e){error.value=(e as Error).message}})
</script>
<template><div class="content-width skills-page"><header class="section-heading"><div><span class="eyebrow">从基础认知，到项目交付</span><h1>你的技能地图</h1><p class="muted">沿着知识的脉络，一步一步建立真本领。</p></div></header><div v-if="error" class="error-message">{{error}}</div><div class="map-legend"><span><i class="legend-dot violet"></i>可探索</span><span><i class="legend-dot green"></i>技能分 ≥ 8 分</span><span>全部关卡开放，箭头表示建议学习顺序</span></div><SkillMap :abilities="abilities"/><div class="map-footer"><Icon name="Lightbulb"/><p>技能分按真实作答加权：课关 × 1、岗关 × 2、赛关 × 3，保留两位小数。课关每一次答错都会计入分数，岗关与赛关在整包提交后统一计入；错题本复答不参与计分。</p></div></div></template>
