// 通知与 PWA（D19）：/api/poll 3-5s 轮询 + Notification 弹窗 + Service Worker 注册
// 铁律：前端不接触任何密钥；轮询走同源 Cookie 会话
import { reactive, ref } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

export interface NotifyItem { name: string; mtime: number; size: number; preview: string }

export const notifyState = reactive({
  permission: (typeof Notification !== 'undefined' ? Notification.permission : 'unsupported') as string,
  pollMs: 4000,
  running: false,
})
export const lastPollAt = ref('')
export const notifyList = ref<NotifyItem[]>([])
export const unread = ref(0)

let since = 0
let timer: ReturnType<typeof setInterval> | null = null
let primed = false

export async function enableNotifications(): Promise<string> {
  if (typeof Notification === 'undefined') return 'unsupported'
  try {
    const p = await Notification.requestPermission()
    notifyState.permission = p
    return p
  } catch { return 'error' }
}

export function sendTestNotification(): boolean {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return false
  try {
    new Notification('CloudLoom 测试通知', { body: '通知链路正常（D19：/api/poll 轮询 + Notification）', tag: 'cloudloom-test' })
    return true
  } catch { return false }
}

export function clearNotify() { notifyList.value = []; unread.value = 0 }

function pushDesktop(items: NotifyItem[]) {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
  const auth = useAuthStore()
  if (auth.user && auth.user.notify_enabled === false) return // 尊重设置 Tab 的通知开关
  for (const it of items.slice(0, 3)) {
    try {
      new Notification('CloudLoom 新通知 · ' + it.name, { body: (it.preview || '').slice(0, 120) || '（无预览）', tag: 'cloudloom-' + it.mtime })
    } catch { /* 通知失败不影响主流程 */ }
  }
}

async function tick() {
  try {
    const r = await api<{ now: number; files: NotifyItem[] }>('/poll?since=' + since)
    lastPollAt.value = new Date().toLocaleTimeString()
    const files = r.files || []
    if (files.length && primed) {              // 首轮只建基线，登录后不轰炸历史文件
      notifyList.value = files.concat(notifyList.value).slice(0, 50)
      unread.value += files.length
      pushDesktop(files)
    }
    since = r.now || Date.now()
    // S4.0 / B6-②：**只有成功的轮询才算建立基线**。原实现把 primed = true 放在 try/catch 之外：
    // boot 时尚未登录的 401、或任何一次失败轮询，都会把 primed 置真，使"第一个成功的轮询"
    // 被误判为"已建过基线" —— 用户一登录就被历史通知轰炸
    //（实测 13 条历史：3 个弹窗 + 红点 13；再来一条新通知红点变 14）。
    primed = true
  } catch { /* 未登录/网络异常静默重试（不置 primed、不推进 since，留待下次成功轮询建基线） */ }
}

export function startNotify(intervalMs = 4000) {
  notifyState.pollMs = intervalMs
  if (notifyState.running) return
  notifyState.running = true
  void tick()
  timer = setInterval(() => { void tick() }, intervalMs)
}
export function stopNotify() {
  if (timer) { clearInterval(timer); timer = null }
  notifyState.running = false
}
export function resetNotify() { since = 0; primed = false; clearNotify() }

// Service Worker：仅缓存静态资源；/api 与 /mcp 永不缓存（SSE 与实时数据不能走缓存）
export function registerSW() {
  if (!('serviceWorker' in navigator)) return
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* 无 SW 不影响主流程 */ })
  })
}
