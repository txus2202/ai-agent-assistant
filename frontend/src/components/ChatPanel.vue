<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { SendHorizontal, Paperclip } from 'lucide-vue-next'
import { useDebateStore } from '../stores/debate'

const props = defineProps<{
  messages: Array<{ role: 'user' | 'assistant', content: string }>
  isDebating: boolean
}>()

const store = useDebateStore()

const inputMsg = ref('')
const selectedAgent = ref('supervisor')
const selectedFile = ref<File | null>(null)
const chatScroll = ref<HTMLElement | null>(null)

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0]
  }
}

const onSubmit = async () => {
  if (!inputMsg.value.trim() || props.isDebating) return
  
  let attachmentUrl = null
  if (selectedFile.value) {
    attachmentUrl = await store.uploadFile(selectedFile.value)
  }

  store.startDebate(inputMsg.value, selectedAgent.value, attachmentUrl)
  
  inputMsg.value = ''
  selectedFile.value = null
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
      <form @submit.prevent="onSubmit" class="flex flex-col gap-2 relative">
        <div class="flex items-center gap-2">
          <select 
            v-model="selectedAgent"
            data-test="target-agent-select"
            class="bg-space-950 border border-space-700 rounded px-2 py-1.5 text-xs font-mono text-slate-300 focus:outline-none focus:border-neon-cyan"
          >
            <option value="supervisor">Supervisor (Full Debate)</option>
            <option value="nl_interpreter">NL Interpreter</option>
            <option value="innovator_architect">Innovator Architect</option>
            <option value="senior_architect">Senior Architect</option>
            <option value="the_judge">The Judge</option>
            <option value="diagrammer">Diagrammer</option>
            <option value="devops_secops">DevOps & SecOps</option>
            <option value="learning">Learning Agent</option>
          </select>
          <label class="cursor-pointer text-space-400 hover:text-neon-cyan transition-colors flex items-center justify-center p-2 rounded hover:bg-space-800">
            <input type="file" @change="handleFileChange" class="hidden" data-test="file-input" />
            <Paperclip class="w-4 h-4" />
          </label>
          <span v-if="selectedFile" class="text-xs text-neon-cyan truncate max-w-[150px] font-mono">
            {{ selectedFile.name }}
          </span>
        </div>
        <textarea 
          v-model="inputMsg"
          placeholder="Enter directive..."
          rows="3"
          class="w-full bg-space-950 border border-space-700 rounded-lg px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-neon-cyan focus:ring-1 focus:ring-neon-cyan transition-all placeholder-space-700 font-mono resize-none custom-scrollbar"
          :disabled="isDebating"
          @keydown.enter.prevent="onSubmit"
        ></textarea>
        <button 
          type="submit"
          :disabled="!inputMsg.trim() || isDebating"
          class="absolute bottom-4 right-4 p-2 text-space-700 hover:text-neon-cyan disabled:opacity-50 transition-colors bg-space-900 rounded-full"
        >
          <SendHorizontal class="w-5 h-5" />
        </button>
      </form>
    </div>
  </div>
</template>
