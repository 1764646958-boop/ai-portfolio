<script setup lang="ts">
// 画像 Tab（M3 / D20 / D21）：读 cron 每日生成的画像 JSON
// 过滤在后端完成（GET /api/profiles）：管理员全见，普通成员只见自己 —— 前端不做也不该做 ACL 裁剪
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

interface Section { key: string | null; entries: Record<string, unknown>[] }
interface ProfileFile {
  file: string; mtime: number; size: number; scope: string
  parse_error: string | null; sections: Section[]; entries_count: number
  data?: Record<string, unknown>
}
const SECTION_LABEL: Record<string, string> = {
  members: '成员画像', members_without_activity: '无协作记录成员', open_items_for_human: '待人工决策事项',
  data_sources: '数据来源', unreadable_sources: '不可读来源', pending_entries: '待写入偏好',
  confidence_and_caveats: '置信度与说明', board_snapshot: '板面快照',
}
const TITLE_KEYS = ['agent', 'username', 'display_name', 'name', 'member', '成员', 'title', 'id', 'note', 'item']

const auth = useAuthStore()
const files = ref<ProfileFile[]>([])
const restricted = ref(false)
const note = ref<string | null>(null)
const loading = ref(false)
const err = ref('')
const openEntry = ref<Record<string, boolean>>({})
const rawFile = ref<Record<string, boolean>>({})

const totalEntries = computed(() => files.value.reduce((n, f) => n + f.entries_count, 0))

function sectionLabel(k: string | null) { return k ? (SECTION_LABEL[k] || k) : '条目' }
function entryTitle(e: Record<string, unknown>) {
  for (const k of TITLE_KEYS) {
    const v = e[k]
    if (typeof v === 'string' && v.trim()) return v.length > 60 ? v.slice(0, 60) + '…' : v
  }
  return '条目'
}
function scalars(e: Record<string, unknown>) {
  const out: { k: string; v: string }[] = []
  for (const k of Object.keys(e)) {
    const v = e[k]
    if (v === null || v === undefined) continue
    if (typeof v === 'object') continue
    const s = String(v)
    out.push({ k, v: s.length > 120 ? s.slice(0, 120) + '…' : s })
    if (out.length >= 6) break
  }
  return out
}
function nestedCount(e: Record<string, unknown>) {
  let n = 0
  for (const k of Object.keys(e)) if (e[k] && typeof e[k] === 'object') n++
  return n
}
function fmt(ts: number) { return new Date(ts).toLocaleString() }
function fmtSize(b: number) { return b < 1024 ? b + ' B' : (b / 1024).toFixed(1) + ' KB' }
function toggle(map: Record<string, boolean>, key: string) { map[key] = !map[key] }
function pretty(e: Record<string, unknown>) { return JSON.stringify(e, null, 2) }

async function load() {
  loading.value = true
  try {
    const r = await api<{ restricted: boolean; note: string | null; files: ProfileFile[] }>('/profiles')
    files.value = r.files || []
    restricted.value = !!r.restricted
    note.value = r.note
    err.value = ''
  } catch (e) { err.value = (e as Error).message } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="h-full overflow-auto p-4">
    <div class="flex items-center gap-3 flex-wrap">
      <h2 class="font-medium">成员画像</h2>
      <span class="text-xs px-1.5 py-0.5 rounded" :class="auth.user && auth.user.role === 'admin' ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-500'">
        {{ auth.user && auth.user.role === 'admin' ? '管理员：可见全量画像' : '成员：仅见自己的条目' }}
      </span>
      <span class="text-xs text-gray-400">由值班 Agent 每日 cron 生成（D21）· {{ files.length }} 份 · {{ totalEntries }} 条</span>
      <button class="text-xs px-2 py-1 rounded border ml-auto hover:bg-gray-50 dark:hover:bg-gray-700" @click="load">刷新</button>
    </div>
    <p v-if="restricted" class="text-xs mt-2 px-3 py-2 rounded bg-amber-50 text-amber-700">
      {{ note || '普通成员仅可见本人的画像条目。' }}
    </p>
    <p v-if="err" class="text-xs text-red-500 mt-2">加载失败：{{ err }}</p>

    <p v-if="!files.length && !loading" class="text-sm text-gray-400 mt-6">
      暂无画像文件。画像由值班 Agent 的 cron 任务每日 06:00 生成到 ~/team-files/系统通知/画像/（SPEC 阶段5）。
    </p>
    <p v-else-if="!totalEntries && !loading && !restricted" class="text-sm text-gray-400 mt-6">画像文件存在但无可展示条目。</p>
    <p v-else-if="restricted && !totalEntries && !loading" class="text-sm text-gray-400 mt-6">
      本窗口画像中没有属于你的条目（M3：普通成员只见自己）。
    </p>

    <section v-for="f in files" :key="f.file" class="mt-4 border rounded-lg bg-white dark:bg-gray-800">
      <header class="px-4 py-3 border-b flex items-center gap-3 flex-wrap">
        <span class="text-sm font-medium">{{ f.file }}</span>
        <span class="text-xs text-gray-400">{{ fmt(f.mtime) }} · {{ fmtSize(f.size) }} · {{ f.entries_count }} 条</span>
        <span v-if="f.scope === 'all'" class="text-[11px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">全量（管理员）</span>
        <span v-else class="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">仅本人条目</span>
        <button v-if="f.data" class="text-xs px-2 py-1 rounded border ml-auto hover:bg-gray-50 dark:hover:bg-gray-700"
          @click="toggle(rawFile, f.file)">{{ rawFile[f.file] ? '收起原始 JSON' : '查看原始 JSON' }}</button>
      </header>
      <p v-if="f.parse_error" class="text-xs text-red-500 px-4 py-2">JSON 解析失败：{{ f.parse_error }}</p>
      <pre v-if="f.data && rawFile[f.file]" class="text-xs overflow-auto max-h-80 p-4 border-b bg-gray-50 dark:bg-gray-900">{{ pretty(f.data) }}</pre>

      <div v-for="s in f.sections" :key="String(s.key)" class="px-4 py-3 border-b last:border-0">
        <div class="text-xs text-gray-400 mb-2">{{ sectionLabel(s.key) }} · {{ s.entries.length }}</div>
        <div class="grid gap-3 md:grid-cols-2">
          <article v-for="(e, i) in s.entries" :key="i" class="border rounded-md p-3">
            <div class="flex items-start gap-2">
              <span class="text-sm font-medium flex-1 break-words">{{ entryTitle(e) }}</span>
              <span v-if="nestedCount(e)" class="text-[11px] text-gray-400 shrink-0">{{ nestedCount(e) }} 项明细</span>
            </div>
            <ul class="mt-1 text-[11px] text-gray-500 space-y-0.5">
              <li v-for="sc in scalars(e)" :key="sc.k"><span class="text-gray-400">{{ sc.k }}：</span>{{ sc.v }}</li>
            </ul>
            <button class="text-[11px] text-blue-600 mt-2" @click="toggle(openEntry, f.file + ':' + String(s.key) + ':' + i)">
              {{ openEntry[f.file + ':' + String(s.key) + ':' + i] ? '收起明细' : '展开明细' }}
            </button>
            <pre v-if="openEntry[f.file + ':' + String(s.key) + ':' + i]"
              class="text-[11px] whitespace-pre-wrap overflow-auto max-h-72 mt-2 border-t pt-2">{{ pretty(e) }}</pre>
          </article>
        </div>
      </div>
    </section>
  </div>
</template>
