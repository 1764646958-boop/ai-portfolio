<template>
  <section class="welcome-screen">
    <img class="welcome-wordmark" :src="brandLogo" alt="卡旺卡 COME WONKA" />
    <span class="welcome-eyebrow"><i class="fa-solid fa-mug-hot"></i> 卡旺卡知识库</span>
    <h2>今天想了解什么？</h2>
    <p>我会检索内部知识、展示处理过程，并将关键结论链接回原始证据。</p>

    <div class="welcome-capabilities">
      <span><i class="fa-solid fa-magnifying-glass"></i> 混合检索</span>
      <span><i class="fa-solid fa-diagram-project"></i> 并行 Agent</span>
      <span><i class="fa-solid fa-link"></i> 可追溯引用</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import brandLogo from '@/assets/brand/kawangka-wordmark.jpg';
</script>
