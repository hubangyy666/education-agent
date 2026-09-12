import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles.css'
import './product.css'
import './learning.css'
import './jobs.css'
import { registerLearningTools } from './webmcp'
createApp(App).use(router).mount('#app')
registerLearningTools()

// A newly built release replaces hashed lazy chunks; recover the saved route once.
window.addEventListener('vite:preloadError', (event) => {
  try {
    const key = 'zhiji-asset-reload-at'
    const previous = Number(sessionStorage.getItem(key) || 0)
    if (Date.now() - previous < 60000) return
    sessionStorage.setItem(key, String(Date.now()))
    event.preventDefault()
    location.reload()
  } catch { /* Keep the page's retry action available when storage is unavailable. */ }
})
