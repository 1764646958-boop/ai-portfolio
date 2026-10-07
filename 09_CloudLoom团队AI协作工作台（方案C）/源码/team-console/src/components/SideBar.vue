<script setup lang="ts">
// 左栏：团队交流（会话区 + 未读红点 + 新建会话）+ 团队 Agent 区（运行状态点）
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useChatStore } from '../stores/chat'

interface Member { id: string; username: string; display_name: string; role: string; status: string }

const emit = defineEmits<{ picked: [] }>()
const chat = useChatStore()
const router = useRouter()
const members = ref<Member[]>([])
const showNew = ref(false)
const pickedIds = ref<string[]>([])
const newTitle = ref('')
const err = ref('')
const busy = ref(false)
let timer: number | undefined

async function loadMembers() {
  try { members.value = (await api<{ members: Member[] }>('/members')).members }
  catch (e: any) { err.value = e.message }
}
function openNew() { showNew.value = true; err.value = ''; pickedIds.value = []; newTitle.value = ''; loadMembers() }
function toggle(id: string) {
  const i = pickedIds.value.indexOf(id)
  if (i >= 0) pickedIds.value.splice(i, 1); else pickedIds.value.push(id)
}
async function create() {
  if (!pickedIds.value.length) { err.value = '请至少选择 1 位成员'; return }
  busy.value = true
  try {
    await chat.createConv(pickedIds.value.length > 1 ? 'group' : 'dm', pickedIds.value, newTitle.value.trim() || undefined)
    showNew.value = false
    go()
  } catch (e: any) { err.value = e.message } finally { busy.value = false }
}
async function openConv(id: string) { await chat.open(id); go() }
function openAgent(id: string) { chat.openAgent(id); go() }
function go() { if (router.currentRoute.value.name !== 'chat') router.push({ name: 'chat' }); emit('picked') }

onMounted(async () => {
  await Promise.all([chat.loadConvs().catch(() => {}), chat.loadAgents().catch(() => {})])
  timer = window.setInterval(() => chat.loadConvs().catch(() => {}), 8000)
})
onUnmounted(() => { if (timer) window.clearInterval(timer) })
</script>

<template>
  <div class="flex flex-col gap-4 min-h-0 h-full">
    <div class="flex flex-col min-h-0">
      <div class="flex items-center mb-2">
        <div class="text-xs font-semibold text-gray-400">团队交流</div>
        <button class="ml-auto text-xs text-blue-600 hover:underline" @click="openNew">+ 新建</button>
      </div>
      <div class="flex flex-col gap-0.5 overflow-y-auto">
        <button
          v-for="c in chat.convs" :key="c.id"
          class="text-left px-2 py-1.5 rounded-md border-l-2 border-transparent hover:bg-gray-100 dark:hover:bg-gray-700"
          :class="chat.mode === 'conv' && chat.activeConv === c.id ? 'bg-blue-100 dark:bg-gray-600 border-blue-500 font-medium' : ''"
          @click="openConv(c.id)"
        >
          <div class="flex items-center gap-2">
            <span class="text-sm truncate">{{ c.title || c.id }}</span>
            <span v-if="c.type === 'group'" class="text-xs text-gray-400">群</span>
            <span v-if="c.unread" class="ml-auto shrink-0 text-xs px-1.5 rounded-full bg-red-500 text-white">{{ c.unread > 99 ? '99+' : c.unread }}</span>
          </div>
          <div class="text-xs text-gray-400 truncate">
            {{ c.last_message ? c.last_message.sender_name + '：' + c.last_message.content : '暂无消息' }}
          </div>
        </button>
        <div v-if="!chat.convs.length" class="text-xs text-gray-400 px-2 py-1">暂无会话，点「+ 新建」开始</div>
      </div>
    </div>

    <div class="flex flex-col min-h-0">
      <div class="text-xs font-semibold text-gray-400 mb-2">
        团队 Agent（{{ chat.runningAgents.length }} 就绪 / {{ chat.agents.length }}）
      </div>
      <div class="flex flex-col gap-0.5 overflow-y-auto">
        <button
          v-for="a in chat.agents" :key="a.id"
          class="text-left px-2 py-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
          :class="chat.mode === 'agent' && chat.agentId === a.id ? 'bg-blue-50 dark:bg-gray-700' : ''"
          @click="openAgent(a.id)"
        >
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full shrink-0" :class="a.status && a.status.running ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'"></span>
            <span class="text-sm truncate">{{ a.name }}</span>
            <span class="ml-auto text-xs text-gray-400 shrink-0">:{{ a.port }}</span>
          </div>
          <div class="text-xs text-gray-400 truncate">
            {{ a.status && a.status.running ? '已就绪' : '休眠中（首次使用自动唤醒）' }}
          </div>
        </button>
        <div v-if="!chat.agents.length" class="text-xs text-gray-400 px-2 py-1">未获取到 Agent</div>
      </div>
    </div>
  </div>

  <div v-if="showNew" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="showNew = false">
    <div class="bg-white dark:bg-gray-900 rounded-xl w-80 p-4 space-y-3">
      <div class="font-semibold text-sm">新建会话</div>
      <input v-model="newTitle" placeholder="群名称（可选）" class="w-full px-2 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent" />
      <div class="max-h-56 overflow-y-auto space-y-1">
        <label v-for="u in members" :key="u.id" class="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" :checked="pickedIds.includes(u.id)" @change="toggle(u.id)" />
          <span>{{ u.display_name || u.username }}</span>
          <span class="text-xs text-gray-400">{{ u.username }}</span>
        </label>
        <div v-if="!members.length" class="text-xs text-gray-400">未获取到成员</div>
      </div>
      <p v-if="err" class="text-xs text-red-600">{{ err }}</p>
      <div class="flex gap-2">
        <button class="flex-1 px-3 py-1.5 rounded-lg border text-sm" @click="showNew = false">取消</button>
        <button :disabled="busy" class="flex-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm disabled:opacity-50" @click="create">
          {{ busy ? '创建中…' : '创建' }}
        </button>
      </div>
    </div>
  </div>
</template>
