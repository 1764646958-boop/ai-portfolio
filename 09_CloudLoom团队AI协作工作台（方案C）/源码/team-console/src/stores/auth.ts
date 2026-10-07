import { defineStore } from 'pinia'
import { api } from '../api'

export interface User {
  id: string; username: string; display_name: string
  role: 'admin' | 'member'; status: string; avatar: string | null; notify_enabled: boolean
}

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null as User | null, loaded: false }),
  actions: {
    async fetchMe() {
      try { this.user = (await api<{ user: User }>('/me')).user }
      catch { this.user = null }
      finally { this.loaded = true }
    },
    async login(username: string, password: string) {
      const r = await api<{ user: User }>('/login', { method: 'POST', body: JSON.stringify({ username, password }) })
      this.user = r.user
    },
    async register(username: string, password: string, displayName: string) {
      return api<{ pending?: boolean; message: string }>('/register', {
        method: 'POST', body: JSON.stringify({ username, password, display_name: displayName }),
      })
    },
    async logout() { await api('/logout', { method: 'POST' }); this.user = null },
  },
})
