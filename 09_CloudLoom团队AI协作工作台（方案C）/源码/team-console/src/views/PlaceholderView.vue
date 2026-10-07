<script setup lang="ts">
// 阶段 1 占位视图：后续阶段逐 Tab 替换为真实页面
import { computed } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
const title = computed(() => (route.meta.title as string) || '页面')
</script>

<template>
  <div class="h-full flex items-center justify-center text-gray-400">
    <div class="text-center">
      <div class="text-lg font-medium">{{ title }}</div>
      <div class="text-sm mt-1">脚手架已就位，功能页面将在阶段 2 / 3 实现</div>
    </div>
  </div>
</template>
