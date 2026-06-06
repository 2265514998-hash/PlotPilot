<template>
  <div class="cockpit-layout">
    <!-- 左栏：实时日志 + 章节轨 -->
    <aside class="cockpit-layout__left" aria-label="互动与章节">
      <div class="cockpit-layout__log">
        <AutopilotTerminalLog
          :novel-id="novelId"
          @desk-refresh="emit('desk-refresh')"
          @chapter-metrics-refresh="emit('chapter-metrics-refresh')"
        />
      </div>
      <AutopilotCockpitChapterRail
        :chapters="chapters"
        :current-chapter-id="currentChapterId"
        @select="(id, title) => emit('chapter-select', id, title)"
      />
    </aside>

    <!-- 中栏：全托管驾驶 -->
    <main class="cockpit-layout__center" aria-label="AUTOPILOT 全托管驾驶">
      <header class="cockpit-layout__center-head">
        <div>
          <span class="cockpit-layout__eyebrow">AUTOPILOT</span>
          <h2 class="cockpit-layout__title">全托管驾驶</h2>
        </div>
        <n-tag v-if="isRunning" type="success" size="small" round>运行中</n-tag>
        <n-tag v-else size="small" round>待机</n-tag>
      </header>
      <div class="cockpit-layout__center-body">
        <AutopilotPanel
          class="cockpit-layout__panel"
          :novel-id="novelId"
          embedded-cockpit
          @status-change="onStatusChange"
          @chapter-content-update="(d: any) => emit('chapter-content-update', d)"
          @chapter-chunk="(d: any) => emit('chapter-chunk', d)"
          @desk-refresh="emit('desk-refresh')"
          @beats-planned="(p: any) => emit('beats-planned', p)"
        />
      </div>
    </main>

    <!-- 右栏：角色 / 关系图 / 知识 -->
    <aside class="cockpit-layout__right" aria-label="角色与知识图谱">
      <n-tabs
        v-model:value="rightTab"
        type="line"
        size="small"
        class="cockpit-layout__tabs"
        animated
      >
        <n-tab-pane name="characters" tab="角色资料" display-directive="show">
          <div class="cockpit-layout__right-pane cockpit-layout__right-pane--split">
            <CharacterNavigator
              class="cockpit-layout__char-nav"
              :slug="novelId"
              :selected-character-id="selectedCharacterId"
              @select-character="selectedCharacterId = $event"
            />
            <CharacterProfile
              class="cockpit-layout__char-profile"
              :slug="novelId"
              :selected-character-id="selectedCharacterId"
              :current-chapter-number="currentChapterNumber"
            />
          </div>
        </n-tab-pane>
        <n-tab-pane name="graph" tab="关系图" display-directive="if">
          <div class="cockpit-layout__right-pane">
            <CharacterRelationGraph :slug="novelId" class="cockpit-layout__graph" />
          </div>
        </n-tab-pane>
        <n-tab-pane name="knowledge" tab="知识库" display-directive="if">
          <div class="cockpit-layout__right-pane cockpit-layout__right-pane--knowledge">
            <KnowledgePanel :slug="novelId" />
          </div>
        </n-tab-pane>
      </n-tabs>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import AutopilotPanel from './AutopilotPanel.vue'
import AutopilotTerminalLog from './AutopilotTerminalLog.vue'
import AutopilotCockpitChapterRail, { type CockpitChapterItem } from './AutopilotCockpitChapterRail.vue'
import CharacterNavigator from '@/components/workbench/CharacterNavigator.vue'
import CharacterProfile from '@/components/workbench/CharacterProfile.vue'
import CharacterRelationGraph from '@/components/graphs/CharacterRelationGraph.vue'
import KnowledgePanel from '@/components/knowledge/KnowledgePanel.vue'

const props = defineProps<{
  novelId: string
  chapters?: CockpitChapterItem[]
  currentChapterId?: number | null
}>()

const emit = defineEmits<{
  'status-change': [status: Record<string, unknown>]
  'chapter-content-update': [data: { chapterNumber: number; content: string; wordCount: number }]
  'chapter-chunk': [data: { chunk: string; beatIndex: number; content: string; chapterNumber: number }]
  'desk-refresh': []
  'beats-planned': [payload: { chapterNumber: number; beats: Array<Record<string, unknown>> }]
  'chapter-metrics-refresh': []
  'chapter-select': [chapterId: number, title: string]
}>()

const chapters = computed(() => props.chapters ?? [])
const currentChapterId = computed(() => props.currentChapterId ?? null)

const rightTab = ref<'characters' | 'graph' | 'knowledge'>('graph')
const selectedCharacterId = ref<string | null>(null)
const isRunning = ref(false)

const currentChapterNumber = computed(() => {
  const ch = chapters.value.find(c => c.id === currentChapterId.value)
  return ch?.number ?? null
})

function onStatusChange(status: Record<string, unknown>) {
  isRunning.value = status?.autopilot_status === 'running'
  emit('status-change', status)
}
</script>

<style scoped>
.cockpit-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(220px, 0.22fr) minmax(360px, 1fr) minmax(280px, 0.32fr);
  gap: 0;
  height: 100%;
  background: var(--app-page-bg);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg, 12px);
  overflow: hidden;
  box-shadow: var(--app-shadow-md);
}

.cockpit-layout__left {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--app-border);
  background: color-mix(in srgb, var(--app-surface-subtle) 90%, #0f111a);
}

.cockpit-layout__log {
  flex: 1;
  min-height: 180px;
  overflow: hidden;
}

.cockpit-layout__center {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--color-primary) 4%, var(--app-surface)) 0%,
    var(--app-page-bg) 120px
  );
}

.cockpit-layout__center-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
  border-bottom: 1px solid var(--app-border);
}

.cockpit-layout__eyebrow {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
  color: var(--app-text-muted);
}

.cockpit-layout__title {
  margin: 2px 0 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--app-text-primary);
}

.cockpit-layout__center-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 12px 12px;
}

.cockpit-layout__panel {
  margin: 0 !important;
}

.cockpit-layout__right {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-left: 1px solid var(--app-border);
  background: var(--app-surface);
}

.cockpit-layout__tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.cockpit-layout__tabs :deep(.n-tabs-nav) {
  padding: 0 8px;
}

.cockpit-layout__tabs :deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  padding: 0 !important;
}

.cockpit-layout__right-pane {
  height: 100%;
  min-height: 280px;
  overflow: hidden;
}

.cockpit-layout__right-pane--split {
  display: grid;
  grid-template-columns: 120px 1fr;
  min-height: 0;
}

.cockpit-layout__char-nav {
  border-right: 1px solid var(--app-border);
  overflow-y: auto;
}

.cockpit-layout__char-profile {
  overflow-y: auto;
  min-height: 0;
}

.cockpit-layout__right-pane--knowledge {
  overflow-y: auto;
}

.cockpit-layout__graph {
  height: 100%;
  min-height: 320px;
}

:deep(.autopilot-terminal) {
  height: 100%;
  border-radius: 0;
  border: none;
}

@media (max-width: 1280px) {
  .cockpit-layout {
    grid-template-columns: 200px 1fr;
    grid-template-rows: 1fr auto;
  }
  .cockpit-layout__right {
    grid-column: 1 / -1;
    max-height: 360px;
    border-left: none;
    border-top: 1px solid var(--app-border);
  }
}

@media (max-width: 900px) {
  .cockpit-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
  }
  .cockpit-layout__left {
    max-height: 280px;
    border-right: none;
    border-bottom: 1px solid var(--app-border);
  }
}
</style>
