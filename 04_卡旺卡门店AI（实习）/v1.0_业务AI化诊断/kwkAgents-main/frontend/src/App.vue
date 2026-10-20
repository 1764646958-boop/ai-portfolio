<template>
  <div class="app-page">
    <div class="app-wrapper">
      <Sidebar />

      <main class="main-content">
        <AuthPanel v-if="!authStore.isAuthenticated" />

        <template v-else>
          <DocumentSettings v-if="chatStore.activeNav === 'settings'" />
          <ComparisonWorkspace v-else-if="chatStore.activeNav === 'procurement'" />
          <template v-else>
            <HistorySidebar />
            <ChatArea />
          </template>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue';
import Sidebar from '@/components/Sidebar.vue';
import AuthPanel from '@/components/AuthPanel.vue';
import HistorySidebar from '@/components/HistorySidebar.vue';
import ChatArea from '@/components/Chat/ChatArea.vue';
import DocumentSettings from '@/components/Documents/DocumentSettings.vue';
import ComparisonWorkspace from '@/components/Procurement/ComparisonWorkspace.vue';

import { useAuthStore } from '@/stores/auth';
import { useChatStore } from '@/stores/chat';
import { useSessionStore } from '@/stores/sessions';

const authStore = useAuthStore();
const chatStore = useChatStore();
const sessionStore = useSessionStore();

document.documentElement.dataset.theme = 'light';
document.documentElement.style.colorScheme = 'light';
localStorage.removeItem('kwkagent-theme');

watch(
  () => authStore.currentUser?.username || null,
  (username, previousUsername) => {
    if (username === previousUsername) return;
    chatStore.resetWorkspace();
    sessionStore.$reset();
  }
);

const handleUnauthorized = () => {
  authStore.handleLogout();
  alert('登录已过期，请重新登录');
};

onMounted(async () => {
  window.addEventListener('unauthorized', handleUnauthorized);
  
  if (authStore.token) {
    try {
      await authStore.fetchMe();
    } catch (_) {
      authStore.handleLogout();
    }
  }
});

onUnmounted(() => {
  window.removeEventListener('unauthorized', handleUnauthorized);
});
</script>
