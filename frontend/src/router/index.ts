import { createRouter, createWebHistory } from 'vue-router'

const Home = () => import('../views/Home.vue')
const Dashboard = () => import('../views/Dashboard.vue')
const Workbench = () => import('../views/Workbench.vue')
const Chapter = () => import('../views/Chapter.vue')
const Cast = () => import('../views/Cast.vue')
const CharacterGraph = () => import('../views/CharacterGraph.vue')
const LocationGraph = () => import('../views/LocationGraph.vue')
const Corkboard = () => import('../views/Corkboard.vue')
const CharacterSchedulerSimulator = () =>
  import('../components/debug/CharacterSchedulerSimulator.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Home', component: Home },
    { path: '/dashboard', name: 'Dashboard', component: Dashboard },
    { path: '/book/:slug/workbench', name: 'Workbench', component: Workbench },
    { path: '/book/:slug/cast', name: 'Cast', component: Cast },
    { path: '/book/:slug/chapter/:id', name: 'Chapter', component: Chapter },
    { path: '/book/:slug/characters', name: 'CharacterGraph', component: CharacterGraph },
    { path: '/book/:slug/location-graph', name: 'LocationGraph', component: LocationGraph },
    { path: '/book/:slug/corkboard', name: 'Corkboard', component: Corkboard },
    {
      path: '/debug/scheduler',
      name: 'CharacterSchedulerSimulator',
      component: CharacterSchedulerSimulator,
    },
  ],
})

export default router
