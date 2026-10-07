<script setup lang="ts">
// 主布局空壳（阶段 1）：左栏（会话区 + Agent 区）/ 主区 / 顶栏 Tab 容器
// 移动端适配（<768px 抽屉 + Tab 置底）在阶段 3 完成（D8）
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import SideBar from '../components/SideBar.vue'
import { notifyList, unread, lastPollAt, clearNotify, resetNotify } from '../lib/notify'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const tabs = [
  { name: 'chat', label: '聊天' },
  { name: 'kanban', label: '看板' },
  { name: 'tasks', label: '任务' },
  { name: 'profiles', label: '画像' },
  { name: 'library', label: '资料库' },
  { name: 'memory', label: '记忆' },
  { name: 'settings', label: '设置' },
]
const drawer = ref(false)
const bell = ref(false)
async function logout() {
  await auth.logout()
  resetNotify()   // 换账号后重新建立通知基线，避免串号
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="h-full flex flex-col bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100">
    <!-- 顶栏 Tab 容器 -->
    <header class="h-12 shrink-0 flex items-center border-b bg-white dark:bg-gray-800 px-3 gap-2">
      <button class="md:hidden p-2" @click="drawer = !drawer">☰</button>
      <div class="font-bold mr-4">CloudLoom</div>
      <nav class="flex-1 hidden md:flex gap-1">
        <router-link v-for="t in tabs" :key="t.name" :to="{ name: t.name }"
          class="px-3 py-1.5 rounded-md text-sm hover:bg-gray-100 dark:hover:bg-gray-700"
          active-class="bg-blue-50 text-blue-600 dark:bg-gray-700">{{ t.label }}</router-link>
      </nav>
      <!-- 通知中心：/api/poll 3-5s 轮询（D19），新文件弹桌面通知（设置 Tab 可关） -->
      <div class="relative">
        <button class="text-sm px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700" @click="bell = !bell">
          🔔<span v-if="unread" class="ml-1 text-[10px] px-1 rounded-full bg-red-500 text-white">{{ unread > 99 ? '99+' : unread }}</span>
        </button>
        <div v-if="bell" class="absolute right-0 top-9 z-30 w-72 max-h-80 overflow-auto border rounded-md bg-white dark:bg-gray-800 shadow-lg p-2">
          <div class="flex items-center text-xs text-gray-400 px-1 pb-1 gap-2">
            <span>系统通知 · 轮询 {{ lastPollAt || '—' }}</span>
            <button class="ml-auto text-blue-600" @click="clearNotify(); bell = false">清空</button>
          </div>
          <p v-if="!notifyList.length" class="text-xs text-gray-400 px-1 py-2">暂无新通知（晨报/周复盘/画像等 cron 产物落盘后会出现在这里）</p>
          <div v-for="n in notifyList" :key="n.name + n.mtime" class="px-1 py-1 border-t">
            <div class="text-xs font-medium break-all">{{ n.name }}</div>
            <div class="text-[11px] text-gray-400 whitespace-pre-wrap">{{ (n.preview || '').slice(0, 80) }}</div>
          </div>
        </div>
      </div>
      <div class="text-sm text-gray-500 hidden sm:block">{{ auth.user?.display_name }}</div>
      <button class="text-sm text-gray-400 hover:text-red-500 ml-2 hidden md:inline" @click="logout">退出</button>
    </header>

    <div class="flex-1 flex min-h-0">
      <!-- 左栏：会话区 + Agent 区（阶段 2 填充真实数据） -->
      <aside class="w-64 shrink-0 border-r bg-white dark:bg-gray-800 p-3 hidden md:flex flex-col gap-4">
        <SideBar class="min-h-0" @picked="drawer = false" />
      </aside>
      <!-- 移动端抽屉占位 -->
      <aside v-if="drawer" class="md:hidden fixed inset-y-0 left-0 w-64 z-20 border-r bg-white dark:bg-gray-800 p-3" @click="drawer = false">
        <SideBar class="h-[calc(100vh-3rem)]" @picked="drawer = false" />
        <nav class="flex flex-col gap-1 mt-4">
          <router-link v-for="t in tabs" :key="t.name" :to="{ name: t.name }" class="px-3 py-2 rounded-md text-sm hover:bg-gray-100 dark:hover:bg-gray-700">{{ t.label }}</router-link>
        </nav>
      </aside>
      <!-- 主区 -->
      <main class="flex-1 min-w-0">
        <router-view />
      </main>
    </div>

    <!-- 移动端底部 Tab（D8） -->
    <nav class="md:hidden shrink-0 flex border-t bg-white dark:bg-gray-800 text-xs">
      <router-link v-for="t in tabs" :key="t.name" :to="{ name: t.name }"
        class="flex-1 min-w-0 py-2 text-center text-[10px] leading-tight" active-class="text-blue-600 font-medium">{{ t.label }}</router-link>
    </nav>
  </div>
</template>
