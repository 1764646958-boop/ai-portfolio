<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const displayName = ref('')
const error = ref('')
const notice = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''; notice.value = ''; busy.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(username.value, password.value)
      router.push({ name: 'chat' })
    } else {
      const r = await auth.register(username.value, password.value, displayName.value || username.value)
      if (r.pending) { notice.value = r.message; mode.value = 'login' }
      else { notice.value = r.message; await auth.login(username.value, password.value); router.push({ name: 'chat' }) }
    }
  } catch (e: any) { error.value = e.message }
  finally { busy.value = false }
}
</script>

<template>
  <div class="min-h-full flex items-center justify-center bg-gray-100 dark:bg-gray-900 px-4">
    <div class="w-full max-w-sm bg-white dark:bg-gray-800 rounded-xl shadow p-8">
      <div class="text-center mb-6">
        <div class="text-2xl font-bold text-gray-800 dark:text-gray-100">CloudLoom</div>
        <div class="text-sm text-gray-500 mt-1">楚华成章 · 团队协作工作台</div>
      </div>
      <div class="flex mb-5 rounded-lg bg-gray-100 dark:bg-gray-700 p-1 text-sm">
        <button class="flex-1 py-1.5 rounded-md" :class="mode==='login' ? 'bg-white dark:bg-gray-600 shadow font-medium' : 'text-gray-500'" @click="mode='login'">登录</button>
        <button class="flex-1 py-1.5 rounded-md" :class="mode==='register' ? 'bg-white dark:bg-gray-600 shadow font-medium' : 'text-gray-500'" @click="mode='register'">注册</button>
      </div>
      <form class="space-y-3" @submit.prevent="submit">
        <input v-model.trim="username" required placeholder="用户名" class="w-full border rounded-lg px-3 py-2 dark:bg-gray-700 dark:border-gray-600" />
        <input v-if="mode==='register'" v-model.trim="displayName" placeholder="显示名（可选）" class="w-full border rounded-lg px-3 py-2 dark:bg-gray-700 dark:border-gray-600" />
        <input v-model="password" required type="password" placeholder="密码" class="w-full border rounded-lg px-3 py-2 dark:bg-gray-700 dark:border-gray-600" />
        <p v-if="error" class="text-sm text-red-500">{{ error }}</p>
        <p v-if="notice" class="text-sm text-green-600">{{ notice }}</p>
        <button :disabled="busy" class="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 disabled:opacity-50">
          {{ busy ? '处理中…' : (mode==='login' ? '登录' : '注册') }}
        </button>
      </form>
      <p class="text-xs text-gray-400 mt-4 text-center">首个注册账号自动成为管理员；后续账号需管理员批准</p>
    </div>
  </div>
</template>
