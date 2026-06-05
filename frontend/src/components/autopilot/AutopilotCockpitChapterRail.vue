<template>
  <aside class="cockpit-rail" aria-label="章节列表">
    <header class="cockpit-rail__head">
      <span class="cockpit-rail__title">章节</span>
      <n-tag size="tiny" round :bordered="false">{{ chapters.length }}</n-tag>
    </header>
    <n-scrollbar class="cockpit-rail__scroll">
      <n-list v-if="chapters.length" hoverable clickable size="small">
        <n-list-item
          v-for="ch in chapters"
          :key="ch.id"
          :class="{ 'is-active': currentChapterId === ch.id }"
          @click="emit('select', ch.id, ch.title)"
        >
          <div class="cockpit-rail__item">
            <span class="cockpit-rail__num">第 {{ ch.number }} 章</span>
            <span class="cockpit-rail__name">{{ ch.title || '未命名' }}</span>
            <n-tag
              size="tiny"
              round
              :type="ch.word_count > 0 ? 'success' : 'default'"
            >
              {{ ch.word_count > 0 ? `${ch.word_count} 字` : '草稿' }}
            </n-tag>
          </div>
        </n-list-item>
      </n-list>
      <n-empty v-else size="small" description="暂无章节" class="cockpit-rail__empty" />
    </n-scrollbar>
  </aside>
</template>

<script setup lang="ts">
export interface CockpitChapterItem {
  id: number
  number: number
  title: string
  word_count: number
}

defineProps<{
  chapters: CockpitChapterItem[]
  currentChapterId: number | null
}>()

const emit = defineEmits<{
  select: [chapterId: number, title: string]
}>()
</script>

<style scoped>
.cockpit-rail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  border-top: 1px solid var(--app-border);
}

.cockpit-rail__head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--app-border);
}

.cockpit-rail__title {
  font-size: 12px;
  font-weight: 650;
  color: var(--app-text-secondary);
}

.cockpit-rail__scroll {
  flex: 1;
  min-height: 0;
  max-height: 220px;
}

.cockpit-rail__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
}

.cockpit-rail__num {
  font-size: 11px;
  font-weight: 600;
  color: var(--app-text-primary);
}

.cockpit-rail__name {
  font-size: 11px;
  color: var(--app-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.n-list-item.is-active),
:deep(.n-list-item.is-active:hover) {
  background: color-mix(in srgb, var(--color-primary) 12%, var(--app-surface));
}

.cockpit-rail__empty {
  padding: 16px 8px;
}
</style>
