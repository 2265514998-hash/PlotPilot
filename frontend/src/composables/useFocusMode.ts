import { ref, onMounted, onUnmounted, type Ref } from 'vue'

export interface FocusModeState {
  active: Ref<boolean>
  toggle: () => void
  enter: () => void
  exit: () => void
}

export function useFocusMode(): FocusModeState {
  const active = ref(false)

  function toggle() {
    active.value = !active.value
    if (active.value) {
      document.documentElement.classList.add('focus-mode')
    } else {
      document.documentElement.classList.remove('focus-mode')
    }
  }

  function enter() {
    active.value = true
    document.documentElement.classList.add('focus-mode')
  }

  function exit() {
    active.value = false
    document.documentElement.classList.remove('focus-mode')
  }

  function onKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
      e.preventDefault()
      toggle()
    }
    if (e.key === 'Escape' && active.value) {
      exit()
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
    document.documentElement.classList.remove('focus-mode')
  })

  return { active, toggle, enter, exit }
}
