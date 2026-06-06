<template>
  <n-modal v-model:show="visible" :mask-closable="true" transform-origin="center" :auto-focus="true">
    <div class="global-search-wrap">
      <n-input
        ref="inputRef"
        v-model:value="query"
        placeholder="搜索章节、角色、地点…"
        size="large"
        clearable
        :autofocus="true"
        @keydown.esc="visible = false"
        @keydown.enter="goToFirst"
        @update:value="onSearch"
      >
        <template #prefix><n-icon><search-outline /></n-icon></template>
      </n-input>

      <div v-if="query && results.length" class="search-results">
        <div v-for="r of results" :key="r.id" class="search-result-item" @click="goTo(r)">
          <span class="search-result-icon">{{ r.icon }}</span>
          <div>
            <div class="search-result-title">{{ r.title }}</div>
            <div class="search-result-excerpt" v-html="r.excerpt" />
          </div>
          <n-tag size="tiny" :bordered="false">{{ r.type }}</n-tag>
        </div>
      </div>

      <div v-else-if="query && !results.length && !searching" class="search-empty">
        未找到相关结果
      </div>

      <div class="search-hint" v-if="!query">
        <span>输入关键词搜索（支持标题/角色/地点）</span>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NModal, NInput, NIcon, NTag } from 'naive-ui'
import { SearchOutline } from '@vicons/ionicons5'

interface SearchResult { id: number; icon: string; title: string; excerpt: string; type: string; route: string }

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean] }>()
const visible = ref(props.modelValue)
watch(() => props.modelValue, v => { visible.value = v; if (v) query.value = ''; results.value = [] })
watch(visible, v => emit('update:modelValue', v))

const router = useRouter()
const query = ref('')
const results = ref<SearchResult[]>([])
const searching = ref(false)

function onSearch() {
  if (!query.value.trim()) { results.value = []; return }
  // Client-side search through cached data from Pinia stores
  // This is intentionally lightweight - full search would need a backend endpoint
  searching.value = true
  setTimeout(() => {
    const q = query.value.toLowerCase()
    const mock: SearchResult[] = []
    // In production, query the store or API
    if ('chapter'.includes(q) || q.length < 3) {
      mock.push({ id: 1, icon: '📄', title: `搜索: "${query.value}"`, excerpt: '在章节和角色中搜索…（全功能搜索需后端支持）', type: '提示', route: '' })
    }
    results.value = mock
    searching.value = false
  }, 150)
}

function goTo(r: SearchResult) {
  if (r.route) { router.push(r.route); visible.value = false }
}

function goToFirst() {
  if (results.value[0]?.route) { router.push(results.value[0].route); visible.value = false }
}
</script>

<style scoped>
.global-search-wrap { width: 500px; max-width: 90vw; }
.search-results { max-height: 360px; overflow-y: auto; margin-top: 0.5rem; }
.search-result-item { display: flex; align-items: flex-start; gap: 0.5rem; padding: 0.6rem 0.5rem; border-radius: 8px; cursor: pointer; transition: background 0.1s; }
.search-result-item:hover { background: var(--action-color-hover); }
.search-result-icon { font-size: 1.2rem; flex-shrink: 0; margin-top: 2px; }
.search-result-title { font-weight: 500; font-size: 0.875rem; }
.search-result-excerpt { font-size: 0.75rem; color: var(--text-color-muted); }
.search-empty, .search-hint { text-align: center; padding: 1rem; font-size: 0.85rem; color: var(--text-color-muted); }
</style>
