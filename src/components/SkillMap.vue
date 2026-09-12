<script setup lang="ts">
import { computed } from 'vue'
import { formatSkillScore, skillScore } from '../scores'

interface Ability { id: string; name: string; skill_score: number }
const props = defineProps<{ abilities: Ability[] }>()
const byId = computed(() => new Map(props.abilities.map(ability => [ability.id, ability])))

// Coordinates follow the supplied 1122 × 1402 illustration. Only the local
// island and its label are interactive; the roads and whitespace stay inert.
const nodes = [
  { id: 'A1', name: '标注基础认知', color: '#7838fa', card: [578, 31, 188, 103], progress: [592, 99, 159], island: 'M360 147 L397 122 L399 72 L429 58 L454 77 L468 66 C462 1 558 -7 564 61 L583 92 L596 128 L632 158 L584 200 L544 185 L509 207 L474 187 L445 209 L361 167 Z' },
  { id: 'A2', name: '标注规范理解', color: '#075cff', card: [576, 225, 205, 103], progress: [599, 294, 165], island: 'M351 322 L385 292 L394 253 L422 243 L446 259 L449 228 L474 216 L513 236 L550 217 L574 230 L574 278 L601 327 L630 345 L554 391 L515 373 L486 390 L433 366 L401 366 L351 337 Z' },
  { id: 'A3', name: '分类与属性判断', color: '#eb16a5', card: [263, 400, 188, 105], progress: [277, 469, 161], island: 'M26 490 L59 463 L60 424 L86 412 L85 397 L108 385 L136 402 L147 397 L182 380 L237 410 L234 446 L260 473 L266 506 L296 524 L238 566 L202 550 L169 566 L117 543 L82 558 L27 516 Z' },
  { id: 'A4', name: '目标检测与定位', color: '#7535fb', card: [880, 396, 196, 106], progress: [901, 466, 158], island: 'M624 497 L659 462 L664 426 L688 410 L718 427 L742 399 L774 388 L811 389 L833 399 L839 386 L864 402 L866 446 L894 484 L931 516 L915 546 L862 572 L817 555 L786 577 L741 552 L698 570 L626 526 Z' },
  { id: 'A5', name: '精细分割', color: '#00bfd4', card: [877, 603, 200, 106], progress: [902, 674, 159], island: 'M637 687 L670 654 L676 610 L703 595 L730 617 L751 610 L788 602 L815 627 L835 612 L849 597 L869 609 L869 650 L892 683 L921 713 L862 755 L816 750 L784 771 L745 749 L701 747 L638 715 Z' },
  { id: 'A6', name: '工业缺陷识别', color: '#e29409', card: [547, 794, 170, 102], progress: [565, 863, 140], island: 'M321 872 L351 837 L356 812 L382 795 L412 812 L423 786 L461 768 L485 781 L507 813 L536 830 L551 862 L553 914 L577 934 L517 962 L466 948 L438 954 L399 932 L370 935 L321 905 Z' },
  { id: 'A7', name: '复杂视觉场景', color: '#0875ff', card: [968, 807, 131, 101], progress: [973, 875, 111], island: 'M742 883 L787 845 L794 799 L816 782 L846 800 L866 782 L889 775 L902 797 L932 793 L949 817 L949 854 L974 879 L972 914 L995 935 L935 973 L892 953 L864 971 L818 944 L792 945 L742 908 Z' },
  { id: 'A8', name: '文本与语义标注', color: '#00b68c', card: [262, 603, 182, 107], progress: [272, 674, 158], island: 'M34 688 L79 649 L84 612 L111 600 L139 618 L167 594 L209 599 L235 621 L236 646 L255 640 L266 676 L267 714 L294 734 L240 769 L200 750 L171 769 L120 744 L84 748 L36 718 Z' },
  { id: 'A9', name: 'AI协同与质量审核', color: '#8536ed', card: [609, 1015, 213, 106], progress: [630, 1086, 173], island: 'M368 1122 L403 1087 L408 1034 L430 1018 L460 1035 L479 1027 L510 1015 L545 1021 L576 1037 L583 1073 L609 1093 L618 1124 L654 1138 L598 1180 L550 1165 L523 1185 L477 1162 L434 1175 L369 1148 Z' },
  { id: 'A10', name: '综合项目交付', color: '#eea914', card: [610, 1218, 209, 106], progress: [631, 1289, 169], island: 'M375 1317 L406 1288 L410 1234 L431 1218 L456 1233 L479 1236 L481 1218 L509 1209 L549 1215 L575 1232 L578 1272 L605 1301 L618 1326 L651 1344 L594 1385 L550 1373 L524 1391 L478 1371 L439 1380 L376 1348 Z' },
] as const

function mastery(id: string) {
  const value = byId.value.get(id)?.skill_score
  return typeof value === 'number' && Number.isFinite(value) ? skillScore(value) : null
}
</script>

<template>
  <div class="illustrated-map-scroll">
    <svg class="illustrated-map" viewBox="0 0 1122 1402" aria-label="技能地图，点击技能建筑或名称进入学习">
      <image href="/skills/skill-map.png" width="1122" height="1402" aria-hidden="true" />
      <RouterLink v-for="node in nodes" :key="node.id" :to="'/skills/' + node.id" custom v-slot="{ href, navigate }">
        <a :href="href" @click="navigate" class="map-hotspot" :class="{ mastered: (mastery(node.id) ?? 0) >= 8 }"
          :style="{ '--node-color': node.color }" :data-ability="node.id"
          :aria-label="`${node.id} ${byId.get(node.id)?.name ?? node.name}，技能分${mastery(node.id) === null ? '加载中' : formatSkillScore(mastery(node.id)) + '分，满分10分'}，进入学习`">
          <path class="island-halo" :d="node.island" />
          <rect class="card-halo" :x="node.card[0]" :y="node.card[1]" :width="node.card[2]" :height="node.card[3]" rx="14" />
          <!-- Cover the reference's baked-in sample values with live mastery. -->
          <g aria-hidden="true" class="live-mastery">
            <rect :x="node.progress[0] - 2" :y="node.progress[1]" :width="node.progress[2] + 4" height="29" rx="3" fill="#fff" />
            <rect :x="node.progress[0]" :y="node.progress[1] + 7" :width="node.progress[2] - 82" height="12" rx="6" fill="#d9d7ef" />
            <rect :x="node.progress[0]" :y="node.progress[1] + 7" :width="(node.progress[2] - 82) * (mastery(node.id) ?? 0) / 10" height="12" rx="6" class="mastery-fill" />
            <text :x="node.progress[0] + node.progress[2]" :y="node.progress[1] + 22" text-anchor="end">{{ mastery(node.id) === null ? '—' : formatSkillScore(mastery(node.id)) + '分' }}</text>
          </g>
        </a>
      </RouterLink>
    </svg>
  </div>
</template>

<style scoped>
.illustrated-map-scroll { overflow-x: auto; padding: 18px 0 24px; }
.illustrated-map { display: block; width: 100%; min-width: 740px; height: auto; margin: 0 auto; }
.map-hotspot { cursor: pointer; outline: none; -webkit-tap-highlight-color: transparent; }
.island-halo, .card-halo { fill: transparent; stroke: transparent; stroke-width: 2; transition: fill .2s, stroke .2s, filter .2s; }
.island-halo { stroke-linejoin: round; }
.map-hotspot:hover .island-halo, .map-hotspot:focus-visible .island-halo {
  fill: color-mix(in srgb, var(--node-color) 10%, transparent);
  stroke: color-mix(in srgb, var(--node-color) 42%, transparent);
  filter: drop-shadow(0 9px 10px var(--node-color));
}
.map-hotspot:hover .card-halo, .map-hotspot:focus-visible .card-halo {
  fill: color-mix(in srgb, var(--node-color) 5%, transparent);
  stroke: var(--node-color);
  filter: drop-shadow(0 6px 8px var(--node-color));
}
.map-hotspot:active .island-halo { fill: color-mix(in srgb, var(--node-color) 22%, transparent); }
.map-hotspot:focus-visible .card-halo { stroke-width: 4; }
.live-mastery { pointer-events: none; }
.live-mastery text { font: 19px Arial, sans-serif; fill: #171442; }
.mastery-fill { fill: var(--node-color); }
.mastered .mastery-fill { fill: #439c58; }
.mastered .card-halo { stroke: #439c58; }
@media (max-width: 760px) {
  .illustrated-map-scroll { margin-inline: -21px; padding-inline: 12px; }
}
@media (prefers-reduced-motion: reduce) {
  .island-halo, .card-halo { transition: none; }
}
</style>
