import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
    {
      path: '/',
      component: () => import('./layouts/MainLayout.vue'),
      children: [
        { path: '', name: 'chat', component: () => import('./views/ChatView.vue'), meta: { title: '聊天' } },
        { path: 'kanban', name: 'kanban', component: () => import('./views/KanbanView.vue'), meta: { title: '看板' } },
        { path: 'tasks', name: 'tasks', component: () => import('./views/TasksView.vue'), meta: { title: '任务' } },
        { path: 'profiles', name: 'profiles', component: () => import('./views/ProfilesView.vue'), meta: { title: '画像' } },
        { path: 'library', name: 'library', component: () => import('./views/LibraryView.vue'), meta: { title: '资料库' } },
        { path: 'memory', name: 'memory', component: () => import('./views/MemoryView.vue'), meta: { title: '记忆' } },
        { path: 'settings', name: 'settings', component: () => import('./views/SettingsView.vue'), meta: { title: '设置' } },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.loaded) await auth.fetchMe()
  if (to.name !== 'login' && !auth.user) return { name: 'login' }
  if (to.name === 'login' && auth.user) return { name: 'chat' }
})

export default router
