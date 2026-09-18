<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { SendHorizontal } from 'lucide-vue-next'

const props = defineProps<{
  messages: Array<{ role: 'user' | 'assistant', content: string }>
  isDebating: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', request: string): void
}>()

const inputMsg = ref('')
const chatScroll = ref<HTMLElement | null>(null)

const onSubmit = () => {
  if (!inputMsg.value.trim() || props.isDebating) return
  emit('submit', inputMsg.value)
  inputMsg.value = ''
}

// Auto-scroll to bottom when messages change
watch(() => props.messages.length, async () => {
  await nextTick()
  if (chatScroll.value) {
    chatScroll.value.scrollTop = chatScroll.value.scrollHeight
  }
})
</script>

<template>
  <div class="flex flex-col h-full bg-space-900 border-r border-space-800">
    <!-- Header -->
    <div class="p-4 border-b border-space-800">
      <h2 class="font-mono text-xs tracking-[0.2em] text-slate-400">MISSION LOG</h2>
    </div>

    <!-- Messages -->
    <div ref="chatScroll" class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
      <div 
        v-for="(msg, i) in messages" 
        :key="i"
        class="flex flex-col max-w-[85%]"
        :class="msg.role === 'user' ? 'self-end items-end ml-auto' : 'self-start items-start'"
      >
        <div class="text-[10px] font-mono text-slate-500 mb-1 tracking-wider uppercase">
          {{ msg.role === 'user' ? 'COMMANDER' : 'A.T.E.N.E.A' }}
        </div>
        <div 
          class="px-4 py-3 rounded-lg text-sm font-sans"
          :class="msg.role === 'user' ? 'bg-neon-blue/10 border border-neon-blue/30 text-neon-blue' : 'bg-space-800 border border-space-700 text-slate-300 whitespace-pre-wrap'"
        >
          {{ msg.content }}
        </div>
      </div>
      
      <!-- Typing indicator -->
      <div v-if="isDebating" class="flex space-x-1 items-center p-2">
        <div class="w-1.5 h-1.5 bg-neon-cyan rounded-full animate-bounce"></div>
        <div class="w-1.5 h-1.5 bg-neon-cyan rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
        <div class="w-1.5 h-1.5 bg-neon-cyan rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
      </div>
    </div>

    <!-- Input -->
    <div class="p-4 border-t border-space-800">
      <form @submit.prevent="onSubmit" class="relative">
        <input 
          v-model="inputMsg"
          type="text"
          placeholder="Enter directive..."
          class="w-full bg-space-950 border border-space-700 rounded-lg px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all placeholder-space-700 font-mono"
          :disabled="isDebating"
        />
        <button 
          type="submit"
          :disabled="!inputMsg.trim() || isDebating"
          class="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-space-700 hover:text-neon-cyan disabled:opacity-50 transition-colors"
        >
          <SendHorizontal class="w-5 h-5" />
        </button>
      </form>
    </div>
  </div>
</template>
