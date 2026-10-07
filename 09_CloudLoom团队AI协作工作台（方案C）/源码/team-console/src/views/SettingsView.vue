<script setup lang="ts">
// 设置 Tab（SPEC 阶段5）：个人信息 · 通知开关（PUT /api/me 持久化）· 退出登录 · Agent 工坊（管理员，D5/D16/D22）
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'
import { notifyState, enableNotifications, sendTestNotification, lastPollAt, notifyList, clearNotify } from '../lib/notify'

interface Agent {
  id: string; name: string; description: string; preset: boolean; enabled: boolean
  port: number; status: { running?: boolean; port?: number } | null
  avatar?: string | null   // S4.0 / B4：Agent 头像；为空时前端回退占位图 public/avatar-placeholder.png
}
const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.user?.role === 'admin')

const displayName = ref('')
const profileMsg = ref('')
const profileErr = ref('')
const savingProfile = ref(false)
const notifyMsg = ref('')
const busy = ref(false)

const agents = ref<Agent[]>([])
const agentsErr = ref('')
const agentsMsg = ref('')
const createOpen = ref(false)
const createBusy = ref(false)
const createErr = ref('')
const form = ref({ id: '', name: '', description: '', soul: '' })
const editOpen = ref(false)
const editBusy = ref(false)
const editErr = ref('')
const edit = ref({ id: '', name: '', description: '', enabled: true, soul: '' })

async function saveProfile() {
  savingProfile.value = true; profileMsg.value = ''; profileErr.value = ''
  try {
    const r = await api<{ user: { display_name: string } }>('/me', {
      method: 'PUT', body: JSON.stringify({ display_name: displayName.value }),
    })
    if (auth.user) auth.user.display_name = r.user.display_name
    profileMsg.value = '已保存'
  } catch (e) { profileErr.value = (e as Error).message } finally { savingProfile.value = false }
}
async function toggleNotify() {
  if (!auth.user) return
  const next = !auth.user.notify_enabled
  busy.value = true; notifyMsg.value = ''
  try {
    const r = await api<{ user: { notify_enabled: boolean } }>('/me', {
      method: 'PUT', body: JSON.stringify({ notify_enabled: next }),
    })
    auth.user.notify_enabled = r.user.notify_enabled
    notifyMsg.value = next ? '桌面通知已开启' : '桌面通知已关闭（仅站内提醒）'
  } catch (e) { notifyMsg.value = (e as Error).message } finally { busy.value = false }
}
async function requestPerm() {
  const r = await enableNotifications()
  notifyMsg.value = r === 'granted' ? '浏览器通知权限已授予，点「发送测试通知」验证'
    : r === 'denied' ? '权限被拒绝，可在浏览器地址栏站点设置里重新允许'
    : r === 'unsupported' ? '当前浏览器不支持 Notification（iOS 需先「添加到主屏幕」后用 Safari 打开）'
    : '未授予权限'
}
function testNotify() { sendTestNotification() }
async function logout() { await auth.logout(); router.push({ name: 'login' }) }

async function loadAgents() {
  try {
    const r = await api<{ agents: Agent[] }>('/agents')
    agents.value = r.agents || []
    agentsErr.value = ''
  } catch (e) { agentsErr.value = (e as Error).message }
}
async function createAgent() {
  createErr.value = ''; agentsMsg.value = ''
  if (!form.value.id.trim() || !form.value.name.trim()) { createErr.value = 'id 与显示名必填'; return }
  createBusy.value = true
  try {
    await api('/agents', { method: 'POST', body: JSON.stringify(form.value) })
    createOpen.value = false
    agentsMsg.value = 'Agent 已创建（已装 systemd 托管，首次使用自动唤醒，D5）'
    form.value = { id: '', name: '', description: '', soul: '' }
    await loadAgents()
  } catch (e) { createErr.value = (e as Error).message } finally { createBusy.value = false }
}
function openEdit(a: Agent) {
  editErr.value = ''
  edit.value = { id: a.id, name: a.name, description: a.description, enabled: a.enabled, soul: '' }
  editOpen.value = true
}
async function saveEdit() {
  editErr.value = ''; agentsMsg.value = ''
  editBusy.value = true
  try {
    const body: Record<string, unknown> = { name: edit.value.name, description: edit.value.description, enabled: edit.value.enabled }
    if (edit.value.soul.trim()) body.soul = edit.value.soul
    await api('/agents/' + edit.value.id, { method: 'PUT', body: JSON.stringify(body) })
    editOpen.value = false
    agentsMsg.value = '已保存：' + edit.value.id
    await loadAgents()
  } catch (e) { editErr.value = (e as Error).message } finally { editBusy.value = false }
}
async function toggleEnabled(a: Agent) {
  agentsErr.value = ''; agentsMsg.value = ''
  try {
    await api('/agents/' + a.id, { method: 'PUT', body: JSON.stringify({ enabled: !a.enabled }) })
    agentsMsg.value = (a.enabled ? '已停用：' : '已启用：') + a.id
    await loadAgents()
  } catch (e) { agentsErr.value = (e as Error).message }
}
async function delAgent(a: Agent) {
  if (!window.confirm('确认删除 Agent「' + a.name + '（' + a.id + '）」？将卸载其 systemd 单元并删除 Hermes profile，不可恢复。')) return
  agentsErr.value = ''; agentsMsg.value = ''
  try { await api('/agents/' + a.id, { method: 'DELETE' }); agentsMsg.value = '已删除：' + a.id; await loadAgents() }
  catch (e) { agentsErr.value = (e as Error).message }
}
function running(a: Agent) { return !!(a.status && a.status.running) }
interface Member { id: string; username: string; display_name: string; role: string; status: string }
const members = ref<Member[]>([])
const memberMsg = ref("")
const memberErr = ref("")
const statusLabel = (st: string) => (st === "active" ? "已启用" : st === "pending" ? "待批准" : "已停用")
const statusClass = (st: string) => (st === "active" ? "bg-green-100 text-green-700" : st === "pending" ? "bg-amber-100 text-amber-700" : "bg-gray-200 text-gray-600")
const isAdminRole = (r: string) => r === "admin"
const canApprove = (m: Member) => m.status !== "active"
const canDisable = (m: Member) => m.status === "active" && m.id !== (auth.user ? auth.user.id : "")
async function loadMembers() {
  memberErr.value = ""
  try {
    const r = await api<{ members: Member[] }>("/members")
    members.value = r.members
  } catch (e: any) { memberErr.value = "成员列表读取失败：" + e.message }
}
async function approveMember(id: string) {
  memberMsg.value = ""; memberErr.value = ""
  try {
    await api("/members/" + id + "/approve", { method: "POST", body: "{}" })
    memberMsg.value = "已批准并启用"
    await loadMembers()
  } catch (e: any) { memberErr.value = "操作失败：" + e.message }
}
async function disableMember(id: string) {
  memberMsg.value = ""; memberErr.value = ""
  try {
    await api("/members/" + id + "/disable", { method: "POST", body: "{}" })
    memberMsg.value = "已停用"
    await loadMembers()
  } catch (e: any) { memberErr.value = "操作失败：" + e.message }
}
onMounted(() => { if (auth.user) displayName.value = auth.user.display_name; loadAgents(); if (auth.user?.role === "admin") loadMembers() })
</script>

<template>
  <div class="h-full overflow-auto p-4">
    <div class="grid gap-4 md:grid-cols-2">
      <section class="border rounded-lg bg-white dark:bg-gray-800 p-4">
        <h2 class="font-medium mb-3">个人信息</h2>
        <div class="flex items-center gap-3 mb-3">
          <div class="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-lg">
            {{ (auth.user && auth.user.display_name ? auth.user.display_name : '?').slice(0, 1) }}
          </div>
          <div class="text-sm">
            <div class="font-medium">{{ auth.user && auth.user.display_name }}</div>
            <div class="text-xs text-gray-400">{{ auth.user && auth.user.username }} ·
              {{ auth.user && auth.user.role === 'admin' ? '管理员' : '成员' }}</div>
          </div>
        </div>
        <label class="block text-xs text-gray-500 mb-1">显示名</label>
        <div class="flex gap-2">
          <input v-model="displayName" class="flex-1 border rounded px-2 py-1 bg-white dark:bg-gray-900" />
          <button class="text-sm px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50"
            :disabled="savingProfile" @click="saveProfile">保存</button>
        </div>
        <p v-if="profileMsg" class="text-xs text-green-600 mt-2">{{ profileMsg }}</p>
        <p v-if="profileErr" class="text-xs text-red-500 mt-2">{{ profileErr }}</p>
      </section>

      <section class="border rounded-lg bg-white dark:bg-gray-800 p-4">
        <h2 class="font-medium mb-3">通知</h2>
        <div class="flex items-center gap-3">
          <button class="text-sm px-3 py-1 rounded border disabled:opacity-50" :disabled="busy" @click="toggleNotify">
            {{ auth.user && auth.user.notify_enabled ? '已开启 · 点击关闭' : '已关闭 · 点击开启' }}
          </button>
          <span class="text-xs text-gray-400">服务端持久化（users.notify_enabled）</span>
        </div>
        <div class="text-xs text-gray-500 mt-3">
          浏览器权限：<span class="font-mono">{{ notifyState.permission }}</span>
          <button class="text-blue-600 ml-2" @click="requestPerm">申请/检查权限</button>
          <button class="text-blue-600 ml-2" @click="testNotify">发送测试通知</button>
        </div>
        <p class="text-xs text-gray-400 mt-2">
          {{ notifyState.pollMs / 1000 }}s 轮询 /api/poll（D19）· 最近轮询：{{ lastPollAt || '—' }} ·
          未读站内提醒：{{ notifyList.length }}
          <button class="text-blue-600 ml-1" @click="clearNotify">清空</button>
        </p>
        <p class="text-xs text-gray-400 mt-2">
          iOS 需「添加到主屏幕」后从主屏图标打开，通知权限才可用（PWA，D19）。
        </p>
        <p v-if="notifyMsg" class="text-xs text-blue-600 mt-2">{{ notifyMsg }}</p>
      </section>
    </div>

    <section v-if="isAdmin" class="border rounded-lg bg-white dark:bg-gray-800 p-4 mt-4">
      <div class="flex items-center gap-3 flex-wrap mb-3">
        <h2 class="font-medium">成员管理</h2>
        <span class="text-xs text-gray-400">首个注册者为管理员，后续注册需批准后方可使用</span>
        <button class="text-xs px-2 py-1 rounded border hover:bg-gray-50 dark:hover:bg-gray-700 ml-auto" @click="loadMembers">刷新</button>
      </div>
      <div v-if="members.length" class="space-y-2">
        <div v-for="m in members" :key="m.id" class="flex items-center gap-2 text-xs rounded p-2 bg-gray-100 dark:bg-gray-700">
          <span class="font-medium">{{ m.display_name }}</span>
          <span class="text-gray-400">{{ m.username }}</span>
          <span v-if="isAdminRole(m.role)" class="text-blue-600">管理员</span>
          <span class="px-1.5 py-0.5 rounded" :class="statusClass(m.status)">{{ statusLabel(m.status) }}</span>
          <span class="ml-auto flex gap-3">
            <button v-if="canApprove(m)" class="text-blue-600 hover:underline" @click="approveMember(m.id)">批准/启用</button>
            <button v-if="canDisable(m)" class="text-red-600 hover:underline" @click="disableMember(m.id)">停用</button>
          </span>
        </div>
      </div>
      <p v-else class="text-xs text-gray-400">暂无成员</p>
      <p v-if="memberMsg" class="text-xs text-blue-600 mt-2">{{ memberMsg }}</p>
      <p v-if="memberErr" class="text-xs text-amber-600 mt-2">{{ memberErr }}</p>
    </section>

    <section class="border rounded-lg bg-white dark:bg-gray-800 p-4 mt-4">
      <div class="flex items-center gap-3 flex-wrap mb-3">
        <h2 class="font-medium">Agent 工坊</h2>
        <span class="text-xs text-gray-400">{{ agents.length }} 个 Agent · 懒启动 8650-8999（D5）</span>
        <template v-if="isAdmin">
          <button class="text-xs px-3 py-1.5 rounded bg-blue-600 text-white ml-auto" @click="createOpen = true">新建 Agent</button>
        </template>
        <span v-else class="text-xs text-amber-600 ml-auto">仅管理员可新建/编辑/停用</span>
        <button class="text-xs px-2 py-1 rounded border hover:bg-gray-50 dark:hover:bg-gray-700" @click="loadAgents">刷新</button>
      </div>
      <p v-if="agentsErr" class="text-xs text-red-500 mb-2">{{ agentsErr }}</p>
      <p v-if="agentsMsg" class="text-xs text-green-600 mb-2">{{ agentsMsg }}</p>
      <div class="grid gap-3 md:grid-cols-2">
        <article v-for="a in agents" :key="a.id" class="border rounded-md p-3">
          <div class="flex items-center gap-2">
            <img class="w-8 h-8 rounded-full object-cover shrink-0 border border-gray-200 dark:border-gray-600"
                 :src="a.avatar || '/avatar-placeholder.png'" :alt="a.name" />
            <span class="w-2 h-2 rounded-full" :class="running(a) ? 'bg-green-500' : 'bg-gray-300'"></span>
            <span class="text-sm font-medium">{{ a.name }}</span>
            <span class="text-xs text-gray-400 font-mono">{{ a.id }}</span>
            <span v-if="a.preset" class="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">预设</span>
            <span v-if="!a.enabled" class="text-[11px] px-1.5 py-0.5 rounded bg-red-50 text-red-500">已停用</span>
          </div>
          <p class="text-xs text-gray-500 mt-1 break-words">{{ a.description || '（无描述）' }}</p>
          <div class="text-[11px] text-gray-400 mt-2">
            端口 {{ a.port }} · {{ running(a) ? '运行中' : '休眠中（首次使用自动唤醒）' }}
          </div>
          <div v-if="isAdmin" class="flex gap-2 mt-2">
            <button class="text-xs text-blue-600" @click="openEdit(a)">编辑</button>
            <button class="text-xs" :class="a.enabled ? 'text-amber-600' : 'text-green-600'" @click="toggleEnabled(a)">
              {{ a.enabled ? '停用' : '启用' }}
            </button>
            <button v-if="!a.preset" class="text-xs text-red-500" @click="delAgent(a)">删除</button>
          </div>
        </article>
      </div>
    </section>

    <section class="border rounded-lg bg-white dark:bg-gray-800 p-4 mt-4">
      <h2 class="font-medium mb-2">会话</h2>
      <button class="text-sm px-3 py-1.5 rounded border text-red-600" @click="logout">退出登录</button>
      <p class="text-xs text-gray-400 mt-2">退出将清除 httpOnly Cookie 会话（JWT 7 天有效，重新登录即刷新）。</p>
    </section>

    <div v-if="createOpen" class="fixed inset-0 z-30 bg-black/40 flex items-center justify-center p-4" @click.self="createOpen = false">
      <div class="bg-white dark:bg-gray-800 rounded-lg w-full max-w-lg p-5 max-h-[85vh] overflow-auto">
        <h3 class="font-medium mb-3">新建 Agent</h3>
        <label class="block text-xs text-gray-500 mb-1">id（小写字母开头的拼音/字母数字，2-32 位，D22）</label>
        <input v-model="form.id" placeholder="例如 meishu" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900" />
        <label class="block text-xs text-gray-500 mb-1">显示名</label>
        <input v-model="form.name" placeholder="例如 美术 Agent" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900" />
        <label class="block text-xs text-gray-500 mb-1">职责描述</label>
        <input v-model="form.description" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900" />
        <label class="block text-xs text-gray-500 mb-1">SOUL.md（留空则用默认模板，含【行为边界】/可自主/需升级人审）</label>
        <textarea v-model="form.soul" rows="5" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900"></textarea>
        <p class="text-xs text-gray-400 mb-2">创建过程：hermes profile create --clone-from cehua → 写 .env 端口与密钥 → 覆盖 SOUL.md → 装 systemd（不启动）。约需 1-2 分钟。</p>
        <p v-if="createErr" class="text-xs text-red-500 mb-2">{{ createErr }}</p>
        <div class="flex justify-end gap-2">
          <button class="text-sm px-3 py-1.5 rounded border" @click="createOpen = false">取消</button>
          <button class="text-sm px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-50"
            :disabled="createBusy" @click="createAgent">{{ createBusy ? '创建中…' : '创建' }}</button>
        </div>
      </div>
    </div>

    <div v-if="editOpen" class="fixed inset-0 z-30 bg-black/40 flex items-center justify-center p-4" @click.self="editOpen = false">
      <div class="bg-white dark:bg-gray-800 rounded-lg w-full max-w-lg p-5 max-h-[85vh] overflow-auto">
        <h3 class="font-medium mb-3">编辑 Agent · {{ edit.id }}</h3>
        <label class="block text-xs text-gray-500 mb-1">显示名</label>
        <input v-model="edit.name" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900" />
        <label class="block text-xs text-gray-500 mb-1">职责描述</label>
        <input v-model="edit.description" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900" />
        <label class="flex items-center gap-2 text-sm mb-3">
          <input type="checkbox" v-model="edit.enabled" /> 启用（停用会停掉其 gateway；启用不主动拉起，保持懒启动语义）
        </label>
        <label class="block text-xs text-gray-500 mb-1">SOUL.md（留空则不修改；须含【行为边界】才生效）</label>
        <textarea v-model="edit.soul" rows="6" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900"></textarea>
        <p v-if="editErr" class="text-xs text-red-500 mb-2">{{ editErr }}</p>
        <div class="flex justify-end gap-2">
          <button class="text-sm px-3 py-1.5 rounded border" @click="editOpen = false">取消</button>
          <button class="text-sm px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-50"
            :disabled="editBusy" @click="saveEdit">{{ editBusy ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
