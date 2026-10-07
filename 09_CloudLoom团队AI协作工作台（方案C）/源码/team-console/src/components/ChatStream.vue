<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Agent, Msg } from '../stores/chat'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{
  messages: Msg[]
  agents: Agent[]
  streaming?: boolean
  status?: string
  disabled?: boolean
}>()
const emit = defineEmits<{
  (e: 'send', payload: { text: string; files: File[] }): void
  (e: 'recall', id: string): void
}>()

const auth = useAuthStore()
const text = ref('')
const files = ref<File[]>([])
const pickerOpen = ref(false)
const pickerQuery = ref('')
const scrollEl = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const filteredAgents = computed(() => {
  const q = pickerQuery.value.replace(/^@/, '').toLowerCase()
  return props.agents
    .filter((a) => a.enabled !== false)
    .filter((a) => !q || a.id.toLowerCase().includes(q) || a.name.toLowerCase().includes(q))
})

function onInput() {
  const m = text.value.match(/@([^\s@]*)$/)
  pickerOpen.value = !!m
  pickerQuery.value = m ? m[1] : ''
}
function pick(a: Agent) {
  text.value = text.value.replace(/@[^\s@]*$/, '@' + a.id + ' ')
  pickerOpen.value = false
}
function chooseFiles(e: Event) {
  const el = e.target as HTMLInputElement
  files.value = [...files.value, ...Array.from(el.files || [])]
  el.value = ''
}
function submit() {
  const t = text.value.trim()
  if ((!t && !files.value.length) || props.disabled) return
  emit('send', { text: t, files: files.value })
  text.value = ''
  files.value = []
  pickerOpen.value = false
}
// 撤回按钮仅在「本人 + 5 分钟内 + 未撤回」时出现（D18：后端为准，前端只做提示）
function canRecall(m: Msg) {
  if (props.disabled) return false
  if (m.sender_type !== 'member' || m.recalled || m.pending || !m.id) return false
  if (m.sender_id !== auth.user?.id) return false
  return Date.now() - new Date(m.created_at).getTime() < 5 * 60 * 1000
}
function isSelf(m: Msg) {
  return m.sender_type === 'member' && m.sender_id === auth.user?.id
}
async function scrollToEnd() {
  await nextTick()
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}
watch(() => props.messages.map((m) => m.content).join('|'), scrollToEnd)
watch(() => props.status, scrollToEnd)
watch(() => props.streaming, scrollToEnd)
defineExpose({ scrollToEnd })
</script>

<template>
  <div class="h-full flex flex-col min-h-0">
    <!-- 消息流 -->
    <div ref="scrollEl" class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
      <div v-if="!messages.length" class="text-sm text-gray-400 text-center mt-10">
        还没有消息。用 @ 拉 Agent 进来，或直接输入内容。
      </div>
      <div v-for="m in messages" :key="m.id" class="flex" :class="isSelf(m) ? 'justify-end' : 'justify-start'">
        <div class="max-w-[76%]">
          <div class="text-xs text-gray-400 mb-0.5" :class="isSelf(m) ? 'text-right' : ''">
            {{ m.sender_name }}
            <span v-if="m.sender_type === 'agent'" class="ml-1 px-1 rounded bg-purple-50 text-purple-600 dark:bg-purple-900/40">Agent</span>
          </div>
          <div
            class="px-3 py-2 rounded-lg text-sm whitespace-pre-wrap break-words"
            :class="m.recalled
              ? 'bg-gray-100 text-gray-400 italic dark:bg-gray-800'
              : isSelf(m)
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-800 border dark:border-gray-700'"
          >
            <template v-if="m.recalled">消息已撤回</template>
            <template v-else>{{ m.content }}<span v-if="m.pending" class="opacity-60"> ⏳</span></template>
          </div>
          <div class="mt-0.5 text-xs text-gray-400 flex gap-2" :class="isSelf(m) ? 'justify-end' : ''">
            <span>{{ new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</span>
            <button v-if="canRecall(m)" class="hover:text-red-500" @click="emit('recall', m.id)">撤回</button>
          </div>
        </div>
      </div>
      <!-- 唤醒/流式状态（4.2：懒启动「正在唤醒」必须显示） -->
      <div v-if="status || streaming" class="flex items-center gap-2 text-xs text-gray-500">
        <span class="inline-block w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
        <span>{{ status || '正在生成…' }}</span>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="shrink-0 border-t bg-white dark:bg-gray-800 p-3 relative">
      <div v-if="files.length" class="flex flex-wrap gap-2 mb-2">
        <span v-for="(f, i) in files" :key="i" class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700">
          📎 {{ f.name }}
          <button class="ml-1 text-gray-400 hover:text-red-500" @click="files.splice(i, 1)">×</button>
        </span>
      </div>
      <!-- @ 选择器 -->
      <div v-if="pickerOpen && filteredAgents.length"
        class="absolute bottom-full left-3 mb-1 w-72 max-h-56 overflow-y-auto rounded-md border bg-white dark:bg-gray-800 shadow-lg z-10">
        <button v-for="a in filteredAgents" :key="a.id"
          class="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 flex justify-between"
          @click="pick(a)">
          <span>{{ a.name }}</span>
          <span class="text-xs text-gray-400">{{ a.id }}<span v-if="a.status?.running" class="ml-1 text-green-500">运行中</span></span>
        </button>
      </div>
      <div class="flex items-end gap-2">
        <textarea
          v-model="text" rows="2" :disabled="disabled"
          placeholder="输入内容，@ 拉 Agent 进来（如 @cehua）"
          class="flex-1 resize-none rounded-md border px-3 py-2 text-sm bg-white dark:bg-gray-900 dark:border-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          @input="onInput" @keydown.enter.exact.prevent="submit"
        ></textarea>
        <input ref="fileInput" type="file" class="hidden" multiple @change="chooseFiles" />
        <button class="px-3 py-2 rounded-md border text-sm hover:bg-gray-50 dark:hover:bg-gray-700" title="上传文件（≤10MB）"
          :disabled="disabled" @click="fileInput?.click()">📎</button>
        <button class="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
          :disabled="disabled" @click="submit">发送</button>
      </div>
    </div>
  </div>
</template>
