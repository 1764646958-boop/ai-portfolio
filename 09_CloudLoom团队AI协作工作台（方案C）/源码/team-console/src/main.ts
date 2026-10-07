import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { registerSW, startNotify } from './lib/notify'

createApp(App).use(createPinia()).use(router).mount('#app')
registerSW()            // PWA：Service Worker（静态资源缓存，/api 不缓存）
startNotify(4000)       // D19：3-5s 轮询 /api/poll，新通知弹窗
