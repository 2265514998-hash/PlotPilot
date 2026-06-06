<template>
  <div class="split-editor" :class="{ 'is-split': active }">
    <n-split v-if="active" direction="horizontal" :default-size="0.5" :min="0.25" :max="0.75" style="height:100%">
      <template #1>
        <div class="split-pane">
          <div class="split-pane__label">✏️ 写作</div>
          <slot name="primary" />
        </div>
      </template>
      <template #2>
        <div class="split-pane">
          <div class="split-pane__label">📖 参考</div>
          <slot name="secondary" />
        </div>
      </template>
    </n-split>
    <div v-else class="split-single">
      <slot name="primary" />
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props { active?: boolean }
withDefaults(defineProps<Props>(), { active: false })
</script>

<style scoped>
.split-editor { height: 100%; overflow: hidden; }
.split-single { height: 100%; }
.split-pane { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.split-pane__label {
  padding: 2px 8px; font-size: 0.65rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--text-color-muted); border-bottom: 1px solid var(--divider-color);
  background: var(--action-color-secondary, rgba(0,0,0,0.02));
}
</style>
