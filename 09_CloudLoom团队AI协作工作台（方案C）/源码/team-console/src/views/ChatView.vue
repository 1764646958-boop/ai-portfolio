<script setup lang="ts">
// 聊天流：①会话模式（服务端持久化 + @Agent 异步拉入 + 增量轮询）②Agent 直聊模式（SSE 流式 + 懒启动提示）
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { chatStream } from '../api'
import { useChatStore, type Msg } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
import { idbLoad, idbSave } from '../lib/idb'
import ChatStream from '../components/ChatStream.vue'

const chat = useChatStore()
const agentMsgs = ref<Msg[]>([])
const status = ref('')
const streaming = ref(false)
let timer: number | undefined

const streamRef = ref<InstanceType<typeof ChatStream> | null>(null)
// C-13 修复（S3.1）：记住用户上次打开的会话，避免每次挂载都跳到「最近更新」会话
//（会话顺序随任意成员发言漂移，曾导致消息误发到群聊）
// S4.0 / B6-③：会话记忆**按用户区分**。原键 'cloudloom:lastConvId' 是全局的 —— 同一浏览器上
// A 退出、B 登录后，B 会继承 A 的"上次会话"并直接跳进去（越权观感，且容易把消息发错会话）。
// 新键 cloudloom:<user_id>:lastConvId。旧全局键不再读取（无法判定它属于谁，读了就有串号风险），
// 仅做一次清理；副作用：升级后首次进入聊天会回退到「最近更新」会话（一次性）。
const LAST_CONV_KEY_LEGACY = 'cloudloom:lastConvId'
try { localStorage.removeItem(LAST_CONV_KEY_LEGACY) } catch { /* 存储被禁用时忽略 */ }
function convKey(): string {
  const uid = useAuthStore().user?.id || 'anon'
  return `cloudloom:${uid}:lastConvId`
}
function rememberConv(id: string) {
  try { localStorage.setItem(convKey(), id) } catch { /* 存储被禁用时忽略 */ }
}
function recallConv(): string {
  try { return localStorage.getItem(convKey()) || '' } catch { return '' }
}
// 目标会话：上次打开且仍在有权列表中（已无权则自然回退）→ 否则回退「最近更新」会话
function pickConvId(): string {
  const last = recallConv()
  if (last && chat.convs.some((c) => c.id === last)) return last
  return chat.convs.length ? chat.convs[0].id : ''
}
// 进入会话后滚动到底部（ChatStream 已 expose scrollToEnd）
async function openConvAndScroll(id: string) {
  if (!id) return
  await chat.open(id)
  await streamRef.value?.scrollToEnd()
}

const activeAgent = computed(() => chat.agents.find((a) => a.id === chat.agentId) || null)
const isAgentMode = computed(() => chat.mode === 'agent')
const headerTitle = computed(() =>
  isAgentMode.value
    ? `${activeAgent.value?.name || chat.agentId}（Agent 直聊）`
    : chat.activeConvObj?.title || '团队交流',
)

async function loadAgentHistory() {
  const id = chat.agentId
  if (!id) { agentMsgs.value = []; return }
  agentMsgs.value = await idbLoad<Msg>('agent:' + id)
  status.value = ''
  streaming.value = false
}

async function sendToAgent(text: string) {
  const id = chat.agentId
  if (!text.trim() || streaming.value || !id) return
  const now = new Date().toISOString()
  agentMsgs.value.push({
    id: 'u-' + Date.now(), sender_id: '', sender_type: 'member', sender_name: '我',
    content: text, type: 'text', created_at: now,
  })
  const replyId = 'a-' + Date.now()
  agentMsgs.value.push({
    id: replyId, sender_id: id, sender_type: 'agent',
    sender_name: activeAgent.value?.name || id, content: '', type: 'text', created_at: now, pending: true,
  })
  streaming.value = true
  status.value = ''
  // M1：每次请求携带完整会话历史（不含正在生成的占位）
  const history = agentMsgs.value
    .filter((m) => !m.pending && m.content)
    .map((m) => ({ role: m.sender_type === 'member' ? 'user' : 'assistant', content: m.content }))
  await chatStream({ agent: id, messages: history }, {
    onStatus: (s) => { status.value = s.message },
    onDelta: (d) => {
      const m = agentMsgs.value.find((x) => x.id === replyId)
      if (m) m.content += d
    },
    onError: (e) => {
      const m = agentMsgs.value.find((x) => x.id === replyId)
      if (m) { m.content = `⚠️ ${e}`; m.pending = false }
      status.value = ''
    },
    onDone: () => {
      streaming.value = false
      status.value = ''
      const m = agentMsgs.value.find((x) => x.id === replyId)
      if (m) m.pending = false
      idbSave('agent:' + id, agentMsgs.value)
      chat.loadAgents().catch(() => {})
    },
  })
}

async function onSend(p: { text: string; files: File[] }) {
  if (isAgentMode.value) {
    if (p.files.length) chat.error = 'Agent 直聊暂不支持附件，请在会话中上传'
    await sendToAgent(p.text)
  } else {
    await chat.send(p.text, 'text', p.files)
  }
}

// 4s 轮询：会话未读红点 + 当前会话增量（D19 前端 3-5s 轮询）
async function tick() {
  try {
    await chat.loadConvs()
    if (!isAgentMode.value && chat.activeConv) await chat.pull()
  } catch { /* 网络抖动忽略，下轮重试 */ }
}

onMounted(async () => {
  await Promise.all([chat.loadAgents(), chat.loadConvs()])
  if (chat.mode === 'agent') await loadAgentHistory()
  else if (!chat.activeConv) await openConvAndScroll(pickConvId())
  timer = window.setInterval(tick, 4000)
})
onUnmounted(() => { if (timer) window.clearInterval(timer) })
watch(() => chat.activeConv, (id) => { if (id) rememberConv(id) })
watch(() => chat.agentId, async () => { if (chat.mode === 'agent') await loadAgentHistory() })
watch(() => chat.mode, async (m) => { if (m === 'agent') await loadAgentHistory() })
</script>

<template>
  <div class="h-full flex flex-col min-h-0">
    <div class="h-11 shrink-0 flex items-center gap-2 px-4 border-b bg-white dark:bg-gray-800">
      <span class="text-sm font-medium truncate">{{ headerTitle }}</span>
      <span v-if="isAgentMode" class="text-xs px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 dark:bg-purple-900/40">SSE 直连</span>
      <span v-if="isAgentMode && activeAgent" class="text-xs text-gray-400">
        {{ activeAgent.status?.running ? '已就绪' : '休眠中（发送即唤醒）' }} · 端口 {{ activeAgent.port }}
      </span>
      <div class="flex-1"></div>
      <span v-if="!isAgentMode && chat.activeConvObj" class="text-xs text-gray-400">
        {{ chat.activeConvObj.members.length }} 人
      </span>
      <button v-if="isAgentMode" class="text-xs text-blue-600 hover:underline"
        @click="chat.mode = 'conv'">← 返回会话</button>
    </div>

    <div v-if="chat.error" class="shrink-0 px-4 py-2 text-xs text-red-600 bg-red-50 dark:bg-red-900/20">
      {{ chat.error }}
      <button class="ml-2 underline" @click="chat.error = ''">关闭</button>
    </div>

    <ChatStream
      ref="streamRef"
      class="flex-1 min-h-0"
      :messages="isAgentMode ? agentMsgs : chat.messages"
      :agents="chat.agents"
      :streaming="isAgentMode ? streaming : false"
      :status="isAgentMode ? status : ''"
      :disabled="isAgentMode && streaming"
      @send="onSend"
      @recall="(id: string) => chat.recall(id)"
    />
  </div>
</template>
