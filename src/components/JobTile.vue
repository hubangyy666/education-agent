<script setup lang="ts">
import { RouterLink } from 'vue-router'
import Icon from './Icon.vue'
import JobArtwork from './JobArtwork.vue'
defineProps<{to?:any,label:string,hint?:string,icon?:string,kind?:string,caption?:string,active?:boolean,done?:boolean}>()
defineEmits<{select:[]}>()
</script>
<template>
  <component :is="to?RouterLink:'button'" :to="to" :type="to?undefined:'button'" class="jp-tile" :class="{active,done}" :aria-current="active?'step':undefined" @click="$emit('select')">
    <span class="jp-tile-square"><small>{{hint}}</small><span v-if="done" class="jp-tile-check"><Icon name="Check" :size="14"/></span><JobArtwork v-if="kind" :kind="kind"/><span v-else class="jp-tile-art"><i class="jp-art-back"></i><i class="jp-art-front"><Icon :name="icon||'BookOpen'" :size="54"/></i><i class="jp-art-dot"></i></span></span>
    <strong>{{label}}</strong><span v-if="caption" class="jp-tile-caption">{{caption}}</span>
  </component>
</template>
