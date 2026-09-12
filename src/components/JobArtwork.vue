<script setup lang="ts">
defineProps<{ kind: string }>()
</script>

<template>
  <svg class="job-artwork" viewBox="0 0 240 150" fill="none" aria-hidden="true">
    <template v-if="kind==='vision'">
      <rect x="51" y="24" width="140" height="99" rx="12" fill="#CBD7FF"/>
      <rect x="42" y="15" width="140" height="99" rx="12" fill="white" stroke="#3459CC" stroke-width="3"/>
      <path d="M53 91 88 55l25 24 18-15 40 37H53Z" fill="#DBE5FF"/>
      <circle cx="149" cy="41" r="10" fill="#FFD867"/>
      <path d="m76 74 8-15h34l11 15v15H70V74h6Z" fill="#4E6EE5"/>
      <path d="m88 63-5 11h35l-6-11H88Z" fill="#C6D3FF"/>
      <circle cx="83" cy="89" r="7" fill="#233C85"/><circle cx="118" cy="89" r="7" fill="#233C85"/>
      <path d="M61 65v-14h16m46 0h16v14m0 26v14h-16m-46 0H61V91" stroke="#4865D8" stroke-width="3"/>
      <path d="m156 90 31 26-18 2-8 15-5-43Z" fill="#FFCA46" stroke="#D7A021" stroke-width="2"/>
      <path d="M49 131h139" stroke="#BAC9F5" stroke-width="3" stroke-linecap="round"/>
    </template>
    <template v-else-if="kind==='industrial'">
      <path d="m64 56 72-29 43 32-70 31-45-34Z" fill="#FFE5AE" stroke="#A87927" stroke-width="2"/>
      <path d="m64 56 45 34v37l-45-34V56Z" fill="#D99A37"/>
      <path d="m109 90 70-31v38l-70 30V90Z" fill="#F2C264"/>
      <path d="m113 49 9 10-9 8 16 10" stroke="#925813" stroke-width="4" stroke-linecap="round"/>
      <circle cx="151" cy="62" r="29" fill="#FFFCF0" fill-opacity=".8" stroke="#5C4786" stroke-width="7"/>
      <path d="m174 83 23 24" stroke="#5C4786" stroke-width="12" stroke-linecap="round"/>
      <path d="m137 57 8 7 13-14" stroke="#B78432" stroke-width="3" stroke-linecap="round"/>
      <path d="M48 130h134" stroke="#E9D2AA" stroke-width="3" stroke-linecap="round"/>
      <path d="M47 28v16m-8-8h16" stroke="#E9B54B" stroke-width="3"/>
    </template>
    <template v-else-if="kind==='text'">
      <rect x="69" y="30" width="111" height="100" rx="9" fill="#D9C7F5"/>
      <rect x="57" y="18" width="111" height="100" rx="9" fill="white" stroke="#7950AE" stroke-width="3"/>
      <rect x="70" y="36" width="38" height="13" rx="3" fill="#BE9AEA"/>
      <path d="M116 43h37M71 63h82M71 80h48M128 80h25M71 98h68" stroke="#BFB0D6" stroke-width="4" stroke-linecap="round"/>
      <rect x="67" y="72" width="56" height="16" rx="3" fill="#E9DDF8" stroke="#9162C9" stroke-width="2"/>
      <path d="M137 100h45a10 10 0 0 1 10 10v17h-14l-12 11v-11h-29a10 10 0 0 1-10-10v-7a10 10 0 0 1 10-10Z" fill="#FFD35E"/>
      <path d="M140 114h5m9 0h5m9 0h5" stroke="#8B6922" stroke-width="4" stroke-linecap="round"/>
      <path d="M39 128h73" stroke="#D9C9EF" stroke-width="3" stroke-linecap="round"/>
    </template>
    <template v-else>
      <rect x="60" y="26" width="110" height="105" rx="10" fill="#C7E5D5"/>
      <rect x="49" y="17" width="110" height="105" rx="10" fill="white" stroke="#3C8165" stroke-width="3"/>
      <rect x="77" y="10" width="53" height="17" rx="6" fill="#73B696"/>
      <path d="m66 49 5 5 10-12m-15 32 5 5 10-12m-15 32 5 5 10-12" stroke="#55A47B" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M93 49h45M93 74h38M93 99h30" stroke="#B9D4C7" stroke-width="4" stroke-linecap="round"/>
      <path d="m162 67 30 11v22c0 16-13 28-30 36-17-8-30-20-30-36V78l30-11Z" fill="#4C9775"/>
      <path d="m148 101 10 10 19-24" stroke="white" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="189" cy="36" r="8" fill="#FFDA69"/>
      <path d="M42 134h76" stroke="#C2DBCD" stroke-width="3" stroke-linecap="round"/>
    </template>
  </svg>
</template>
