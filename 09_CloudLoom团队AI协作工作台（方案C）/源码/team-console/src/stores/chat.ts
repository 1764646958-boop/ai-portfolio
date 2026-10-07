import { defineStore } from 'pinia'
import { api } from '../api'
import { idbLoad, idbSave } from '../lib/idb'

export interface ConvMember { id: string; name: string }
export interface Msg {
  seq?: number; id: string; conversation_id?: string
  sender_id: string; sender_type: 'member' | 'agent'; sender_name: string
  content: string; type: string; created_at: string
  recalled?: boolean; recalled_at?: string | null
  pending?: boolean; agentStatus?: string
}
export interface Conv {
  id: string; type: 'dm' | 'group'; title: string; members: ConvMember[]
  unread: number; last_message: Msg | null; last_read_seq: number; updated_at: string
}
export interface Agent {
  id: string; name: string; description?: string; preset?: boolean
  enabled?: boolean; port: number; status?: { running?: boolean }
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    convs: [] as Conv[],
    agents: [] as Agent[],
    activeConv: '' as string,
    mode: 'conv' as 'conv' | 'agent',   // 会话流 或 与单个 Agent 直聊（SSE）
    agentId: '' as string,
    messages: [] as Msg[],
    maxSeq: 0,
    error: '' as string,
    loading: false,
  }),
  getters: {
    totalUnread: (s) => s.convs.reduce((n, c) => n + (c.unread || 0), 0),
    activeConvObj: (s) => s.convs.find((c) => c.id === s.activeConv) || null,
    runningAgents: (s) => s.agents.filter((a) => a.status?.running),
    sleepingAgents: (s) => s.agents.filter((a) => !a.status?.running),
  },
  actions: {
    async loadAgents() {
      this.agents = (await api<{ agents: Agent[] }>('/agents')).agents
    },
    async loadConvs() {
      this.convs = (await api<{ conversations: Conv[] }>('/conversations')).conversations
    },
    async createConv(type: 'dm' | 'group', memberIds: string[], title?: string) {
      const r = await api<{ conversation_id: string; existed?: boolean }>('/conversations', {
        method: 'POST', body: JSON.stringify({ type, member_ids: memberIds, title }),
      })
      await this.loadConvs()
      await this.open(r.conversation_id)
      return r.conversation_id
    },
    openAgent(id: string) { this.mode = 'agent'; this.agentId = id },
    async open(id: string) {
      this.mode = 'conv'
      this.activeConv = id
      this.error = ''
      this.loading = true
      // 先上本地缓存秒出，再以服务端为准校正
      const cached = await idbLoad<Msg>(id)
      if (cached.length) {
        this.messages = cached
        this.maxSeq = Math.max(...cached.map((m) => m.seq || 0))
      } else {
        this.messages = []
        this.maxSeq = 0
      }
      try {
        const r = await api<{ messages: Msg[]; max_seq: number }>(`/conversations/${id}/messages`)
        this.merge(r.messages)
        this.maxSeq = Math.max(this.maxSeq, r.max_seq)
        await this.markRead()
        await this.persist()
      } catch (e: any) { this.error = e.message } finally { this.loading = false }
    },
    // 服务端行为权威；本地 pending（乐观回显/流式临时）保留在末尾
    merge(rows: Msg[]) {
      const pend = this.messages.filter((m) => m.pending)
      const map = new Map<string, Msg>()
      for (const m of rows) map.set(m.id, m)
      for (const m of this.messages) if (!m.pending && !map.has(m.id)) map.set(m.id, m)
      const out = [...map.values()].sort((a, b) => (a.seq || 0) - (b.seq || 0))
      this.messages = [...out, ...pend]
    },
    async pull() {
      if (!this.activeConv) return
      const before = this.maxSeq
      const r = await api<{ messages: Msg[]; max_seq: number }>(`/conversations/${this.activeConv}/messages?since=${before}`)
      if (r.messages.length) {
        this.merge(r.messages)
        this.maxSeq = Math.max(this.maxSeq, r.max_seq)
        await this.markRead()
        await this.persist()
      }
    },
    async markRead() {
      if (!this.activeConv || !this.maxSeq) return
      try { await api(`/conversations/${this.activeConv}/read`, { method: 'POST', body: JSON.stringify({ seq: this.maxSeq }) }) } catch { /* ignore */ }
    },
    async send(content: string, type = 'text', files: File[] = []) {
      if (!this.activeConv) return
      let text = content
      for (const f of files) {
        const fd = new FormData()
        fd.append('file', f)
        fd.append('category', '资料库')
        const up = await api<{ file: { name: string } }>('/files', { method: 'POST', body: fd })
        text += `${text ? '\n' : ''}📎 ${up.file.name}`
      }
      if (!text.trim()) return
      const localId = 'local-' + Date.now()
      this.messages.push({
        id: localId, sender_id: '', sender_type: 'member', sender_name: '我',
        content: text, type, created_at: new Date().toISOString(), pending: true,
      })
      try {
        await api(`/conversations/${this.activeConv}/messages`, { method: 'POST', body: JSON.stringify({ content: text, type }) })
      } catch (e: any) { this.error = e.message }
      this.messages = this.messages.filter((m) => m.id !== localId)
      await this.pull()
      await this.loadConvs()
    },
    async recall(id: string) {
      try {
        await api(`/messages/${id}/recall`, { method: 'POST' })
        const m = this.messages.find((x) => x.id === id)
        if (m) { m.recalled = true; m.content = '' }
        await this.persist()
      } catch (e: any) { this.error = e.message }
    },
    async persist() {
      if (this.activeConv) await idbSave(this.activeConv, this.messages)
    },
    reset() { this.activeConv = ''; this.messages = []; this.maxSeq = 0; this.error = '' },
  },
})
