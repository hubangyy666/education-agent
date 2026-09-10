import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles.css'
import './product.css'
import './learning.css'
import { registerLearningTools } from './webmcp'
createApp(App).use(router).mount('#app')
registerLearningTools()
