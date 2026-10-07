<script setup lang="ts">
// 记忆 Tab：搜索（D24 索引检索）、新建/编辑/删除、ACL 可见性徽标（D25）
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

interface Mem {
  id: string; type: string; title: string; content: string; tags: string[]
  author: string; visibility: string; allow_members: string[]
  source_task_id: string | null; source_agent: string | null; created_at: string
}
interface Member { id: string; username: string; display_name: string; role: string }

const auth = useAuthStore()
const list = ref<Mem[]>([])
const members = ref<Member[]>([])
const q = ref('')
const fType = ref('')
const fVis = ref('')
const err = ref('')
const msg = ref('')
const busy = ref(false)
const showForm = ref(false)
const editingId = ref<string | null>(null)

const TYPE_LABEL: Record<string, string> = { decision: '决策', preference: '偏好', fact: '事实', conclusion: '结论' }
const VIS_META: Record<string, { label: string; cls: string }> = {
  private: { label: '仅自己', cls: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200' },
  team: { label: '团队可见', cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
  restricted: { label: '指定成员', cls: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300' },
}
const emptyForm = () => ({
  type: 'fact', title: '', content: '', tagsText: '',
  visibility: 'team' as 'private' | 'team' | 'restricted', allow_members: [] as string[],
})
const form = ref(emptyForm())

async function search() {
  err.value = ''
  const p = new URLSearchParams()
  if (q.value.trim()) p.set('q', q.value.trim())
  if (fType.value) p.set('type', fType.value)
  if (fVis.value) p.set('visibility', fVis.value)
  p.set('limit', '100')
  try { list.value = (await api<{ memories: Mem[] }>(`/memories?${p.toString()}`)).memories }
  catch (e: any) { err.value = e.message }
}
async function loadMembers() {
  try { members.value = (await api<{ members: Member[] }>('/members')).members } catch { members.value = [] }
}
function openCreate() { editingId.value = null; form.value = emptyForm(); err.value = ''; msg.value = ''; showForm.value = true }
function openEdit(m: Mem) {
  editingId.value = m.id
  form.value = { type: m.type, title: m.title, content: m.content, tagsText: m.tags.join(','), visibility: m.visibility as any, allow_members: [...m.allow_members] }
  err.value = ''; msg.value = ''; showForm.value = true
}
function toggleMember(id: string) {
  const i = form.value.allow_members.indexOf(id)
  if (i >= 0) form.value.allow_members.splice(i, 1); else form.value.allow_members.push(id)
}
async function save() {
  err.value = ''; msg.value = ''
  if (!form.value.title.trim()) { err.value = '标题不能为空'; return }
  if (form.value.visibility === 'restricted' && !form.value.allow_members.length) { err.value = '「指定成员」需至少选择 1 位成员（服务端同样校验）'; return }
  const body: Record<string, unknown> = {
    type: form.value.type, title: form.value.title.trim(), content: form.value.content,
    tags: form.value.tagsText, visibility: form.value.visibility, allow_members: form.value.allow_members,
  }
  busy.value = true
  try {
    if (editingId.value) await api(`/memories/${editingId.value}`, { method: 'PUT', body: JSON.stringify(body) })
    else await api('/memories', { method: 'POST', body: JSON.stringify(body) })
    msg.value = editingId.value ? '已保存修改' : '已新建记忆'
    showForm.value = false
    await search()
  } catch (e: any) { err.value = e.message } finally { busy.value = false }
}
async function remove(m: Mem) {
  if (!window.confirm(`确认删除记忆「${m.title}」？该操作不可撤销。`)) return
  err.value = ''; msg.value = ''
  try {
    await api(`/memories/${m.id}`, { method: 'DELETE' })
    msg.value = '已删除'
    if (editingId.value === m.id) showForm.value = false
    await search()
  } catch (e: any) { err.value = e.message }
}
function canEdit(m: Mem) {
  const u = auth.user
  return !!u && (u.role === 'admin' || u.username === m.author)
}
function fmtTime(s: string) { return (s || '').replace('T', ' ').slice(0, 16) }

onMounted(async () => { await Promise.all([search(), loadMembers()]) })
</script>

<template>
  <div class="flex h-full min-h-0">
    <div class="flex-1 flex flex-col min-w-0">
      <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2 flex-wrap">
        <h2 class="font-semibold mr-2">团队记忆</h2>
        <input
          v-model="q" @keyup.enter="search" placeholder="搜索记忆（≥2 字中文可命中）"
          class="flex-1 min-w-40 px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-transparent"
        />
        <select v-model="fType" @change="search" class="text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-transparent px-2 py-1.5">
          <option value="">全部类型</option>
          <option v-for="(l, k) in TYPE_LABEL" :key="k" :value="k">{{ l }}</option>
        </select>
        <select v-model="fVis" @change="search" class="text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-transparent px-2 py-1.5">
          <option value="">全部可见性</option>
          <option value="private">仅自己</option>
          <option value="team">团队可见</option>
          <option value="restricted">指定成员</option>
        </select>
        <button class="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700" @click="search">搜索</button>
        <button class="px-3 py-1.5 rounded-lg border border-blue-600 text-blue-600 text-sm hover:bg-blue-50 dark:hover:bg-blue-900/20" @click="openCreate">+ 新建记忆</button>
      </div>

      <p v-if="err" class="px-4 py-2 text-xs text-red-600 bg-red-50 dark:bg-red-900/20">{{ err }}</p>
      <p v-else-if="msg" class="px-4 py-2 text-xs text-green-700 bg-green-50 dark:bg-green-900/20">{{ msg }}</p>

      <div class="flex-1 overflow-y-auto p-4 grid grid-cols-1 lg:grid-cols-2 gap-3 content-start">
        <div
          v-for="m in list" :key="m.id"
          class="rounded-xl border border-gray-200 dark:border-gray-700 p-3 flex flex-col gap-2"
          :class="editingId === m.id ? 'ring-2 ring-blue-400' : ''"
        >
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">{{ TYPE_LABEL[m.type] || m.type }}</span>
            <span class="text-xs px-2 py-0.5 rounded-full" :class="VIS_META[m.visibility] ? VIS_META[m.visibility].cls : ''">
              {{ VIS_META[m.visibility] ? VIS_META[m.visibility].label : m.visibility }}
            </span>
            <span v-if="m.source_agent" class="text-xs text-gray-400">来自任务 · {{ m.source_agent }}</span>
            <span class="ml-auto text-xs text-gray-400">{{ fmtTime(m.created_at) }}</span>
          </div>
          <div class="font-medium text-sm">{{ m.title }}</div>
          <div class="text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap line-clamp-4">{{ m.content }}</div>
          <div v-if="m.tags.length" class="flex gap-1 flex-wrap">
            <span v-for="t in m.tags" :key="t" class="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500">#{{ t }}</span>
          </div>
          <div
            v-if="m.visibility === 'restricted' && m.allow_members.length"
            class="text-xs text-purple-600 dark:text-purple-400"
          >可见成员：{{ m.allow_members.join('、') }}</div>
          <div class="flex items-center gap-3 text-xs mt-auto pt-1">
            <span class="text-gray-400">{{ m.author }}</span>
            <template v-if="canEdit(m)">
              <button class="text-blue-600 hover:underline" @click="openEdit(m)">编辑</button>
              <button class="text-red-600 hover:underline" @click="remove(m)">删除</button>
            </template>
            <span v-else class="text-gray-300 dark:text-gray-600">仅作者/管理员可改</span>
          </div>
        </div>
        <div v-if="!list.length" class="col-span-full p-8 text-center text-sm text-gray-400">无匹配记忆</div>
      </div>
    </div>

    <div v-if="showForm" class="w-[24rem] border-l border-gray-200 dark:border-gray-700 flex flex-col min-h-0">
      <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center">
        <span class="font-semibold text-sm">{{ editingId ? '编辑记忆' : '新建记忆' }}</span>
        <button class="ml-auto text-xs text-gray-400 hover:text-gray-600" @click="showForm = false">关闭</button>
      </div>
      <div class="flex-1 overflow-y-auto p-4 space-y-3">
        <div>
          <div class="text-xs text-gray-500 mb-1">类型</div>
          <select v-model="form.type" class="w-full px-2 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent">
            <option v-for="(l, k) in TYPE_LABEL" :key="k" :value="k">{{ l }}（{{ k }}）</option>
          </select>
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">标题 *</div>
          <input v-model="form.title" class="w-full px-2 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">内容</div>
          <textarea v-model="form.content" rows="6" class="w-full px-2 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent"></textarea>
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">标签（逗号分隔）</div>
          <input v-model="form.tagsText" placeholder="如：报价,口径" class="w-full px-2 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">可见性（D25 ACL）</div>
          <select v-model="form.visibility" class="w-full px-2 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-transparent">
            <option value="team">团队可见</option>
            <option value="private">仅自己</option>
            <option value="restricted">指定成员</option>
          </select>
        </div>
        <div v-if="form.visibility === 'restricted'">
          <div class="text-xs text-gray-500 mb-1">可见成员 *</div>
          <div class="max-h-40 overflow-y-auto space-y-1 rounded border border-gray-300 dark:border-gray-600 p-2">
            <label v-for="u in members" :key="u.id" class="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" :checked="form.allow_members.includes(u.username)" @change="toggleMember(u.username)" />
              <span>{{ u.display_name || u.username }}</span>
              <span class="text-xs text-gray-400">{{ u.username }}</span>
            </label>
          </div>
        </div>
        <button :disabled="busy" class="w-full px-3 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50" @click="save">
          {{ busy ? '提交中…' : (editingId ? '保存修改' : '创建记忆') }}
        </button>
      </div>
    </div>
  </div>
</template>
