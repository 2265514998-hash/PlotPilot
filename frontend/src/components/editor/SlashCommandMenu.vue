<template>
  <div v-if="visible" class="slash-command-popup" ref="popupRef">
    <div v-for="group of groups" :key="group.name" class="slash-command-group">
      <div class="slash-command-group-label">{{ group.label }}</div>
      <div
        v-for="(cmd, i) of group.commands"
        :key="cmd.id"
        class="slash-command-item"
        :class="{ 'slash-command-item--selected': selectedGroupIdx === groupIdx(group.name) && selectedCmdIdx === i }"
        @click="$emit('select', cmd)"
        @mouseenter="onHover(group.name, i)"
      >
        <span class="slash-command-item__icon">{{ cmd.icon }}</span>
        <div>
          <div class="slash-command-item__label">{{ cmd.label }}</div>
          <div class="slash-command-item__desc">{{ cmd.desc }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

export interface SlashCommand {
  id: string
  icon: string
  label: string
  desc: string
  action: 'heading' | 'paragraph' | 'divider' | 'scene-break' | 'pov-switch' | 'time-jump' | 'flashback' | 'ai-continue' | 'ai-rewrite' | 'ai-expand' | 'ai-shorten' | 'ai-tone'
}

interface CommandGroup { name: string; label: string; commands: SlashCommand[] }

const props = defineProps<{ visible: boolean; query: string }>()
const emit = defineEmits<{ select: [cmd: SlashCommand]; close: [] }>()

const selectedGroupIdx = ref(0)
const selectedCmdIdx = ref(0)
const popupRef = ref<HTMLElement | null>(null)

const allCommands: CommandGroup[] = [
  {
    name: 'basic', label: '基础',
    commands: [
      { id: 'h1', icon: 'H1', label: '一级标题', desc: '章标题', action: 'heading' },
      { id: 'h2', icon: 'H2', label: '二级标题', desc: '节标题', action: 'heading' },
      { id: 'p', icon: '¶', label: '正文段落', desc: '普通文本', action: 'paragraph' },
      { id: 'hr', icon: '—', label: '分割线', desc: '内容分隔', action: 'divider' },
    ],
  },
  {
    name: 'novel', label: '小说',
    commands: [
      { id: 'scene-break', icon: '⁂', label: '场景分隔', desc: '插入 ***', action: 'scene-break' },
      { id: 'pov', icon: '👁', label: 'POV 切换', desc: '标记视角角色变化', action: 'pov-switch' },
      { id: 'time-jump', icon: '⏰', label: '时间跳跃', desc: '插入时间过渡标签', action: 'time-jump' },
      { id: 'flashback', icon: '↩', label: '闪回段落', desc: '回忆/倒叙段落', action: 'flashback' },
    ],
  },
  {
    name: 'ai', label: 'AI 辅助',
    commands: [
      { id: 'ai-continue', icon: '▶', label: '续写', desc: '从当前位置继续写作', action: 'ai-continue' },
      { id: 'ai-rewrite', icon: '🔄', label: '改写', desc: '优化当前段落表达', action: 'ai-rewrite' },
      { id: 'ai-expand', icon: '⬍', label: '扩写', desc: '扩充细节和描写', action: 'ai-expand' },
      { id: 'ai-shorten', icon: '⬆', label: '缩写', desc: '精简冗余内容', action: 'ai-shorten' },
      { id: 'ai-tone', icon: '🎭', label: '变语气', desc: '切换正式/轻松/紧张', action: 'ai-tone' },
    ],
  },
]

const groups = computed(() => {
  if (!props.query) return allCommands
  const q = props.query.toLowerCase()
  return allCommands.map(g => ({
    ...g,
    commands: g.commands.filter(c => c.label.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q)),
  })).filter(g => g.commands.length > 0)
})

function groupIdx(name: string) {
  return groups.value.findIndex(g => g.name === name)
}

function onHover(gn: string, ci: number) {
  const gi = groupIdx(gn)
  if (gi >= 0) { selectedGroupIdx.value = gi; selectedCmdIdx.value = ci }
}

function getFlatIndex(): number {
  let idx = 0
  for (let gi = 0; gi < groups.value.length; gi++) {
    for (let ci = 0; ci < groups.value[gi].commands.length; ci++) {
      if (gi === selectedGroupIdx.value && ci === selectedCmdIdx.value) return idx
      idx++
    }
  }
  return idx
}

function selectByFlatIndex(flat: number) {
  let idx = 0
  for (let gi = 0; gi < groups.value.length; gi++) {
    for (let ci = 0; ci < groups.value[gi].commands.length; ci++) {
      if (idx === flat) { selectedGroupIdx.value = gi; selectedCmdIdx.value = ci; return }
      idx++
    }
  }
  selectedGroupIdx.value = 0; selectedCmdIdx.value = 0
}

function onKeydown(e: KeyboardEvent) {
  if (!props.visible) return
  if (e.key === 'ArrowDown') { e.preventDefault(); selectByFlatIndex(getFlatIndex() + 1) }
  if (e.key === 'ArrowUp') { e.preventDefault(); selectByFlatIndex(Math.max(0, getFlatIndex() - 1)) }
  if (e.key === 'Enter') {
    e.preventDefault()
    const g = groups.value[selectedGroupIdx.value]
    const c = g?.commands[selectedCmdIdx.value]
    if (c) emit('select', c)
  }
  if (e.key === 'Escape') { e.preventDefault(); emit('close') }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>
