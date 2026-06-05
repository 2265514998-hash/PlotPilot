<template>
  <section class="story-pipeline" aria-label="StoryPipeline 写作管线">
    <header class="story-pipeline__head">
      <span class="story-pipeline__brand">StoryPipeline</span>
      <span v-if="isRunning" class="story-pipeline__live">实时</span>
    </header>
    <div class="story-pipeline__track">
      <div
        v-for="(step, index) in steps"
        :key="step.key"
        class="story-pipeline__step"
        :class="`is-${step.state}`"
      >
        <span class="story-pipeline__icon" aria-hidden="true">
          <template v-if="step.state === 'done'">✓</template>
          <template v-else-if="step.state === 'active'">●</template>
          <template v-else>{{ index + 1 }}</template>
        </span>
        <span class="story-pipeline__label">{{ step.label }}</span>
        <span v-if="index < steps.length - 1" class="story-pipeline__connector" aria-hidden="true" />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    isRunning?: boolean
    currentStage?: string | null
    writingSubstep?: string | null
    auditProgress?: string | null
  }>(),
  {
    isRunning: false,
    currentStage: null,
    writingSubstep: null,
    auditProgress: null,
  },
)

type StepState = 'pending' | 'active' | 'done'

interface PipelineStep {
  key: string
  label: string
  state: StepState
}

const ORDER = [
  { key: 'outline_planning', label: '章前规划' },
  { key: 'context_assembly', label: '装配上下文' },
  { key: 'beat_magnification', label: '节拍拆分' },
  { key: 'prose', label: '正文生成' },
  { key: 'voice_check', label: '文风自检' },
  { key: 'narrative_sync', label: '叙事同步' },
  { key: 'tension', label: '张力评分' },
] as const

function resolveActiveKey(): string {
  const stage = props.currentStage || ''
  if (stage === 'auditing') {
    const p = props.auditProgress || ''
    if (p === 'voice_check') return 'voice_check'
    if (p === 'aftermath_pipeline') return 'narrative_sync'
    if (p === 'tension_scoring') return 'tension'
    return 'voice_check'
  }
  if (stage === 'writing') {
    const sub = props.writingSubstep || ''
    if (sub === 'outline_planning') return 'outline_planning'
    if (sub === 'context_assembly') return 'context_assembly'
    if (sub === 'beat_magnification') return 'beat_magnification'
    return 'prose'
  }
  if (stage === 'planning' || stage === 'macro_planning' || stage === 'act_planning') {
    return 'outline_planning'
  }
  return ''
}

const steps = computed<PipelineStep[]>(() => {
  const activeKey = resolveActiveKey()
  const activeIndex = ORDER.findIndex(s => s.key === activeKey)
  return ORDER.map((s, i) => {
    let state: StepState = 'pending'
    if (!props.isRunning && activeIndex < 0) {
      state = 'pending'
    } else if (activeIndex < 0) {
      state = i === 0 && props.isRunning ? 'active' : 'pending'
    } else if (i < activeIndex) {
      state = 'done'
    } else if (i === activeIndex) {
      state = 'active'
    }
    return { ...s, state }
  })
})
</script>

<style scoped>
.story-pipeline {
  padding: 12px 14px;
  border-radius: var(--app-radius-lg, 12px);
  border: 1px solid color-mix(in srgb, var(--color-primary, #6366f1) 22%, var(--app-border));
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--color-primary, #6366f1) 8%, var(--app-surface-elevated, #1a1d2e)) 0%,
    var(--app-surface-subtle, #141824) 100%
  );
}

.story-pipeline__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.story-pipeline__brand {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--color-primary, #818cf8) 80%, white);
}

.story-pipeline__live {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-success, #22c55e) 25%, transparent);
  color: var(--color-success, #4ade80);
  animation: pipeline-pulse 2s ease-in-out infinite;
}

.story-pipeline__track {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 0;
  align-items: center;
}

.story-pipeline__step {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 4px 4px;
  border-radius: 8px;
  font-size: 11px;
  color: var(--app-text-muted);
  position: relative;
}

.story-pipeline__step.is-done {
  color: var(--color-success, #4ade80);
}

.story-pipeline__step.is-active {
  color: var(--app-text-primary);
  background: color-mix(in srgb, var(--color-primary, #6366f1) 18%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--color-primary) 35%, transparent);
}

.story-pipeline__icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
}

.story-pipeline__step.is-done .story-pipeline__icon {
  background: color-mix(in srgb, var(--color-success) 20%, transparent);
  border-color: color-mix(in srgb, var(--color-success) 40%, transparent);
}

.story-pipeline__step.is-active .story-pipeline__icon {
  background: var(--color-primary, #6366f1);
  border-color: transparent;
  color: #fff;
}

.story-pipeline__connector {
  width: 12px;
  height: 1px;
  margin-left: 2px;
  background: var(--app-border);
}

@keyframes pipeline-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

@media (max-width: 1100px) {
  .story-pipeline__track {
    gap: 6px;
  }
  .story-pipeline__connector {
    display: none;
  }
}
</style>
