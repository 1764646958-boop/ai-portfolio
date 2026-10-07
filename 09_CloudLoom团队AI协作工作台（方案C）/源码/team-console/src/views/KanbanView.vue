<script setup lang="ts">
// 看板 Tab（C1 共享看板 / 4.1）：GET /api/kanban 只读渲染 + POST /api/kanban-command 交值班 Agent 执行
// 看板写操作一律走 kanban-command（Agent 侧 kanban_* 工具），前端不直连看板库（SPEC 接口边界）
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api'

interface KComment { id: string; author: string; body: string; created_at: string }
interface KTask {
  id: string; title: string; body: string | null; assignee: string | null
  status: string; priority: string | null; created_by: string | null
  created_at: string; started_at: string | null; completed_at: string | null
  block_kind: string | null; result: string | null; comments: KComment[]
}
interface AgentBrief { id: string; name: string; enabled: boolean }

const ORDER = ['todo', 'in_progress', 'blocked', 'review', 'done']
const LABEL: Record<string, string> = {
  todo: '待办', in_progress: '进行中', blocked: '阻塞', review: '待复核', done: '已完成',
}
const DOT: Record<string, string> = {
  todo: 'bg-gray-400', in_progress: 'bg-blue-500', blocked: 'bg-red-500', review: 'bg-amber-500', done: 'bg-green-500',
}
const tasks = ref<KTask[]>([])
const agents = ref<AgentBrief[]>([])
const loading = ref(false)
const err = ref('')
const lastAt = ref('')
const onlyBlocked = ref(false)
const detail = ref<KTask | null>(null)
const cmd = ref('')
const cmdAgent = ref('zhiban')
const cmdBusy = ref(false)
const cmdReply = ref('')
const cmdErr = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const statuses = computed(() => {
  const keys = Array.from(new Set(tasks.value.map((t) => t.status || 'todo')))
  const known = ORDER.filter((k) => keys.includes(k))
  const other = keys.filter((k) => !ORDER.includes(k)).sort()
  return known.concat(other)
})
const visible = computed(() => {
  if (onlyBlocked.value) return tasks.value.filter((t) => t.status === 'blocked' || t.block_kind)
  return tasks.value
})
function col(s: string) { return visible.value.filter((t) => (t.status || 'todo') === s) }
function label(s: string) { return LABEL[s] || s }
function dot(s: string) { return DOT[s] || 'bg-gray-300' }
function fmt(ts: string | null) { return ts ? String(ts).replace('T', ' ').slice(0, 16) : '—' }

async function load() {
  loading.value = true
  try {
    const r = await api<{ tasks: KTask[] }>('/kanban')
    tasks.value = r.tasks || []
    lastAt.value = new Date().toLocaleTimeString()
    err.value = ''
  } catch (e) { err.value = (e as Error).message } finally { loading.value = false }
}
async function loadAgents() {
  try { agents.value = (await api<{ agents: AgentBrief[] }>('/agents')).agents.filter((a) => a.enabled) }
  catch { agents.value = [] }
}
async function sendCmd() {
  if (!cmd.value.trim() || cmdBusy.value) return
  cmdBusy.value = true; cmdErr.value = ''; cmdReply.value = ''
  try {
    const r = await api<{ agent: string; reply: string }>('/kanban-command', {
      method: 'POST', body: JSON.stringify({ command: cmd.value.trim(), agent: cmdAgent.value }),
    })
    cmdReply.value = r.reply || '（Agent 未返回文本）'
    cmd.value = ''
    await load()
  } catch (e) { cmdErr.value = (e as Error).message } finally { cmdBusy.value = false }
}
onMounted(() => { load(); loadAgents(); timer = setInterval(load, 8000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="shrink-0 px-4 py-3 border-b bg-white dark:bg-gray-800">
      <div class="flex items-center gap-3 flex-wrap">
        <h2 class="font-medium">共享看板</h2>
        <span class="text-xs text-gray-400">{{ tasks.length }} 张卡 · 8s 自动刷新 · 更新于 {{ lastAt }}</span>
        <label class="text-xs text-gray-500 flex items-center gap-1 ml-auto">
          <input type="checkbox" v-model="onlyBlocked" /> 仅看阻塞
        </label>
        <button class="text-xs px-2 py-1 rounded border hover:bg-gray-50 dark:hover:bg-gray-700" @click="load">刷新</button>
      </div>
      <p v-if="err" class="text-xs text-red-500 mt-2">加载失败：{{ err }}</p>
      <div class="mt-3 border rounded-md p-2 bg-gray-50 dark:bg-gray-900">
        <div class="flex items-center gap-2 text-xs text-gray-500 mb-1">
          <span>对看板下指令（交给 Agent 执行，例如「给某张卡加评论」「新建卡片：……」）</span>
          <select v-model="cmdAgent" class="ml-auto border rounded px-1 py-0.5 bg-white dark:bg-gray-800">
            <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}（{{ a.id }}）</option>
            <option v-if="!agents.length" value="zhiban">值班 Agent</option>
          </select>
        </div>
        <textarea v-model="cmd" rows="2" placeholder="用自然语言描述要执行的看板操作"
          class="w-full text-sm border rounded p-2 bg-white dark:bg-gray-800"></textarea>
        <div class="flex items-center gap-2 mt-2">
          <button class="text-xs px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-50"
            :disabled="cmdBusy || !cmd.trim()" @click="sendCmd">{{ cmdBusy ? 'Agent 执行中…' : '下发指令' }}</button>
          <span v-if="cmdBusy" class="text-xs text-gray-400">Agent 执行需数十秒至数分钟，请勿关闭页面</span>
        </div>
        <p v-if="cmdErr" class="text-xs text-red-500 mt-2">{{ cmdErr }}</p>
        <pre v-if="cmdReply" class="text-xs whitespace-pre-wrap mt-2 border-t pt-2 max-h-40 overflow-auto">{{ cmdReply }}</pre>
      </div>
    </div>

    <div class="flex-1 min-h-0 overflow-auto p-4">
      <div class="flex gap-3 items-start min-h-full">
        <section v-for="s in statuses" :key="s" class="w-72 shrink-0">
          <header class="flex items-center gap-2 mb-2 px-1">
            <span class="w-2 h-2 rounded-full" :class="dot(s)"></span>
            <span class="text-sm font-medium">{{ label(s) }}</span>
            <span class="text-xs text-gray-400">{{ col(s).length }}</span>
          </header>
          <div class="flex flex-col gap-2">
            <article v-for="t in col(s)" :key="t.id"
              class="border rounded-md p-3 bg-white dark:bg-gray-800 cursor-pointer hover:shadow"
              @click="detail = t">
              <div class="text-sm font-medium leading-snug">{{ t.title }}</div>
              <div class="text-[11px] text-gray-400 mt-1 font-mono">{{ t.id }}</div>
              <div class="flex items-center gap-2 mt-2 flex-wrap text-[11px]">
                <span v-if="t.assignee" class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700">{{ t.assignee }}</span>
                <span v-if="t.priority" class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700">{{ t.priority }}</span>
                <span v-if="t.block_kind" class="px-1.5 py-0.5 rounded bg-red-50 text-red-600">阻塞 {{ t.block_kind }}</span>
                <span v-if="t.comments && t.comments.length" class="text-gray-400">评论 {{ t.comments.length }}</span>
              </div>
              <div class="text-[11px] text-gray-400 mt-2">{{ fmt(t.created_at) }}</div>
            </article>
            <p v-if="!col(s).length" class="text-xs text-gray-300 px-1">（空）</p>
          </div>
        </section>
        <p v-if="!tasks.length && !loading" class="text-sm text-gray-400">暂无看板卡片</p>
      </div>
    </div>

    <div v-if="detail" class="fixed inset-0 z-30 bg-black/40 flex items-center justify-center p-4" @click.self="detail = null">
      <div class="bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full max-h-[85vh] overflow-auto p-5">
        <div class="flex items-start gap-3">
          <h3 class="font-medium flex-1">{{ detail.title }}</h3>
          <button class="text-gray-400 hover:text-gray-600" @click="detail = null">✕</button>
        </div>
        <div class="text-xs text-gray-500 mt-2 flex gap-3 flex-wrap">
          <span>状态：{{ label(detail.status) }}</span>
          <span>负责人：{{ detail.assignee || '—' }}</span>
          <span>优先级：{{ detail.priority || '—' }}</span>
          <span class="font-mono">{{ detail.id }}</span>
        </div>
        <pre v-if="detail.body" class="text-sm whitespace-pre-wrap mt-3 border-t pt-3">{{ detail.body }}</pre>
        <div v-if="detail.result" class="mt-3 border-t pt-3">
          <div class="text-xs text-gray-400 mb-1">结果</div>
          <pre class="text-sm whitespace-pre-wrap">{{ detail.result }}</pre>
        </div>
        <div v-if="detail.comments && detail.comments.length" class="mt-3 border-t pt-3">
          <div class="text-xs text-gray-400 mb-2">评论（{{ detail.comments.length }}）</div>
          <div v-for="c in detail.comments" :key="c.id" class="text-sm mb-2">
            <span class="text-gray-500">{{ c.author }}</span>
            <span class="text-[11px] text-gray-400 ml-2">{{ fmt(c.created_at) }}</span>
            <p class="whitespace-pre-wrap">{{ c.body }}</p>
          </div>
        </div>
        <div class="text-[11px] text-gray-400 mt-3">
          创建：{{ fmt(detail.created_at) }} · 开始：{{ fmt(detail.started_at) }} · 完成：{{ fmt(detail.completed_at) }}
        </div>
      </div>
    </div>
  </div>
</template>
