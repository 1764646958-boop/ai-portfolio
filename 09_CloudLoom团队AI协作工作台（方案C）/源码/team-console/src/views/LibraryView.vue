<script setup lang="ts">
// 资料库 Tab（D4/D14）：GET/POST /api/files（≤10MB multipart）· POST /api/links · 下载 · 删除（仅管理员）
// 前端不落地密钥；上传走同源 Cookie 会话，FormData 由 api() 自动处理（不设 Content-Type）
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

interface Entry {
  id: string; kind: string; name: string; category: string; url: string | null
  size: number | null; mime: string | null; uploader: string; created_at: string
}
const auth = useAuthStore()
const list = ref<Entry[]>([])
const loading = ref(false)
const err = ref('')
const msg = ref('')
const q = ref('')
const kindFilter = ref('')
const catFilter = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const uploadCat = ref('资料库')
const uploading = ref(false)
const linkOpen = ref(false)
const linkForm = ref({ name: '', url: '', category: '资料库' })
const linkErr = ref('')
const savingLink = ref(false)

const isAdmin = computed(() => auth.user?.role === 'admin')
const categories = computed(() => {
  const s = new Set<string>()
  for (const e of list.value) if (e.category) s.add(e.category)
  return Array.from(s).sort()
})
const shown = computed(() => {
  const term = q.value.trim().toLowerCase()
  return list.value.filter((e) => {
    if (kindFilter.value && e.kind !== kindFilter.value) return false
    if (catFilter.value && e.category !== catFilter.value) return false
    if (term && !e.name.toLowerCase().includes(term)) return false
    return true
  })
})
const fileCount = computed(() => list.value.filter((e) => e.kind === 'file').length)
const linkCount = computed(() => list.value.filter((e) => e.kind === 'link').length)
function fmtSize(b: number | null) { return b === null ? '—' : (b < 1024 ? b + ' B' : (b / 1024).toFixed(1) + ' KB') }
function fmt(ts: string) { return String(ts).replace('T', ' ').slice(0, 16) }

async function load() {
  loading.value = true
  try {
    const r = await api<{ files: Entry[] }>('/files')
    list.value = r.files || []
    err.value = ''
  } catch (e) { err.value = (e as Error).message } finally { loading.value = false }
}
async function doUpload(ev: Event) {
  const input = ev.target as HTMLInputElement
  const f = input.files && input.files[0]
  if (!f) return
  if (f.size > 10 * 1024 * 1024) {
    err.value = '文件 ' + fmtSize(f.size) + ' 超过 10MB 上限（大文件请用「添加链接」走网盘，D14）'
    input.value = ''
    return
  }
  uploading.value = true; err.value = ''; msg.value = ''
  try {
    const fd = new FormData()
    fd.append('file', f)
    fd.append('category', uploadCat.value || '资料库')
    const r = await api<{ file: Entry }>('/files', { method: 'POST', body: fd })
    msg.value = '已上传：' + r.file.name + '（' + r.file.category + '）'
    await load()
  } catch (e) { err.value = (e as Error).message } finally { uploading.value = false; input.value = '' }
}
async function addLink() {
  linkErr.value = ''
  if (!linkForm.value.name.trim() || !linkForm.value.url.trim()) { linkErr.value = '名称与链接均必填'; return }
  savingLink.value = true
  try {
    await api('/links', { method: 'POST', body: JSON.stringify(linkForm.value) })
    linkOpen.value = false
    msg.value = '已添加链接：' + linkForm.value.name
    linkForm.value = { name: '', url: '', category: '资料库' }
    await load()
  } catch (e) { linkErr.value = (e as Error).message } finally { savingLink.value = false }
}
function open(e: Entry) {
  if (e.kind === 'link' && e.url) { window.open(e.url, '_blank', 'noopener'); return }
  window.open('/api/files/' + e.id + '/download', '_blank')
}
async function remove(e: Entry) {
  if (!window.confirm('确认删除「' + e.name + '」？删除后不可恢复（文件将从服务器移除）。')) return
  try { await api('/files/' + e.id, { method: 'DELETE' }); msg.value = '已删除：' + e.name; await load() }
  catch (er) { err.value = (er as Error).message }
}
onMounted(load)
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="shrink-0 px-4 py-3 border-b bg-white dark:bg-gray-800">
      <div class="flex items-center gap-3 flex-wrap">
        <h2 class="font-medium">资料库</h2>
        <span class="text-xs text-gray-400">{{ fileCount }} 个文件 · {{ linkCount }} 个链接</span>
        <div class="ml-auto flex items-center gap-2">
          <label class="text-xs text-gray-500">分类
            <input v-model="uploadCat" list="cat-list" class="ml-1 border rounded px-1 py-0.5 w-24 bg-white dark:bg-gray-800" />
          </label>
          <datalist id="cat-list"><option v-for="c in categories" :key="c" :value="c" /></datalist>
          <input ref="fileInput" type="file" class="hidden" @change="doUpload" />
          <button class="text-xs px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-50"
            :disabled="uploading" @click="fileInput && fileInput.click()">{{ uploading ? '上传中…' : '上传文件' }}</button>
          <button class="text-xs px-3 py-1.5 rounded border hover:bg-gray-50 dark:hover:bg-gray-700" @click="linkOpen = true">添加链接</button>
        </div>
      </div>
      <div class="flex items-center gap-2 mt-2 flex-wrap text-xs">
        <input v-model="q" placeholder="按名称搜索" class="border rounded px-2 py-1 w-48 bg-white dark:bg-gray-800" />
        <select v-model="kindFilter" class="border rounded px-1 py-1 bg-white dark:bg-gray-800">
          <option value="">全部类型</option><option value="file">文件</option><option value="link">链接</option>
        </select>
        <select v-model="catFilter" class="border rounded px-1 py-1 bg-white dark:bg-gray-800">
          <option value="">全部分类</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
        <button class="px-2 py-1 rounded border hover:bg-gray-50 dark:hover:bg-gray-700" @click="load">刷新</button>
        <span class="text-gray-400">上限 10MB/文件（D14）</span>
      </div>
      <p v-if="err" class="text-xs text-red-500 mt-2">{{ err }}</p>
      <p v-if="msg" class="text-xs text-green-600 mt-2">{{ msg }}</p>
    </div>

    <div class="flex-1 min-h-0 overflow-auto">
      <table class="w-full text-sm">
        <thead class="text-xs text-gray-400 border-b">
          <tr>
            <th class="text-left font-normal px-4 py-2">名称</th>
            <th class="text-left font-normal px-2 py-2 w-20">类型</th>
            <th class="text-left font-normal px-2 py-2 w-24">分类</th>
            <th class="text-left font-normal px-2 py-2 w-20">大小</th>
            <th class="text-left font-normal px-2 py-2 w-24">上传者</th>
            <th class="text-left font-normal px-2 py-2 w-36">时间</th>
            <th class="text-right font-normal px-4 py-2 w-32">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in shown" :key="e.id" class="border-b hover:bg-gray-50 dark:hover:bg-gray-800">
            <td class="px-4 py-2 break-all">{{ e.name }}</td>
            <td class="px-2 py-2">
              <span class="text-[11px] px-1.5 py-0.5 rounded"
                :class="e.kind === 'link' ? 'bg-purple-50 text-purple-600' : 'bg-blue-50 text-blue-600'">
                {{ e.kind === 'link' ? '链接' : '文件' }}
              </span>
            </td>
            <td class="px-2 py-2 text-gray-500">{{ e.category }}</td>
            <td class="px-2 py-2 text-gray-500">{{ fmtSize(e.size) }}</td>
            <td class="px-2 py-2 text-gray-500">{{ e.uploader }}</td>
            <td class="px-2 py-2 text-gray-500 text-xs">{{ fmt(e.created_at) }}</td>
            <td class="px-4 py-2 text-right whitespace-nowrap">
              <button class="text-xs text-blue-600 mr-2" @click="open(e)">{{ e.kind === 'link' ? '打开' : '下载' }}</button>
              <button v-if="isAdmin" class="text-xs text-red-500" @click="remove(e)">删除</button>
            </td>
          </tr>
          <tr v-if="!shown.length && !loading"><td colspan="7" class="px-4 py-6 text-center text-gray-400">
            {{ list.length ? '没有匹配的条目' : '资料库为空，上传第一个文件或添加链接' }}
          </td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="linkOpen" class="fixed inset-0 z-30 bg-black/40 flex items-center justify-center p-4" @click.self="linkOpen = false">
      <div class="bg-white dark:bg-gray-800 rounded-lg w-full max-w-md p-5">
        <h3 class="font-medium mb-3">添加链接</h3>
        <label class="block text-xs text-gray-500 mb-1">名称</label>
        <input v-model="linkForm.name" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900" />
        <label class="block text-xs text-gray-500 mb-1">链接（http/https）</label>
        <input v-model="linkForm.url" placeholder="https://" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900" />
        <label class="block text-xs text-gray-500 mb-1">分类</label>
        <input v-model="linkForm.category" list="cat-list" class="w-full border rounded px-2 py-1 mb-3 bg-white dark:bg-gray-900" />
        <p v-if="linkErr" class="text-xs text-red-500 mb-2">{{ linkErr }}</p>
        <div class="flex justify-end gap-2">
          <button class="text-sm px-3 py-1.5 rounded border" @click="linkOpen = false">取消</button>
          <button class="text-sm px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-50"
            :disabled="savingLink" @click="addLink">{{ savingLink ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
