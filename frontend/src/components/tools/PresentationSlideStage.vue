<script setup lang="ts">
import { ref } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import type { Slide } from '../../utils/slideParser'
import { useTouchSwipe } from '../../utils/touchSwipe'

defineProps<{
  currentSlide: Slide | undefined
  currentSlideIndex: number
  totalSlides: number
  slideDirection: 'forward' | 'backward'
}>()

const emit = defineEmits<{
  (e: 'prev'): void
  (e: 'next'): void
  (e: 'go-to', idx: number): void
}>()

const stageRef = ref<HTMLElement | null>(null)

useTouchSwipe(stageRef, {
  onSwipeLeft: () => emit('next'),
  onSwipeRight: () => emit('prev'),
  threshold: 25,
})
</script>

<template>
  <div class="flex items-center justify-center py-2 px-4 bg-[#050914] border-b border-space-800 shrink-0">
    <div
      class="flex items-center bg-[#030509] border border-cyan-500/30 rounded-lg px-2 sm:px-3 py-1 gap-2 font-mono text-xs text-slate-300 shadow-sm"
    >
      <button
        type="button"
        @click="emit('prev')"
        :disabled="currentSlideIndex <= 1"
        data-test="slide-prev-btn"
        class="p-1 text-slate-400 hover:text-neon-cyan disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
        title="Diapositiva anterior (←)"
        aria-label="Diapositiva anterior"
      >
        <ChevronLeft class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
      </button>

      <span
        data-test="slide-counter"
        class="text-[11px] sm:text-xs min-w-16 text-center text-neon-cyan font-bold select-none font-mono"
      >
        {{ currentSlideIndex }} / {{ totalSlides }}
      </span>

      <button
        type="button"
        @click="emit('next')"
        :disabled="currentSlideIndex >= totalSlides"
        data-test="slide-next-btn"
        class="p-1 text-slate-400 hover:text-neon-cyan disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
        title="Siguiente diapositiva (→ / Espacio)"
        aria-label="Siguiente diapositiva"
      >
        <ChevronRight class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
      </button>
    </div>
  </div>

  <div
    ref="stageRef"
    class="flex-1 overflow-y-auto overflow-x-hidden p-3 sm:p-6 md:p-8 bg-[#02050b] flex flex-col items-center relative custom-scrollbar touch-pan-y"
    style="touch-action: pan-y"
  >
    <Transition
      :name="slideDirection === 'forward' ? 'slide-forward' : 'slide-backward'"
      mode="out-in"
    >
      <div
        v-if="currentSlide"
        :key="currentSlide.index"
        data-test="presentation-slide-canvas"
        class="w-full max-w-4xl my-auto min-h-0 sm:min-h-[420px] bg-gradient-to-b from-[#081120] to-[#040813] border border-cyan-500/35 rounded-2xl p-4 sm:p-8 md:p-10 shadow-[0_0_50px_rgba(0,229,255,0.12)] flex flex-col justify-between transition-all duration-200"
        :class="currentSlide.layout === 'hero' ? 'text-center items-center justify-center' : ''"
      >
        <div class="w-full">
          <div class="flex items-center justify-between gap-3 mb-2">
            <span class="text-[11px] sm:text-xs font-mono font-bold uppercase tracking-widest text-cyan-400">
              Diapositiva {{ currentSlide.index }}
            </span>
            <span class="text-[10px] font-mono text-cyan-400/60 uppercase">Atenea Council</span>
          </div>

          <h2 class="text-xl sm:text-2xl md:text-3xl font-mono font-bold text-white tracking-wide uppercase text-shadow-glow">
            {{ currentSlide.title }}
          </h2>

          <div
            v-if="currentSlide.subtitle"
            class="p-3 sm:p-4 my-3 sm:my-4 bg-cyan-950/40 border-l-4 border-cyan-400 rounded-r-xl text-slate-200 text-sm sm:text-base italic font-sans"
          >
            {{ currentSlide.subtitle }}
          </div>
        </div>

        <div class="w-full my-auto py-2">
          <div
            v-if="currentSlide.cards && currentSlide.cards.length"
            class="grid gap-3 sm:gap-4 my-2"
            :class="
              currentSlide.cards.length === 2
                ? 'grid-cols-1 md:grid-cols-2'
                : currentSlide.cards.length >= 3
                  ? 'grid-cols-1 md:grid-cols-3'
                  : 'grid-cols-1'
            "
          >
            <div
              v-for="(card, cardIdx) in currentSlide.cards"
              :key="cardIdx"
              class="bg-[#050b18]/90 border border-cyan-500/30 hover:border-cyan-400/80 rounded-xl p-4 sm:p-5 shadow-[0_0_20px_rgba(0,229,255,0.06)] flex flex-col justify-between transition-all"
            >
              <div>
                <div class="flex items-center justify-between gap-2 mb-2 border-b border-cyan-500/20 pb-2">
                  <h4 class="text-sm sm:text-base font-mono font-bold text-cyan-200 uppercase truncate">
                    {{ card.title }}
                  </h4>
                  <span
                    v-if="card.badge"
                    class="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/40 text-[10px] font-mono font-bold text-cyan-300 uppercase shrink-0"
                  >
                    {{ card.badge }}
                  </span>
                </div>
                <div class="text-slate-300 text-xs sm:text-sm leading-relaxed whitespace-pre-line">
                  {{ card.content }}
                </div>
              </div>
            </div>
          </div>

          <ul
            v-if="currentSlide.bullets && currentSlide.bullets.length"
            class="list-none p-0 my-3 space-y-2.5 text-left"
            :class="currentSlide.layout === 'hero' ? 'max-w-xl mx-auto' : ''"
          >
            <li
              v-for="(bullet, bIdx) in currentSlide.bullets"
              :key="bIdx"
              class="flex items-start gap-3 text-slate-200 text-sm sm:text-base"
            >
              <span
                class="inline-block w-2 h-2 mt-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(0,229,255,0.8)] shrink-0"
              ></span>
              <span class="leading-relaxed">{{ bullet }}</span>
            </li>
          </ul>
        </div>

        <div
          v-if="currentSlide.notes"
          class="w-full text-left pt-2 border-t border-cyan-500/20 text-[11px] font-mono text-cyan-300/70"
        >
          <span class="font-bold text-cyan-400">Nota:</span> {{ currentSlide.notes }}
        </div>
      </div>

      <div v-else :key="'empty'" class="text-center text-slate-400 font-mono text-sm">
        No se han encontrado diapositivas estructuradas.
      </div>
    </Transition>
  </div>

  <div class="flex items-center justify-center gap-1.5 px-4 py-2.5 bg-[#050914] border-t border-space-800">
    <button
      v-for="idx in totalSlides"
      :key="idx"
      type="button"
      @click="emit('go-to', idx)"
      class="h-1.5 sm:h-2 rounded-full transition-all cursor-pointer"
      :class="
        idx === currentSlideIndex
          ? 'w-6 sm:w-8 bg-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.8)]'
          : 'w-2 bg-slate-700 hover:bg-slate-500'
      "
      :title="`Ir a diapositiva ${idx}`"
      :aria-label="`Ir a diapositiva ${idx}`"
    />
  </div>
</template>

<style scoped>
.text-shadow-glow {
  text-shadow: 0 0 15px rgba(0, 229, 255, 0.4);
}

.slide-forward-enter-active,
.slide-forward-leave-active,
.slide-backward-enter-active,
.slide-backward-leave-active {
  transition: opacity 0.22s ease-out, transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-forward-enter-from {
  opacity: 0;
  transform: translateX(40px) scale(0.98);
}
.slide-forward-leave-to {
  opacity: 0;
  transform: translateX(-40px) scale(0.98);
}

.slide-backward-enter-from {
  opacity: 0;
  transform: translateX(-40px) scale(0.98);
}
.slide-backward-leave-to {
  opacity: 0;
  transform: translateX(40px) scale(0.98);
}
</style>

