<script setup lang="ts">
defineProps<{
  activeTab: 'preview' | 'raw'
  renderedHtml: string
  rawLines: string[]
}>()
</script>

<template>
  <div
    v-if="activeTab === 'preview'"
    data-test="document-preview-container"
    class="flex-1 overflow-auto p-6 md:p-10 bg-[#02050a] text-slate-200 leading-relaxed custom-scrollbar selection:bg-pink-500/30"
  >
    <div class="max-w-3xl mx-auto doc-body font-sans text-sm" v-html="renderedHtml"></div>
  </div>

  <div
    v-else
    data-test="document-raw-container"
    class="flex-1 overflow-auto p-4 md:p-6 bg-[#03060c] font-mono text-xs custom-scrollbar"
  >
    <div class="table w-full">
      <div
        v-for="(line, idx) in rawLines"
        :key="idx"
        class="table-row hover:bg-space-900/40 transition-colors"
      >
        <span
          class="table-cell pr-4 py-0.5 text-right text-space-600 select-none w-12 font-mono text-[11px]"
        >
          {{ idx + 1 }}
        </span>
        <span class="table-cell py-0.5 text-pink-100 whitespace-pre break-words">
          {{ line }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.doc-h1) {
  font-size: 1.5rem;
  font-weight: 800;
  color: #ffffff;
  border-bottom: 1px solid rgba(236, 72, 153, 0.4);
  padding-bottom: 0.5rem;
  margin-top: 0;
  margin-bottom: 1.25rem;
  letter-spacing: -0.025em;
}

:deep(.doc-h2) {
  font-size: 1.25rem;
  font-weight: 700;
  color: #fce7f3;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 0.35rem;
  margin-top: 1.75rem;
  margin-bottom: 0.75rem;
}

:deep(.doc-h3) {
  font-size: 1.05rem;
  font-weight: 600;
  color: #fbcfe8;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
}

:deep(.doc-p) {
  margin-top: 0;
  margin-bottom: 0.85rem;
  line-height: 1.7;
  color: #cbd5e1;
}

:deep(.doc-ul),
:deep(.doc-ol) {
  margin-top: 0.25rem;
  margin-bottom: 1rem;
  padding-left: 1.5rem;
  color: #cbd5e1;
}

:deep(.doc-ul) {
  list-style-type: disc;
}

:deep(.doc-ol) {
  list-style-type: decimal;
}

:deep(li) {
  margin-bottom: 0.35rem;
  line-height: 1.6;
}

:deep(.doc-code-block) {
  background: #060a12;
  border: 1px solid rgba(236, 72, 153, 0.25);
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: #fce7f3;
  overflow-x: auto;
  margin: 1rem 0;
}

:deep(.doc-inline-code) {
  background: #1e0e1a;
  border: 1px solid rgba(236, 72, 153, 0.3);
  padding: 0.15rem 0.35rem;
  border-radius: 0.25rem;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: #ffffff;
}

:deep(.doc-blockquote) {
  border-left: 3px solid #ec4899;
  padding-left: 1rem;
  margin: 1rem 0;
  color: #ffffff;
  font-style: italic;
  background: #100b14;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
  border-radius: 0 0.25rem 0.25rem 0;
}

:deep(.doc-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1.25rem 0;
  font-size: 0.85rem;
}

:deep(.doc-table th),
:deep(.doc-table td) {
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: 0.6rem 0.85rem;
  text-align: left;
}

:deep(.doc-table th) {
  background: #1a0b16;
  color: #ffffff;
  font-weight: 700;
}

:deep(.doc-hr) {
  border: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  margin: 1.5rem 0;
}
</style>

