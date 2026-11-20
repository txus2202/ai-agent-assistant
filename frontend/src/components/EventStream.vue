<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'

export interface TelemetryEvent {
  id?: string
  timestamp?: string
  type: string
  role?: string | null
  [key: string]: unknown
}

const props = defineProps<{
  events: Array<TelemetryEvent>
}>()

const listContainer = ref<HTMLElement | null>(null)

watch(
  () => props.events.length,
  async () => {
    await nextTick()
    if (listContainer.value) {
      listContainer.value.scrollTop = listContainer.value.scrollHeight
    }
  }
)

const formatTime = (isoString?: string) => {
  if (!isoString) return '--:--:--.---'
  const d = new Date(isoString)
  return d.toTimeString().split(' ')[0] + '.' + d.getMilliseconds().toString().padStart(3, '0')
}

const HIGHLIGHTED_EVENT_TYPES = new Set(['agent_started', 'agent_completed', 'hitl_required', 'error'])
const payloadCache = new WeakMap<TelemetryEvent, string>()

const serializePayload = (event: TelemetryEvent): string => {
  const cached = payloadCache.get(event)
  if (cached !== undefined) return cached
  const serialized = JSON.stringify(event, (k, v) =>
    (k === 'id' || k === 'timestamp' || k === 'type' || k === 'role') ? undefined : v
  ).replace(/^{|}$/g, '')
  payloadCache.set(event, serialized)
  return serialized
}

const formattedEvents = computed(() =>
  props.events.map((event, index) => ({
    key: event.id ?? `${event.type}-${event.timestamp ?? ''}-${index}`,
    typeUpper: event.type.toUpperCase(),
    type: event.type,
    isOtherType: !HIGHLIGHTED_EVENT_TYPES.has(event.type),
    role: event.role,
    formattedTime: formatTime(event.timestamp),
    payload: serializePayload(event)
  }))
)
</script>

<template>
  <div class="h-full flex flex-col font-mono text-[10px] text-space-400 min-h-0">
    <div class="p-2 border-b border-space-800 flex justify-between items-center shrink-0">
      <span class="text-neon-amber uppercase tracking-widest">Event Stream</span>
      <span class="text-space-500">{{ events.length }} events</span>
    </div>
    <div 
      ref="listContainer"
      class="flex-1 min-h-0 overflow-y-auto custom-scrollbar overscroll-contain p-2 space-y-1"
      style="-webkit-overflow-scrolling: touch;"
    >
      <div 
        v-for="event in formattedEvents" 
        :key="event.key"
        class="border-b border-space-800/50 pb-1 break-words hover:bg-space-800/50 transition-colors cursor-crosshair"
      >
        <span class="text-space-600 mr-2">[{{ event.formattedTime }}]</span>
        <span 
          class="font-bold mr-1"
          :class="{
            'text-neon-cyan': event.type === 'agent_started',
            'text-neon-green': event.type === 'agent_completed',
            'text-neon-amber': event.type === 'hitl_required',
            'text-neon-red': event.type === 'error',
            'text-space-300': event.isOtherType
          }"
        >{{ event.typeUpper }}</span>
        
        <span v-if="event.role" class="text-neon-pink mr-1">[{{ event.role }}]</span>
        
        <span class="text-space-400">
          {{ event.payload }}
        </span>
      </div>
      <div v-if="events.length === 0" class="text-center p-4 text-space-600 italic">
        Awaiting telemetry...
      </div>
    </div>
  </div>
</template>
