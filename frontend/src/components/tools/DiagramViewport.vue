<script setup lang="ts">
defineProps<{
  renderError: string | null
  diagramSvg: string
  code: string
  zoomLevel: number
}>()
</script>

<template>
  <div class="flex-1 overflow-auto bg-[#020408] relative custom-scrollbar select-none">
    <div class="min-w-full min-h-full flex items-center justify-center p-3 sm:p-6 md:p-8 m-auto">
      <div
        v-if="renderError"
        class="max-w-xl p-6 bg-red-950/20 border border-red-500/40 rounded-xl text-center font-mono m-auto"
      >
        <div class="text-red-400 text-sm font-bold mb-2">Error al renderizar el diagrama</div>
        <div class="text-xs text-slate-400 mb-4">{{ renderError }}</div>
        <pre
          class="p-3 bg-[#030509] border border-space-800 rounded text-left text-xs text-cyan-300 overflow-x-auto"
          >{{ code }}</pre
        >
      </div>

      <div
        v-else-if="diagramSvg"
        data-test="rendered-diagram-svg"
        class="diagram-svg-wrapper transition-transform duration-200 ease-out origin-center flex items-center justify-center m-auto"
        :style="{ transform: `scale(${zoomLevel})` }"
        v-html="diagramSvg"
      ></div>

      <div v-else class="flex flex-col items-center gap-3 text-neon-cyan font-mono text-xs m-auto">
        <div class="w-6 h-6 border-2 border-neon-cyan border-t-transparent rounded-full animate-spin"></div>
        <span>Generando representación visual...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diagram-svg-wrapper {
  max-width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.diagram-svg-wrapper :deep(svg) {
  display: block;
  margin: auto;
  max-width: 100%;
  max-height: 72vh;
  width: auto;
  height: auto;
  overflow: visible;
}
</style>

