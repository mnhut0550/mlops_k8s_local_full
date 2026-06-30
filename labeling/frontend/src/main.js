import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Upload   from './views/Upload.vue'
import Label    from './views/Label.vue'
import Progress from './views/Progress.vue'
import Train    from './views/Train.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',         component: Upload   },
    { path: '/label',    component: Label    },
    { path: '/progress', component: Progress },
    { path: '/train',    component: Train    },
  ]
})

createApp(App).use(router).mount('#app')
