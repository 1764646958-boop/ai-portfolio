<script setup lang="ts">
// 任务 Tab：发起（含 @引用文件 / @引用记忆）、列表与状态徽标、waiting_approval 审批区、产物预览/下载/分享、取消
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api'
import { useChatStore } from '../stores/chat'

interface Out { id: string; task_id: string; file_name: string; file_size: number | null; created_at: string }
interface Correction { id: string; action: string; note: string; decided_by: string; created_at: string }
interface Task {
  id: string; title: string; description: string; agent_id: string
  ref_files: string[]; ref_memories: string[]; status: string
  requires_approval: boolean; approval_status: string | null; approved_by: string | null
  correction_note: string | null; progress: string | null; error: string | null
  result_summary: string | null; memory_visibility: string
  created_by: string; created_at: string; completed_at: string | null
  queue_ahead?: number; outputs?: Out[]; corrections?: Correction[]
  meta?: { delivery_status?: { verdict: string; source: string }; approval_forced_by?: string[]; zhiban_review?: { verdict: string; reason: string } }
}
interface LibFile { id: string; kind: string; name: string; category: string; url: string | null }
interface ShareConv { id: string; type: string; title: string; members: { id: string; name: string }[] }
interface Mem { id: string; type: string; title: string; content: string; tags: string[]; visibility: string; author: string }

const chat = useChatStore()
const tasks = ref<Task[]>([])
const detail = ref<Task | null>(null)
const libFiles = ref<LibFile[]>([])
const mems = ref<Mem[]>([])
const memQ = ref('')
const note = ref('')
const err = ref('')
const busy = ref(false)
const showForm = ref(false)
const preview = ref<{ name: string; text: string } | null>(null)
const shareOut = ref<{ t: Task; o: Out } | null>(null)
const shareConvs = ref<ShareConv[]>([])
const shareMsg = ref('')
const filter = ref('')
let timer: number | undefined

const form = ref({
  title: '', description: '', agent_id: '',
  ref_files: [] as string[], ref_memories: [] as string[],
  requires_approval: false, memory_visibility: 'team' as 'team' | 'private' | 'restricted',
  memory_allow_members: [] as string[],
})

const STATUS_META: Record<string, { label: string; cls: string }> = {
  queued: { label: '排队中', cls: 'bg-gray-100 text-gray-600 dark:bg-gray-700' },
  running: { label: '执行中', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40' },
  waiting_approval: { label: '待审批', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40' },
  done: { label: '已完成', cls: 'bg-green-100 text-green-700 dark:bg-green-900/40' },
  failed: { label: '失败', cls: 'bg-red-100 text-red-700 dark:bg-red-900/40' },
}
const shown = computed(() => (filter.value ? tasks.value.filter((t) => t.status === filter.value) : tasks.value))
const pendingCount = computed(() => tasks.value.filter((t) => t.status === 'waiting_approval').length)
const canDecide = computed(() => {
  const t = detail.value
  return !!t && t.status === 'waiting_approval'
})

async function load() {
  tasks.value = (await api<{ tasks: Task[] }>('/tasks?limit=200')).tasks
  if (detail.value) {
    try { detail.value = (await api<{ task: Task }>(`/tasks/${detail.value.id}`)).task } catch { detail.value = null }
  }
}
async function loadLib() { libFiles.value = (await api<{ files: LibFile[] }>('/files')).files }
async function searchMem() {
  try { mems.value = (await api<{ memories: Mem[] }>(`/memories?q=${encodeURIComponent(memQ.value)}&limit=20`)).memories }
  catch (e: any) { err.value = e.message }
}
async function create() {
  err.value = ''
  if (!form.value.title.trim() || !form.value.description.trim() || !form.value.agent_id) {
    err.value = '标题、描述、执行 Agent 均为必填'
    return
  }
  if (isRestricted.value && !form.value.memory_allow_members.length) {
    err.value = '可见性为「指定成员」时，至少勾选 1 位可见成员'
    return
  }
  busy.value = true
  try {
    const r = await api<{ task: Task; approval_forced_by: string[] }>('/tasks', {
      method: 'POST', body: JSON.stringify({ ...form.value, memory_allow_members: isRestricted.value ? form.value.memory_allow_members : [] }),
    })
    if (r.approval_forced_by?.length) err.value = `已按 D36 强制人审（命中：${r.approval_forced_by.join('、')}），完成后需审批`
    form.value = { title: '', description: '', agent_id: '', ref_files: [], ref_memories: [], requires_approval: false, memory_visibility: 'team' , memory_allow_members: [] }
    showForm.value = false
    await load()
    await openDetail(r.task.id)
  } catch (e: any) { err.value = e.message } finally { busy.value = false }
}
async function openDetail(id: string) { detail.value = (await api<{ task: Task }>(`/tasks/${id}`)).task }
async function decide(action: 'approve' | 'modify' | 'reject') {
  if (!detail.value || !note.value.trim()) { err.value = '审批意见（note）必填'; return }
  busy.value = true
  try {
    const r = await api<{ task: Task }>(`/tasks/${detail.value.id}/approval`, {
      method: 'POST', body: JSON.stringify({ action, note: note.value }),
    })
    note.value = ''
    err.value = ''
    detail.value = r.task
    await load()
  } catch (e: any) { err.value = e.message } finally { busy.value = false }
}
async function cancelTask(t: Task) {
  try {
    const r = await api<{ task: Task }>(`/tasks/${t.id}/cancel`, { method: 'POST' })
    detail.value = r.task
    await load()
  } catch (e: any) { err.value = e.message }
}
const dlUrl = (t: Task, o: Out) => `/api/tasks/${t.id}/outputs/${o.id}/download`
async function doPreview(t: Task, o: Out) {
  try {
    const res = await fetch(dlUrl(t, o), { credentials: 'same-origin' })
    if (!res.ok) throw new Error(`读取失败 ${res.status}`)
    const text = await res.text()
    preview.value = { name: o.file_name, text: text.slice(0, 20000) }
  } catch (e: any) { err.value = e.message }
}
// 分享：登记为资料库链接（团队成员凭下载地址可取），并复制绝对地址
async function share(t: Task, o: Out) {
  const url = new URL(dlUrl(t, o), window.location.origin).toString()
  try {
    await api('/links', { method: 'POST', body: JSON.stringify({ name: `任务产物：${o.file_name}`, url, category: '资料库' }) })
    await navigator.clipboard?.writeText(url).catch(() => {})
    err.value = `已分享到资料库并复制链接：${url}`
    await loadLib()
  } catch (e: any) { err.value = e.message }
}
// 分享到会话（验收项11「可分享到会话」）：把产物下载地址作为消息发进指定会话。
// 复用既有 /conversations 与 /conversations/:id/messages 接口，未新增后端 API。
const convLabel = (c: ShareConv) => c.title || (c.type === 'dm' ? c.members.map((m) => m.name).join('、') : '群聊')
async function openShareConv(t: Task, o: Out) {
  shareOut.value = { t, o }
  shareMsg.value = ''
  try {
    const r = await api<{ conversations: ShareConv[] }>('/conversations')
    shareConvs.value = r.conversations
  } catch (e: any) { shareMsg.value = '会话列表读取失败：' + e.message }
}
async function doShareConv(convId: string) {
  if (!shareOut.value) return
  const { t, o } = shareOut.value
  const url = new URL(dlUrl(t, o), window.location.origin).toString()
  try {
    await api('/conversations/' + convId + '/messages', {
      method: 'POST',
      body: JSON.stringify({ content: '【任务产物分享】' + o.file_name + String.fromCharCode(10) + url, type: 'text' }),
    })
    shareMsg.value = '已分享到会话'
    setTimeout(() => { shareOut.value = null }, 900)
  } catch (e: any) { shareMsg.value = '分享失败：' + e.message }
}function toggle(arr: string[], id: string) {
  const i = arr.indexOf(id)
  if (i >= 0) arr.splice(i, 1); else arr.push(id)
}
function fmtSize(n: number | null) { return n == null ? '-' : n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB` }

interface Member { id: string; username: string; display_name: string; role: string; status: string }
const allMembers = ref<Member[]>([])
const isRestricted = computed(() => form.value.memory_visibility === 'restricted')
const pickableMembers = computed(() => allMembers.value.filter((m) => m.status === 'active'))
async function loadMembers() {
  try { allMembers.value = (await api<{ members: Member[] }>('/members')).members } catch { allMembers.value = [] }
}
function toggleAllow(id: string) {
  const a = form.value.memory_allow_members
  const i = a.indexOf(id)
  if (i >= 0) a.splice(i, 1)
  else a.push(id)
}
onMounted(async () => {
  await Promise.all([chat.loadAgents(), load(), loadLib(), loadMembers()])
  await searchMem()
  timer = window.setInterval(() => load().catch(() => {}), 5000)
})
onUnmounted(() => { if (timer) window.clearInterval(timer) })
</script>

<template>
  <div class="flex h-full min-h-0">
    <!-- 列表区 -->
    <div class="flex-1 flex flex-col min-w-0">
      <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2 flex-wrap">
        <h2 class="font-semibold mr-2">办公任务</h2>
        <button class="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700" @click="showForm = !showForm">
          {{ showForm ? '收起' : '+ 发起任务' }}
        </button>
        <select v-model="filter" class="text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-transparent px-2 py-1.5">
          <option value="">全部状态</option>
          <option v-for="(m, k) in STATUS_META" :key="k" :value="k">{{ m.label }}</option>
        </select>
        <span v-if="pendingCount" class="text-xs px-2 py-1 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/40">
          {{ pendingCount }} 项待你审批
        </span>
      </div>

      <div v-if="showForm" class="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 space-y-3 overflow-y-auto max-h-[52%]">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input v-model="form.title" placeholder="任务标题 *" class="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm" />
          <select v-model="form.agent_id" class="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm">
            <option value="">选择执行 Agent *</option>
            <option v-for="a in chat.agents" :key="a.id" :value="a.id">{{ a.name }}（{{ a.id }}）</option>
          </select>
        </div>
        <textarea v-model="form.description" rows="4" placeholder="任务描述 *（要交付什么、口径与格式要求）" class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm"></textarea>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div class="rounded-lg border border-gray-300 dark:border-gray-600 p-3 bg-white dark:bg-gray-900">
            <div class="text-xs font-medium mb-2">@ 引用文件（资料库）</div>
            <div class="max-h-32 overflow-y-auto space-y-1">
              <label v-for="f in libFiles" :key="f.id" class="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" :checked="form.ref_files.includes(f.id)" @change="toggle(form.ref_files, f.id)" />
                <span class="truncate">{{ f.name }}</span>
              </label>
              <div v-if="!libFiles.length" class="text-xs text-gray-400">资料库为空</div>
            </div>
          </div>
          <div class="rounded-lg border border-gray-300 dark:border-gray-600 p-3 bg-white dark:bg-gray-900">
            <div class="text-xs font-medium mb-2">@ 引用记忆</div>
            <input v-model="memQ" @input="searchMem" placeholder="搜索记忆后勾选…" class="w-full mb-2 px-2 py-1 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent" />
            <div class="max-h-32 overflow-y-auto space-y-1">
              <label v-for="m in mems" :key="m.id" class="flex items-start gap-2 text-sm cursor-pointer">
                <input type="checkbox" class="mt-0.5" :checked="form.ref_memories.includes(m.id)" @change="toggle(form.ref_memories, m.id)" />
                <span class="truncate">{{ m.title }}<span class="text-xs text-gray-400 ml-1">{{ m.visibility }}</span></span>
              </label>
              <div v-if="!mems.length" class="text-xs text-gray-400">无匹配记忆</div>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-4 flex-wrap text-sm">
          <label class="flex items-center gap-2">
            <input type="checkbox" v-model="form.requires_approval" /> 需要人工审批（D36）
          </label>
          <label class="flex items-center gap-2">
            产物记忆可见性
            <select v-model="form.memory_visibility" class="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900">
              <option value="team">团队</option>
              <option value="private">仅自己</option>
              <option value="restricted">指定成员</option>
            </select>
          </label>
          <div v-if="isRestricted" class="flex items-center gap-2 flex-wrap">
            <span class="text-xs text-gray-500">可见成员（至少 1 位）：</span>
            <label v-for="m in pickableMembers" :key="m.id" class="flex items-center gap-1 text-xs">
              <input type="checkbox" :checked="form.memory_allow_members.includes(m.id)" @change="toggleAllow(m.id)" />
              {{ m.display_name }}
            </label>
            <span v-if="!pickableMembers.length" class="text-xs text-gray-400">无可选成员</span>
          </div>
          <button :disabled="busy" class="px-4 py-1.5 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50" @click="create">
            {{ busy ? '提交中…' : '提交任务' }}
          </button>
        </div>
        <p v-if="err" class="text-xs text-amber-600 dark:text-amber-400">{{ err }}</p>
      </div>

      <!-- 任务列表 -->
      <div class="flex-1 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-800">
        <button
          v-for="t in shown" :key="t.id"
          class="w-full text-left px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/60"
          :class="detail && detail.id === t.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''"
          @click="openDetail(t.id)"
        >
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs px-2 py-0.5 rounded-full" :class="STATUS_META[t.status] && STATUS_META[t.status].cls">{{ STATUS_META[t.status] ? STATUS_META[t.status].label : t.status }}</span>
            <span class="font-medium text-sm truncate">{{ t.title }}</span>
            <span class="text-xs text-gray-400 ml-auto">{{ t.agent_id }}</span>
          </div>
          <div class="mt-1 text-xs text-gray-500 truncate">
            {{ t.result_summary || t.error || t.description }}
          </div>
          <div v-if="t.meta && t.meta.approval_forced_by && t.meta.approval_forced_by.length" class="mt-1 text-xs text-amber-600 dark:text-amber-400">
            需人工审批（D36 命中：{{ t.meta.approval_forced_by.join('、') }}）
          </div>
        </button>
        <div v-if="!shown.length" class="p-8 text-center text-sm text-gray-400">暂无任务</div>
      </div>
    </div>

    <!-- 详情区 -->
    <div v-if="detail" class="w-[26rem] border-l border-gray-200 dark:border-gray-700 flex flex-col min-h-0">
      <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2">
        <span class="font-semibold text-sm truncate">{{ detail.title }}</span>
        <button class="ml-auto text-xs text-gray-400 hover:text-gray-600" @click="detail = null">关闭</button>
      </div>
      <div class="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-xs px-2 py-0.5 rounded-full" :class="STATUS_META[detail.status] && STATUS_META[detail.status].cls">{{ STATUS_META[detail.status] ? STATUS_META[detail.status].label : detail.status }}</span>
          <span class="text-xs text-gray-400">Agent: {{ detail.agent_id }}</span>
          <span v-if="detail.queue_ahead" class="text-xs text-amber-600">前面还有 {{ detail.queue_ahead }} 人</span>
        </div>
        <p class="whitespace-pre-wrap text-gray-700 dark:text-gray-300">{{ detail.description }}</p>

        <div v-if="detail.meta && detail.meta.delivery_status" class="text-xs rounded-lg p-2 bg-gray-100 dark:bg-gray-800">
          交付状态：{{ detail.meta.delivery_status.verdict }}
          <span class="text-gray-400">（{{ detail.meta.delivery_status.source }}）</span>
          <div v-if="detail.meta.zhiban_review" class="mt-1 text-gray-500">
            执班复核：{{ detail.meta.zhiban_review.verdict === 'pass' ? '通过' : '不通过' }} —— {{ detail.meta.zhiban_review.reason }}
          </div>
        </div>

        <div v-if="detail.result_summary" class="rounded-lg p-3 bg-green-50 dark:bg-green-900/20">
          <div class="text-xs font-medium mb-1">执行结果</div>
          <div class="whitespace-pre-wrap text-xs">{{ detail.result_summary }}</div>
        </div>
        <div v-if="detail.error" class="rounded-lg p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-xs whitespace-pre-wrap">
          {{ detail.error }}
        </div>

        <div v-if="canDecide" class="rounded-lg border border-amber-300 dark:border-amber-700 p-3 space-y-2">
          <div class="text-sm font-medium text-amber-700 dark:text-amber-400">待人审（D36）</div>
          <textarea v-model="note" rows="2" placeholder="审批意见 *（modify 时作为修正记录注入下一轮）" class="w-full px-2 py-1 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent"></textarea>
          <div class="flex gap-2">
            <button :disabled="busy" class="flex-1 px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm disabled:opacity-50" @click="decide('approve')">批准</button>
            <button :disabled="busy" class="flex-1 px-3 py-1.5 rounded-lg bg-amber-600 text-white text-sm disabled:opacity-50" @click="decide('modify')">修改后重跑</button>
            <button :disabled="busy" class="flex-1 px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm disabled:opacity-50" @click="decide('reject')">驳回</button>
          </div>
        </div>

        <div v-if="detail.corrections && detail.corrections.length" class="space-y-2">
          <div class="text-xs font-medium text-gray-500">修正记录</div>
          <div v-for="c in detail.corrections" :key="c.id" class="text-xs rounded p-2 bg-gray-100 dark:bg-gray-800">
            <span class="font-medium">{{ c.action }}</span> · {{ c.note }}
          </div>
        </div>

        <div v-if="detail.outputs && detail.outputs.length" class="space-y-2">
          <div class="text-xs font-medium text-gray-500">产物</div>
          <div v-for="o in detail.outputs" :key="o.id" class="flex items-center gap-2 text-xs rounded p-2 bg-gray-100 dark:bg-gray-800">
            <span class="truncate flex-1">{{ o.file_name }}</span>
            <span class="text-gray-400">{{ fmtSize(o.file_size) }}</span>
            <button class="text-blue-600 hover:underline" @click="doPreview(detail, o)">预览</button>
            <a class="text-blue-600 hover:underline" :href="dlUrl(detail, o)">下载</a>
            <button class="text-blue-600 hover:underline" @click="openShareConv(detail, o)">分享到会话</button>
            <button class="text-blue-600 hover:underline" @click="share(detail, o)">存资料库</button>
          </div>
        </div>
          <div v-if="shareOut" class="rounded-lg border border-blue-200 dark:border-blue-800 p-2 space-y-2">
            <div class="text-xs font-medium text-gray-500">分享「{{ shareOut.o.file_name }}」到会话</div>
            <div v-if="shareConvs.length" class="flex flex-wrap gap-2">
              <button v-for="c in shareConvs" :key="c.id" class="px-2 py-1 rounded border border-gray-300 dark:border-gray-600 text-xs hover:bg-gray-100 dark:hover:bg-gray-700" @click="doShareConv(c.id)">{{ convLabel(c) }}</button>
            </div>
            <div v-else class="text-xs text-gray-400">暂无可分享的会话</div>
            <div class="flex items-center gap-2">
              <button class="text-xs text-gray-500 hover:underline" @click="shareOut = null">关闭</button>
              <span v-if="shareMsg" class="text-xs text-blue-600">{{ shareMsg }}</span>
            </div>
          </div>
      </div>
      <div class="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex gap-2 items-center">
        <button
          v-if="detail.status === 'queued' || detail.status === 'running' || detail.status === 'waiting_approval'"
          class="px-3 py-1.5 rounded-lg border border-red-300 text-red-600 text-sm hover:bg-red-50 dark:hover:bg-red-900/20"
          @click="cancelTask(detail)"
        >取消任务</button>
        <span v-if="err" class="text-xs text-amber-600">{{ err }}</span>
      </div>
    </div>

    <!-- 产物预览 -->
    <div v-if="preview" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="preview = null">
      <div class="bg-white dark:bg-gray-900 rounded-xl max-w-3xl w-[90%] max-h-[80vh] flex flex-col">
        <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center">
          <span class="text-sm font-medium truncate">{{ preview.name }}</span>
          <button class="ml-auto text-xs text-gray-400" @click="preview = null">关闭</button>
        </div>
        <pre class="p-4 overflow-auto text-xs whitespace-pre-wrap">{{ preview.text }}</pre>
      </div>
    </div>
  </div>
</template>
