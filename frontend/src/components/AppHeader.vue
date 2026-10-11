<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '../stores/config'
import { useDebateStore } from '../stores/debate'
import { Cpu, Volume2, VolumeX, History, ChevronDown, Ear, EarOff } from '@lucide/vue'
import packageJson from '../../package.json'

const router = useRouter()
const version = packageJson.version
const debateStore = useDebateStore()

const toggleAudio = () => {
  debateStore.isVoiceOutputEnabled = !debateStore.isVoiceOutputEnabled
  if (!debateStore.isVoiceOutputEnabled) {
    debateStore.stopTts() // stop immediately if muted
  } else {
    debateStore.unlockAudioContext()
  }
}

const toggleAutoListen = () => {
  if (debateStore.isAutoListenEnabled) {
    debateStore.stopAutoListen()
  } else {
    debateStore.startAutoListen()
  }
}

// Supervisor state
const supervisorProvider = ref('GEMINI')
const supervisorModel = ref('PRO 1.5')
const isDropdownOpen = ref(false)
const selectedProviderForDropdown = ref<{id: string, name: string, models: {id: string, name: string}[]} | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const handleClickOutside = (event: MouseEvent) => {
  if (!dropdownRef.value || !isDropdownOpen.value) return
  
  const path = event.composedPath()
  if (!path.includes(dropdownRef.value)) {
    isDropdownOpen.value = false
    selectedProviderForDropdown.value = null
  }
}

const configStore = useConfigStore()
const providers = computed(() => configStore.providers)

onMounted(async () => {
  // Fetch actual saved supervisor configuration
  try {
    const configRes = await fetch('/api/config/agents/supervisor')
    if (configRes.ok) {
      const config = await configRes.json()
      supervisorProvider.value = config.provider
      supervisorModel.value = config.model_name
    }
  } catch (error) {
    console.error('Error fetching supervisor config:', error)
  }
  
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value
  if (!isDropdownOpen.value) {
    selectedProviderForDropdown.value = null
  }
}

const selectModel = async (providerName: string, modelName: string) => {
  supervisorProvider.value = providerName
  supervisorModel.value = modelName
  isDropdownOpen.value = false
  selectedProviderForDropdown.value = null
  
  // Persist to backend
  try {
    await fetch('/api/config/agents/supervisor', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: providerName, model_name: modelName })
    })
  } catch (error) {
    console.error('Failed to save supervisor config:', error)
  }
}
</script>

<template>
  <header class="h-14 border-b border-cyan-900/40 bg-space-900/90 backdrop-blur-md flex items-center z-30 shrink-0 w-full">
    <!-- Left branding & Status tag -->
    <div class="w-full md:w-1/3 lg:w-1/4 flex items-center pl-4">
      <span class="text-[10px] md:text-xs text-slate-400 font-mono tracking-widest uppercase">System Core v{{ version }}</span>
    </div>

    <!-- Center App Title Banner -->
    <div class="w-full md:flex-1 flex justify-center items-center h-full">
      <div class="hidden sm:block relative px-8 pt-[5px] pb-[6px] bg-space-850 border border-cyan-500/30 rounded-t-sm shadow-[0_0_20px_rgba(0,229,255,0.08)]">
        <div class="absolute -top-[1px] left-1/2 -translate-x-1/2 w-16 h-[2px] bg-cyan-400 shadow-[0_0_10px_#00e5ff]"></div>
        <h1 class="text-xs sm:text-sm font-semibold tracking-widest uppercase text-cyan-100 flex items-center justify-center space-x-2">
          <Cpu class="w-4 h-4 text-cyan-400" />
          <span class="font-bold tracking-widest">A.T.E.N.E.A.</span>
        </h1>
        <div class="text-center">
          <span class="text-[9px] text-cyan-300/70 font-mono font-normal tracking-normal lowercase">(Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas)</span>
        </div>
      </div>
    </div>

    <!-- Right System Controls -->
    <div class="w-full md:w-1/3 lg:w-[400px] flex items-center justify-end pr-4 space-x-4">
      <!-- Supervisor Model Selector -->
      <div class="relative" ref="dropdownRef">
        <button 
          @click="toggleDropdown"
          class="hidden md:flex items-center space-x-2 font-mono text-[10px] md:text-[11px] text-emerald-300 bg-emerald-950/30 border border-emerald-500/30 px-2.5 py-1 rounded hover:bg-emerald-950/50 hover:border-emerald-500/60 transition-colors"
          title="Supervisor Model Configuration"
        >
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span class="leading-none pt-[2px]">SUPERVISOR: {{ supervisorProvider }} - {{ supervisorModel }}</span>
          <ChevronDown class="w-3 h-3 text-emerald-500 ml-1" />
        </button>

        <!-- Dropdown Menu -->
        <div 
          v-if="isDropdownOpen"
          class="absolute top-full right-0 mt-2 w-48 bg-space-900 border border-emerald-900/50 rounded shadow-lg overflow-hidden z-50 font-mono text-xs"
        >
          <!-- View 1: Provider Selection -->
          <div v-if="!selectedProviderForDropdown">
            <div class="px-3 py-1.5 bg-space-950 text-emerald-500/70 text-[9px] uppercase tracking-wider border-b border-emerald-900/30">
              Select Provider
            </div>
            <button 
              v-for="provider in providers" 
              :key="provider.id"
              @click="selectedProviderForDropdown = provider"
              class="w-full text-left px-3 py-2 text-slate-300 hover:bg-space-800 hover:text-emerald-300 transition-colors flex items-center justify-between"
            >
              <span class="font-bold text-[10px] md:text-[11px]">{{ provider.name }}</span>
              <span class="text-[10px] text-slate-500">&gt;</span>
            </button>
          </div>
          
          <!-- View 2: Model Selection -->
          <div v-else class="flex flex-col max-h-[300px]">
            <div class="shrink-0 px-3 py-1.5 bg-space-950 text-emerald-500/70 text-[9px] uppercase tracking-wider border-b border-emerald-900/30 flex items-center justify-between">
              <button @click.stop="selectedProviderForDropdown = null" class="hover:text-emerald-300 px-1 py-0.5 -ml-1">&lt; BACK</button>
              <span>{{ selectedProviderForDropdown.name }}</span>
            </div>
            <div class="overflow-y-auto custom-scrollbar">
              <button 
                v-for="model in selectedProviderForDropdown.models" 
                :key="model.id"
                @click="selectModel(selectedProviderForDropdown.name, model.name)"
                class="w-full text-left px-3 py-2 text-slate-300 hover:bg-space-800 hover:text-emerald-300 transition-colors flex flex-col"
              >
                <span class="font-bold text-[10px] md:text-[11px]">{{ model.name }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Icons -->
      <div class="flex items-center space-x-2 text-slate-400">
        <button 
          @click="toggleAudio"
          class="p-1.5 hover:text-cyan-300 hover:bg-space-800 rounded transition border border-transparent hover:border-cyan-800/60" 
          title="Toggle System Audio"
        >
          <VolumeX v-if="!debateStore.isVoiceOutputEnabled" class="w-4 h-4 text-rose-400" />
          <Volume2 v-else class="w-4 h-4" />
        </button>
        <button 
          @click="toggleAutoListen"
          class="p-1.5 rounded transition border border-transparent"
          :class="debateStore.isAutoListenEnabled ? 'text-amber-400 bg-amber-900/30 border-amber-500/50' : 'hover:text-amber-200 hover:bg-space-800 hover:border-amber-800/60'"
          title="Toggle Auto-Listen (Wake Word)"
        >
          <Ear v-if="debateStore.isAutoListenEnabled" class="w-4 h-4" />
          <EarOff v-else class="w-4 h-4" />
        </button>
        <button 
          @click="router.push('/history')"
          class="p-1.5 hover:text-amber-400 hover:bg-space-800 rounded transition border border-transparent hover:border-amber-800/60 relative" 
          title="Debate History"
        >
          <History class="w-4 h-4" />
        </button>
      </div>
    </div>
  </header>
</template>
