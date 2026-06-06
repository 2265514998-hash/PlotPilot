<template>
  <div class="chapter-tree-panel">
    <div v-if="!treeNodes.length" class="empty-state-splash">
      <span style="font-size:2rem">📂</span>
      <p>暂无章节</p>
      <p class="hint" style="font-size:0.75rem;color:var(--text-color-muted)">切换到「托管撰稿」模式自动生成</p>
    </div>

    <div v-else class="chapter-tree-scroll">
      <div
        v-for="(node, i) of treeNodes"
        :key="node.id"
        class="tree-node"
        :class="{
          'is-active': node.id === currentChapterId,
          'is-dragging': dragIdx === i,
          'is-drag-over': dragOverIdx === i,
        }"
        draggable="true"
        @click="selectChapter(node)"
        @dragstart="onDragStart(i, $event)"
        @dragover.prevent="onDragOver(i)"
        @dragleave="onDragLeave"
        @drop.prevent="onDrop(i)"
        @contextmenu.prevent="showContextMenu($event, node, i)"
      >
        <!-- 折叠箭头 -->
        <span
          v-if="node.children?.length"
          class="tree-toggle"
          @click.stop="toggleCollapse(node.id)"
        >{{ collapsed.has(node.id) ? '▶' : '▼' }}</span>
        <span v-else class="tree-toggle tree-toggle--empty" />

        <!-- 图标 + 标签 -->
        <span class="tree-icon">{{ node.icon || '📄' }}</span>
        <div class="tree-info">
          <div class="tree-title">{{ node.label }}</div>
          <div class="tree-meta">
            <n-tag size="tiny" :bordered="false" :type="node.wordCount > 0 ? 'success' : 'default'">
              {{ node.wordCount > 0 ? `${node.wordCount}字` : '待写' }}
            </n-tag>
          </div>
        </div>

        <!-- 子节点（折叠展开） -->
        <div v-if="node.children?.length && !collapsed.has(node.id)" class="tree-children">
          <div
            v-for="child of node.children"
            :key="child.id"
            class="tree-node tree-node--child"
            :class="{ 'is-active': child.id === currentChapterId }"
            @click.stop="selectChapter(child)"
          >
            <span class="tree-toggle tree-toggle--empty" />
            <span class="tree-icon">{{ child.icon || '📝' }}</span>
            <div class="tree-info">
              <div class="tree-title">{{ child.label }}</div>
              <div class="tree-meta">
                <n-tag size="tiny" :bordered="false" :type="child.wordCount > 0 ? 'success' : 'default'">
                  {{ child.wordCount > 0 ? `${child.wordCount}字` : '待写' }}
                </n-tag>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右键菜单 -->
    <div
      v-if="contextMenu.visible"
      class="context-menu"
      :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
    >
      <div class="context-menu-item" @click="renameChapter">✏️ 重命名</div>
      <div class="context-menu-item" @click="insertAfter">＋ 在下方插入</div>
      <div class="context-menu-item" @click="duplicateChapter">📋 复制</div>
      <div class="context-menu-divider" />
      <div class="context-menu-item context-menu-item--danger" @click="deleteChapter">🗑 删除</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { NTag } from 'naive-ui'

interface TreeNode {
  id: number
  label: string
  icon?: string
  wordCount: number
  children?: TreeNode[]
}

interface Props {
  slug: string
  nodes: TreeNode[]
  currentChapterId?: number | null
}

const props = withDefaults(defineProps<Props>(), {
  currentChapterId: null,
})

const emit = defineEmits<{
  select: [id: number, title: string]
  reorder: [fromIdx: number, toIdx: number]
  rename: [id: number, newTitle: string]
  delete: [id: number]
  insert: [afterIdx: number]
}>()

// ── Tree state ──
const collapsed = ref(new Set<number>())
const treeNodes = computed(() => props.nodes)

// ── Drag state ──
const dragIdx = ref(-1)
const dragOverIdx = ref(-1)

// ── Context menu ──
const contextMenu = ref({ visible: false, x: 0, y: 0, nodeId: 0, nodeIdx: -1 })

// ── Actions ──
function selectChapter(node: TreeNode) {
  emit('select', node.id, node.label)
}

function toggleCollapse(id: number) {
  if (collapsed.value.has(id)) {
    collapsed.value.delete(id)
  } else {
    collapsed.value.add(id)
  }
}

function onDragStart(i: number, e: DragEvent) {
  dragIdx.value = i
  e.dataTransfer!.effectAllowed = 'move'
  e.dataTransfer!.setData('text/plain', String(i))
}

function onDragOver(i: number) {
  dragOverIdx.value = i
}

function onDragLeave() {
  dragOverIdx.value = -1
}

function onDrop(i: number) {
  const from = dragIdx.value
  dragIdx.value = -1
  dragOverIdx.value = -1
  if (from >= 0 && from !== i) {
    emit('reorder', from, i)
  }
}

function showContextMenu(e: MouseEvent, node: TreeNode, idx: number) {
  contextMenu.value = {
    visible: true,
    x: e.clientX,
    y: e.clientY,
    nodeId: node.id,
    nodeIdx: idx,
  }
}

function hideContextMenu() {
  contextMenu.value.visible = false
}

function renameChapter() {
  const title = prompt('新标题：', '')
  if (title && contextMenu.value.nodeId) {
    emit('rename', contextMenu.value.nodeId, title)
  }
  hideContextMenu()
}

function insertAfter() {
  emit('insert', contextMenu.value.nodeIdx)
  hideContextMenu()
}

function duplicateChapter() {
  // TODO: 调用后端复制章节 API
  hideContextMenu()
}

function deleteChapter() {
  if (confirm('确定删除此章节？此操作不可撤销。')) {
    emit('delete', contextMenu.value.nodeId)
  }
  hideContextMenu()
}

onMounted(() => document.addEventListener('click', hideContextMenu))
onUnmounted(() => document.removeEventListener('click', hideContextMenu))
</script>

<style scoped>
.chapter-tree-panel { height: 100%; display: flex; flex-direction: column; }
.chapter-tree-scroll { flex: 1; overflow-y: auto; padding: 0.25rem 0; }

.tree-node {
  display: flex; align-items: center; gap: 0.3rem;
  padding: 0.35rem 0.5rem; border-radius: 8px; cursor: pointer;
  transition: background 0.15s ease;
  user-select: none;
}
.tree-node:hover { background: var(--action-color-hover, rgba(0,0,0,0.04)); }
.tree-node.is-active { background: var(--color-brand-light, rgba(79,70,229,0.1)); box-shadow: inset 3px 0 0 var(--color-brand, #4f46e5); }
.tree-node.is-dragging { opacity: 0.4; }
.tree-node.is-drag-over { box-shadow: inset 0 2px 0 var(--color-brand, #4f46e5); }

.tree-node--child { padding-left: 2rem; font-size: 0.875rem; }

.tree-toggle { width: 16px; text-align: center; font-size: 0.6rem; flex-shrink: 0; color: var(--text-color-muted); cursor: pointer; }
.tree-toggle--empty { visibility: hidden; }
.tree-icon { font-size: 0.9rem; flex-shrink: 0; }
.tree-info { flex: 1; min-width: 0; }
.tree-title { font-size: 0.8rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tree-meta { margin-top: 2px; }

/* Context menu */
.context-menu {
  position: fixed; z-index: 1000;
  background: var(--card-color, #fff); border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.12); min-width: 140px;
  padding: 0.3rem 0; overflow: hidden;
}
.context-menu-item {
  padding: 0.45rem 1rem; font-size: 0.8rem; cursor: pointer;
  transition: background 0.1s;
}
.context-menu-item:hover { background: var(--action-color-hover, rgba(0,0,0,0.05)); }
.context-menu-item--danger { color: #ef4444; }
.context-menu-divider { height: 1px; background: var(--divider-color, rgba(0,0,0,0.08)); margin: 0.2rem 0; }
</style>
