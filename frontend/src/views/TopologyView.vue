<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Lock,
  Network,
  Plus,
  RotateCcw,
  Save,
  Search,
  Check,
  CheckCircle2,
  AlertCircle,
  X,
} from '@lucide/vue'
import AgentCard from '../components/AgentCard.vue'
import {
  configService,
  type DebateTopology,
  type EligibleTopologyAgent,
} from '../services/configService'
import { useDebateStore } from '../stores/debate'

type PhaseSlotKey = 'interpreters' | 'proposers' | 'reviewers' | 'evaluators' | 'implementers'

interface PhaseSlotMeta {
  key: PhaseSlotKey
  roleBadge: string
  phaseBadge: string
  title: string
  subtitle: string
}

const PHASE_SLOTS: readonly PhaseSlotMeta[] = [
  {
    key: 'interpreters',
    roleBadge: 'interpreter',
    phaseBadge: 'Fase 1',
    title: 'Intérpretes de Requerimientos (interpreters)',
    subtitle:
      'Traducen y formalizan la petición inicial antes del primer punto de control HITL. Si queda vacía, se omite esta fase.',
  },
  {
    key: 'proposers',
    roleBadge: 'proposer',
    phaseBadge: 'Fase 2A',
    title: 'Proponentes de Solución (proposers)',
    subtitle:
      'Especialistas que deliberan en paralelo generando propuestas técnicas alternativas.',
  },
  {
    key: 'reviewers',
    roleBadge: 'reviewer',
    phaseBadge: 'Fase 2B',
    title: 'Revisores de Crítica Cruzada (reviewers)',
    subtitle:
      'Auditan iterativamente las propuestas de Fase 2 según el número de rondas configurado.',
  },
  {
    key: 'evaluators',
    roleBadge: 'evaluator',
    phaseBadge: 'Fase 3',
    title: 'Evaluadores y Veredicto (evaluators)',
    subtitle:
      'Analizan riesgos, trade-offs y emiten la evaluación técnica previa al dictamen.',
  },
  {
    key: 'implementers',
    roleBadge: 'implementer',
    phaseBadge: 'Fase 4',
    title: 'Implementadores y Artefactos (implementers)',
    subtitle:
      'Generan en paralelo diagramas, pipelines DevSecOps, código o activos finales.',
  },
]

const router = useRouter()
const debateStore = useDebateStore()

const isLoading = ref(true)
const isSaving = ref(false)
const isResetting = ref(false)
const isCustomized = ref(false)

const supervisorName = ref('Atenea')
const supervisorDescription = ref(
  'Orquestadora estratégica del consejo técnico. Su asignación es fija e inmutable para todos los usuarios.',
)
const supervisorColor = ref('#f59e0b')

const eligibleAgents = ref<EligibleTopologyAgent[]>([])
const selectedBySlot = ref<Record<PhaseSlotKey, string[]>>({
  interpreters: [],
  proposers: [],
  reviewers: [],
  evaluators: [],
  implementers: [],
})
const reviewRounds = ref(1)

const errorMessage = ref<string | null>(null)
const statusMessage = ref<string | null>(null)
const alertBannerRef = ref<HTMLElement | null>(null)

// Specialist Picker Modal State
const pickerDialogRef = ref<HTMLDialogElement | null>(null)
const activePickerSlot = ref<PhaseSlotKey | null>(null)
const pickerSearchQuery = ref('')

const supportsNativeShowModal =
  typeof HTMLDialogElement !== 'undefined' &&
  typeof HTMLDialogElement.prototype.showModal === 'function'

const supportsClosedBy =
  typeof HTMLDialogElement !== 'undefined' && 'closedBy' in HTMLDialogElement.prototype

const activePickerMeta = computed<PhaseSlotMeta | null>(() => {
  if (!activePickerSlot.value) return null
  return PHASE_SLOTS.find((s) => s.key === activePickerSlot.value) || null
})

const filteredPickerAgents = computed<EligibleTopologyAgent[]>(() => {
  const q = pickerSearchQuery.value.trim().toLowerCase()
  if (!q) return eligibleAgents.value
  return eligibleAgents.value.filter(
    (agent) =>
      agent.name.toLowerCase().includes(q) ||
      agent.description.toLowerCase().includes(q) ||
      agent.id.toLowerCase().includes(q),
  )
})

const rangeProgressPercent = computed(() => `${Math.round((reviewRounds.value / 5) * 100)}%`)

const activeExecutionCount = computed(() => {
  return (
    selectedBySlot.value.interpreters.length +
    selectedBySlot.value.proposers.length +
    selectedBySlot.value.evaluators.length +
    selectedBySlot.value.implementers.length
  )
})

function normalizeSlotSelection(rawNames: string[], catalog: EligibleTopologyAgent[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const raw of rawNames || []) {
    const norm = raw.trim().toLowerCase()
    const match = catalog.find(
      (agent) =>
        agent.name.trim().toLowerCase() === norm || agent.id.trim().toLowerCase() === norm,
    )
    if (match && !seen.has(match.name)) {
      seen.add(match.name)
      result.push(match.name)
    }
  }
  return result
}

function buildFallbackCatalog(): EligibleTopologyAgent[] {
  return debateStore.agents
    .filter((ag) => ag.role !== 'supervisor' && !ag.can_ingest_documents)
    .map((ag) => ({
      id: ag.role,
      name: ag.name,
      description: ag.description || '',
      color_hex: ag.color_hex || '#22d3ee',
      uses_rag: ag.uses_rag,
      supports_hitl: ag.supports_hitl,
    }))
}

function applyTopologySnapshot(snapshot: DebateTopology) {
  const catalog =
    snapshot.eligible_agents && snapshot.eligible_agents.length > 0
      ? snapshot.eligible_agents
      : eligibleAgents.value.length > 0
        ? eligibleAgents.value
        : buildFallbackCatalog()

  eligibleAgents.value = catalog
  supervisorName.value = snapshot.supervisor_agent?.name || snapshot.supervisor || 'Atenea'
  if (snapshot.supervisor_agent?.description) {
    supervisorDescription.value = snapshot.supervisor_agent.description
  }
  if (snapshot.supervisor_agent?.color_hex) {
    supervisorColor.value = snapshot.supervisor_agent.color_hex
  }

  selectedBySlot.value = {
    interpreters: normalizeSlotSelection(snapshot.interpreters || [], catalog),
    proposers: normalizeSlotSelection(snapshot.proposers || [], catalog),
    reviewers: normalizeSlotSelection(snapshot.reviewers || [], catalog),
    evaluators: normalizeSlotSelection(snapshot.evaluators || [], catalog),
    implementers: normalizeSlotSelection(snapshot.implementers || [], catalog),
  }
  reviewRounds.value =
    typeof snapshot.review_rounds === 'number' ? snapshot.review_rounds : 1
  isCustomized.value = Boolean(snapshot.is_customized)
  debateStore.topology = snapshot
}

function getAssignedAgentsForSlot(slot: PhaseSlotKey): EligibleTopologyAgent[] {
  const names = selectedBySlot.value[slot]
  const result: EligibleTopologyAgent[] = []
  for (const name of names) {
    const found = eligibleAgents.value.find((ag) => ag.name === name)
    if (found) {
      result.push(found)
    }
  }
  return result
}

function getDraftTopologyRoles(agentName: string): string[] {
  const roles: string[] = []
  for (const slot of PHASE_SLOTS) {
    if (selectedBySlot.value[slot.key].includes(agentName)) {
      roles.push(slot.roleBadge)
    }
  }
  return roles
}

function isAgentSelected(slot: PhaseSlotKey, agentName: string): boolean {
  return selectedBySlot.value[slot].includes(agentName)
}

function removeAgentFromSlot(slot: PhaseSlotKey, agentName: string) {
  errorMessage.value = null
  statusMessage.value = null
  selectedBySlot.value[slot] = selectedBySlot.value[slot].filter((name) => name !== agentName)
}

function toggleAgentInActivePicker(agentName: string) {
  const slot = activePickerSlot.value
  if (!slot) return
  errorMessage.value = null
  statusMessage.value = null
  const existing = selectedBySlot.value[slot]
  if (existing.includes(agentName)) {
    selectedBySlot.value[slot] = existing.filter((name) => name !== agentName)
  } else {
    selectedBySlot.value[slot] = [...existing, agentName]
  }
}

function openPickerForSlot(slot: PhaseSlotKey) {
  activePickerSlot.value = slot
  pickerSearchQuery.value = ''
  const dialog = pickerDialogRef.value
  if (!dialog) return
  if (supportsNativeShowModal) {
    if (!dialog.open) {
      dialog.showModal()
    }
  } else {
    dialog.setAttribute('open', '')
  }
}

function closePicker() {
  const dialog = pickerDialogRef.value
  if (dialog) {
    if (supportsNativeShowModal && dialog.open) {
      dialog.close()
    } else {
      dialog.removeAttribute('open')
    }
  }
  activePickerSlot.value = null
  pickerSearchQuery.value = ''
}

function handleDialogNativeClose() {
  const dialog = pickerDialogRef.value
  if (dialog) {
    dialog.returnValue = ''
  }
  activePickerSlot.value = null
  pickerSearchQuery.value = ''
}

function handleDialogBackdropClick(event: MouseEvent) {
  if (supportsClosedBy) return
  const dialog = pickerDialogRef.value
  if (!dialog || event.target !== dialog) return
  const rect = dialog.getBoundingClientRect()
  const isDialogContent =
    rect.top <= event.clientY &&
    event.clientY <= rect.top + rect.height &&
    rect.left <= event.clientX &&
    event.clientX <= rect.left + rect.width
  if (!isDialogContent) {
    closePicker()
  }
}

function handleRoundsInput(event: Event) {
  errorMessage.value = null
  statusMessage.value = null
  const target = event.target as HTMLInputElement
  const parsed = Number.parseInt(target.value, 10)
  if (!Number.isNaN(parsed)) {
    reviewRounds.value = Math.max(0, Math.min(5, parsed))
  }
}

async function fetchInitialTopology() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const data = await configService.getTopology()
    applyTopologySnapshot(data)
  } catch (err) {
    errorMessage.value =
      err instanceof Error ? err.message : 'No se pudo cargar la topología del servidor.'
  } finally {
    isLoading.value = false
  }
}

async function handleSave() {
  errorMessage.value = null
  statusMessage.value = null

  if (activeExecutionCount.value === 0) {
    errorMessage.value =
      'Debes asignar al menos un especialista activo en Intérpretes, Proponentes, Evaluadores o Implementadores.'
    requestAnimationFrame(() => {
      alertBannerRef.value?.focus()
    })
    return
  }

  isSaving.value = true
  try {
    const updated = await configService.updateTopology({
      interpreters: [...selectedBySlot.value.interpreters],
      proposers: [...selectedBySlot.value.proposers],
      reviewers: [...selectedBySlot.value.reviewers],
      evaluators: [...selectedBySlot.value.evaluators],
      implementers: [...selectedBySlot.value.implementers],
      review_rounds: reviewRounds.value,
    })
    applyTopologySnapshot(updated)
    await debateStore.loadAgents()
    statusMessage.value =
      'Topología personal guardada correctamente. Aplicará en tus próximos debates.'
  } catch (err) {
    errorMessage.value =
      err instanceof Error ? err.message : 'Error al guardar la configuración de topología.'
  } finally {
    isSaving.value = false
  }
}

async function handleReset() {
  errorMessage.value = null
  statusMessage.value = null
  isResetting.value = true
  try {
    const restored = await configService.resetTopology()
    applyTopologySnapshot(restored)
    await debateStore.loadAgents()
    statusMessage.value =
      'Valores por defecto restablecidos. Usando la topología canónica del sistema (topology.yaml).'
  } catch (err) {
    errorMessage.value =
      err instanceof Error ? err.message : 'Error al restablecer la topología por defecto.'
  } finally {
    isResetting.value = false
  }
}

onMounted(() => {
  void fetchInitialTopology()
})
</script>

<template>
  <div
    class="topology-page h-screen h-[100svh] max-h-[100dvh] w-full bg-space-950 text-slate-300 font-sans flex flex-col overflow-hidden"
  >
    <!-- Header -->
    <header
      class="p-4 sm:p-5 border-b border-space-800/80 bg-space-900/90 backdrop-blur-md shrink-0 z-20"
    >
      <div
        class="max-w-6xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
      >
        <div class="flex items-center gap-3 sm:gap-4 min-w-0">
          <button
            type="button"
            @click="router.push('/')"
            data-test="topology-back-btn"
            class="topology-icon-btn p-2 sm:p-2.5 bg-space-850 hover:bg-space-800 border border-space-700/60 hover:border-cyan-500/40 rounded-xl transition-all text-slate-400 hover:text-cyan-300 shadow-sm shrink-0 cursor-pointer"
            title="Volver al chat"
            aria-label="Volver al chat"
          >
            <ArrowLeft aria-hidden="true" class="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
          <div class="min-w-0">
            <h1
              id="topology-main-heading"
              class="topology-heading text-lg sm:text-xl font-mono font-bold tracking-wider text-white flex items-center gap-2"
            >
              <Network aria-hidden="true" class="w-5 h-5 text-cyan-400 shrink-0" />
              <span>TOPOLOGÍA DE DELIBERACIÓN</span>
            </h1>
            <p class="text-[11px] font-mono text-cyan-400 tracking-[0.15em] uppercase mt-0.5">
              CONFIGURACIÓN PERSONAL POR OPERADOR
            </p>
          </div>
        </div>

        <!-- Customization Status Pill -->
        <div class="flex items-center gap-2.5 text-xs font-mono shrink-0">
          <span
            data-test="topology-status-badge"
            class="px-3 py-1.5 rounded-lg border flex items-center gap-2 font-semibold"
            :class="
              isCustomized
                ? 'bg-cyan-950/60 border-cyan-500/50 text-cyan-200'
                : 'bg-space-850/80 border-space-700/60 text-slate-300'
            "
          >
            <CheckCircle2
              aria-hidden="true"
              class="w-3.5 h-3.5 shrink-0"
              :class="isCustomized ? 'text-cyan-400' : 'text-slate-400'"
            />
            <span>{{ isCustomized ? 'Personalizada (Usuario)' : 'Por Defecto (topology.yaml)' }}</span>
          </span>
        </div>
      </div>
    </header>

    <!-- Main Scrollable Form Content -->
    <main class="flex-1 overflow-y-auto px-4 sm:px-6 py-6">
      <div class="max-w-6xl mx-auto">
        <div
          v-if="isLoading"
          class="p-8 text-center font-mono text-xs text-slate-400 bg-space-900/50 border border-space-800 rounded-xl"
        >
          Cargando configuración de topología...
        </div>

        <form
          v-else
          data-test="topology-main-form"
          method="post"
          action="/api/config/topology"
          aria-labelledby="topology-main-heading"
          class="space-y-6 pb-8"
          @submit.prevent="handleSave"
        >
          <!-- Accessible Error Alert -->
          <div
            v-if="errorMessage"
            ref="alertBannerRef"
            role="alert"
            tabindex="-1"
            data-test="topology-error-alert"
            class="p-3.5 rounded-xl bg-red-950/60 border border-red-500/50 text-red-200 text-xs font-mono flex items-start gap-2.5"
          >
            <AlertCircle aria-hidden="true" class="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{{ errorMessage }}</span>
          </div>

          <!-- Accessible Polite Status Confirmation -->
          <div
            v-if="statusMessage"
            role="status"
            aria-live="polite"
            data-test="topology-status-message"
            class="p-3.5 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs font-mono flex items-start gap-2.5"
          >
            <CheckCircle2 aria-hidden="true" class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <span>{{ statusMessage }}</span>
          </div>

          <!-- Top Row: Immutable Supervisor + Review Rounds -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <!-- Immutable Supervisor Card -->
            <section
              data-test="topology-supervisor-card"
              aria-labelledby="supervisor-card-heading"
              class="p-4 sm:p-5 rounded-xl bg-space-900/80 border border-amber-500/30 flex flex-col justify-between gap-3"
            >
              <div class="flex items-start justify-between gap-3 flex-wrap">
                <div class="flex items-center gap-2.5">
                  <span
                    aria-hidden="true"
                    class="w-3 h-3 rounded-full shrink-0"
                    :style="{ backgroundColor: supervisorColor }"
                  ></span>
                  <h2
                    id="supervisor-card-heading"
                    class="topology-heading text-sm font-mono font-bold uppercase tracking-wider text-white"
                  >
                    Agente Supervisor: {{ supervisorName }}
                  </h2>
                </div>
                <span
                  class="px-2.5 py-1 rounded-md bg-amber-950/60 border border-amber-500/40 text-amber-300 text-[11px] font-mono inline-flex items-center gap-1.5"
                >
                  <Lock aria-hidden="true" class="w-3 h-3" />
                  <span>Inmutable</span>
                </span>
              </div>
              <p class="topology-prose text-xs text-slate-400 leading-relaxed">
                {{ supervisorDescription }}
              </p>
              <p class="topology-prose text-[11px] font-mono text-amber-300/80">
                El orquestador estratégico gobierna el flujo HITL y la consolidación final; no puede ser modificado por ningún usuario.
              </p>
            </section>

            <!-- Review Rounds Control Card -->
            <section
              data-test="topology-review-rounds-card"
              aria-labelledby="review-rounds-heading"
              class="p-4 sm:p-5 rounded-xl bg-space-900/80 border border-cyan-800/40 flex flex-col justify-between gap-3"
            >
              <div class="flex items-center justify-between gap-3 flex-wrap">
                <h2
                  id="review-rounds-heading"
                  class="topology-heading text-sm font-mono font-bold uppercase tracking-wider text-white"
                >
                  Rondas de Revisión (Fase 2)
                </h2>
                <span
                  data-test="review-rounds-value"
                  class="px-2.5 py-1 rounded-md bg-cyan-950/70 border border-cyan-500/40 text-cyan-200 text-xs font-mono font-bold"
                >
                  {{ reviewRounds === 0 ? '0 (Sin revisión cruzada)' : `${reviewRounds} ${reviewRounds === 1 ? 'ronda' : 'rondas'}` }}
                </span>
              </div>

              <div class="space-y-2">
                <label
                  for="topology-review-rounds"
                  class="block text-xs font-mono text-slate-300"
                >
                  Iteraciones entre Proponentes y Revisores (0 a 5):
                </label>
                <p id="review-rounds-help" class="topology-prose text-xs text-slate-400">
                  Controla cuántas vueltas de crítica y refinamiento ocurren en la Fase 2 antes del punto HITL. Tus ajustes solo afectan a tu cuenta.
                </p>
                <input
                  id="topology-review-rounds"
                  name="review_rounds"
                  type="range"
                  min="0"
                  max="5"
                  step="1"
                  :value="reviewRounds"
                  :style="{ '--range-progress': rangeProgressPercent }"
                  aria-describedby="review-rounds-help"
                  class="topology-range w-full cursor-pointer"
                  @input="handleRoundsInput"
                />
                <div
                  aria-hidden="true"
                  class="flex justify-between text-[10px] font-mono text-slate-500 px-0.5"
                >
                  <span>0 (OFF)</span>
                  <span>1</span>
                  <span>2</span>
                  <span>3</span>
                  <span>4</span>
                  <span>5 (Máx)</span>
                </div>
              </div>

              <p
                v-if="selectedBySlot.reviewers.length === 0 && reviewRounds > 0"
                class="topology-prose text-[11px] font-mono text-amber-300/90"
              >
                Nota: No hay agentes seleccionados en Revisores (Fase 2B); el bucle de revisión se omitirá aunque las rondas sean mayores que 0.
              </p>
            </section>
          </div>

          <!-- Clean Phase Sections (Only Assigned AgentCards Rendered) -->
          <div class="space-y-4">
            <section
              v-for="slot in PHASE_SLOTS"
              :key="slot.key"
              :data-test="`phase-section-${slot.key}`"
              :aria-labelledby="`phase-heading-${slot.key}`"
              class="p-4 sm:p-5 rounded-xl bg-space-900/70 border border-space-800 space-y-4"
            >
              <!-- Phase Header -->
              <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div class="space-y-1 min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="px-2 py-0.5 rounded bg-cyan-950/70 border border-cyan-700/50 text-[10px] font-mono font-bold uppercase text-cyan-300">
                      {{ slot.phaseBadge }}
                    </span>
                    <h2
                      :id="`phase-heading-${slot.key}`"
                      class="topology-heading text-xs sm:text-sm font-mono font-bold uppercase tracking-wider text-white"
                    >
                      {{ slot.title }}
                    </h2>
                  </div>
                  <p class="topology-prose text-xs text-slate-400">
                    {{ slot.subtitle }}
                  </p>
                </div>

                <div class="flex items-center gap-2.5 shrink-0">
                  <span class="text-[11px] font-mono text-slate-400">
                    Activos: <strong class="text-cyan-300">{{ selectedBySlot[slot.key].length }}</strong>
                  </span>
                  <button
                    type="button"
                    :data-test="`open-picker-${slot.key}`"
                    class="topology-btn px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-cyan-600/50 hover:border-cyan-400 text-cyan-200 font-mono text-xs font-semibold inline-flex items-center gap-1.5 transition cursor-pointer shadow-[0_0_12px_rgba(0,229,255,0.08)]"
                    @click="openPickerForSlot(slot.key)"
                  >
                    <Plus aria-hidden="true" class="w-3.5 h-3.5 text-cyan-400" />
                    <span>Añadir especialista</span>
                  </button>
                </div>
              </div>

              <!-- Assigned Specialist Cards (Reusing AgentCard) -->
              <div
                v-if="getAssignedAgentsForSlot(slot.key).length > 0"
                class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5"
              >
                <AgentCard
                  v-for="agent in getAssignedAgentsForSlot(slot.key)"
                  :key="`${slot.key}-${agent.id}`"
                  :role="agent.id"
                  :role-name="agent.name"
                  :description="agent.description"
                  :color-hex="agent.color_hex"
                  state="STANDBY"
                  :uses-rag="agent.uses_rag"
                  :supports-hitl="agent.supports_hitl"
                  :topology-roles="getDraftTopologyRoles(agent.name)"
                  variant="topology"
                >
                  <template #header-action>
                    <button
                      type="button"
                      :data-test="`remove-${slot.key}-${agent.id}`"
                      :aria-label="`Quitar a ${agent.name} de ${slot.title}`"
                      title="Quitar de esta fase"
                      class="topology-icon-btn px-2 py-1 rounded-md bg-space-900 hover:bg-red-950/60 border border-space-700 hover:border-red-500/50 text-slate-400 hover:text-red-300 text-[10px] font-mono inline-flex items-center gap-1 transition cursor-pointer shrink-0"
                      @click="removeAgentFromSlot(slot.key, agent.name)"
                    >
                      <X aria-hidden="true" class="w-3 h-3" />
                      <span>Quitar</span>
                    </button>
                  </template>
                </AgentCard>
              </div>

              <!-- Empty Phase Notice -->
              <div
                v-else
                :data-test="`empty-slot-${slot.key}`"
                class="p-4 rounded-lg border border-dashed border-space-700/80 bg-space-950/40 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs font-mono text-slate-400"
              >
                <span>Sin especialistas asignados — esta fase se omitirá automáticamente durante el debate.</span>
                <button
                  type="button"
                  class="topology-btn text-cyan-300 hover:text-cyan-200 underline underline-offset-4 text-left sm:text-right cursor-pointer shrink-0"
                  @click="openPickerForSlot(slot.key)"
                >
                  + Seleccionar especialista
                </button>
              </div>
            </section>
          </div>

          <!-- Action Bar -->
          <div
            class="toolbar pt-2 border-t border-space-800 flex flex-wrap items-center justify-between gap-3"
          >
            <button
              type="button"
              data-test="topology-reset-btn"
              :disabled="isSaving || isResetting"
              class="topology-btn px-4 py-2.5 rounded-lg border border-space-700 bg-space-900 hover:bg-space-800 hover:border-amber-500/50 text-slate-300 hover:text-amber-200 font-mono text-xs font-semibold inline-flex items-center gap-2 transition cursor-pointer disabled:opacity-50"
              @click="handleReset"
            >
              <RotateCcw aria-hidden="true" class="w-4 h-4" />
              <span>{{ isResetting ? 'Restableciendo...' : 'Restablecer valores por defecto' }}</span>
            </button>

            <button
              type="submit"
              data-test="topology-save-btn"
              :disabled="isSaving || isResetting"
              class="topology-btn px-5 py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-space-950 font-mono text-xs font-bold uppercase tracking-wider inline-flex items-center gap-2 transition cursor-pointer disabled:opacity-50"
            >
              <Save aria-hidden="true" class="w-4 h-4" />
              <span>{{ isSaving ? 'Guardando...' : 'Guardar topología' }}</span>
            </button>
          </div>
        </form>
      </div>
    </main>

    <!-- Native Modal Dialog for Specialist Selection (Placed outside <form> so forms never nest) -->
    <dialog
      ref="pickerDialogRef"
      data-test="specialist-picker-dialog"
      v-bind="{ closedby: 'any' }"
      aria-labelledby="picker-dialog-title"
      class="picker-dialog p-0 rounded-2xl bg-space-900 border border-cyan-500/40 text-slate-200 shadow-[0_0_50px_rgba(0,229,255,0.2)] w-[min(94vw,64rem)] max-h-[88dvh] m-auto overflow-hidden"
      @close="handleDialogNativeClose"
      @click="handleDialogBackdropClick"
    >
      <div v-if="activePickerMeta" class="flex flex-col max-h-[88dvh]">
        <!-- Dialog Header -->
        <div class="px-4 sm:px-6 py-4 bg-space-950/90 border-b border-space-800 flex items-start justify-between gap-4 shrink-0">
          <div class="space-y-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="px-2 py-0.5 rounded bg-cyan-950 border border-cyan-600/50 text-[10px] font-mono font-bold uppercase text-cyan-300">
                {{ activePickerMeta.phaseBadge }}
              </span>
              <h2
                id="picker-dialog-title"
                class="topology-heading text-sm sm:text-base font-mono font-bold uppercase tracking-wider text-white"
              >
                Especialistas para {{ activePickerMeta.title }}
              </h2>
            </div>
            <p class="topology-prose text-xs text-slate-400">
              {{ activePickerMeta.subtitle }}
            </p>
          </div>

          <button
            type="button"
            aria-label="Cerrar selector de especialistas"
            title="Cerrar (Esc)"
            class="topology-icon-btn p-2 rounded-lg bg-space-900 hover:bg-red-950/40 border border-space-700 hover:border-red-500/50 text-slate-400 hover:text-red-300 transition cursor-pointer shrink-0"
            @click="closePicker"
          >
            <X aria-hidden="true" class="w-4 h-4" />
          </button>
        </div>

        <!-- Search Filter -->
        <div class="px-4 sm:px-6 py-3 bg-space-900/95 border-b border-space-800/80 shrink-0">
          <search>
            <label for="specialist-picker-search" class="sr-only">
              Filtrar especialistas por nombre o descripción
            </label>
            <div class="relative flex items-center">
              <Search aria-hidden="true" class="w-4 h-4 text-slate-500 absolute left-3 pointer-events-none" />
              <input
                id="specialist-picker-search"
                v-model="pickerSearchQuery"
                type="search"
                name="specialist_filter"
                autocorrect="off"
                autocapitalize="none"
                spellcheck="false"
                placeholder="Filtrar especialista por nombre o misión técnica..."
                class="w-full bg-space-950 border border-space-700 focus:border-cyan-400 rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-slate-200 placeholder:text-slate-500 focus:outline-none"
              />
            </div>
          </search>
        </div>

        <!-- Scrollable AgentCard Grid -->
        <div class="flex-1 overflow-y-auto p-4 sm:p-6">
          <div
            v-if="filteredPickerAgents.length === 0"
            class="p-6 text-center text-xs font-mono text-slate-400 border border-dashed border-space-800 rounded-xl"
          >
            No hay especialistas que coincidan con «{{ pickerSearchQuery }}».
          </div>

          <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <AgentCard
              v-for="agent in filteredPickerAgents"
              :key="`picker-${agent.id}`"
              :role="agent.id"
              :role-name="agent.name"
              :description="agent.description"
              :color-hex="agent.color_hex"
              :state="activePickerSlot && isAgentSelected(activePickerSlot, agent.name) ? 'ACTIVE' : 'STANDBY'"
              :uses-rag="agent.uses_rag"
              :supports-hitl="agent.supports_hitl"
              :topology-roles="getDraftTopologyRoles(agent.name)"
              variant="topology"
            >
              <template #header-action>
                <span
                  v-if="activePickerSlot && isAgentSelected(activePickerSlot, agent.name)"
                  class="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 text-[10px] font-mono font-bold inline-flex items-center gap-1 shrink-0"
                >
                  <Check aria-hidden="true" class="w-3 h-3" />
                  <span>Asignado</span>
                </span>
                <span
                  v-else
                  class="px-2 py-0.5 rounded bg-space-800 border border-space-700 text-slate-400 text-[10px] font-mono shrink-0"
                >
                  Disponible
                </span>
              </template>

              <template #footer>
                <button
                  type="button"
                  :data-test="`picker-toggle-${agent.id}`"
                  :aria-pressed="Boolean(activePickerSlot && isAgentSelected(activePickerSlot, agent.name))"
                  class="topology-btn w-full py-2 px-3 rounded-lg font-mono text-xs font-semibold inline-flex items-center justify-center gap-1.5 transition cursor-pointer border"
                  :class="
                    activePickerSlot && isAgentSelected(activePickerSlot, agent.name)
                      ? 'bg-red-950/40 hover:bg-red-950/70 border-red-500/40 text-red-200'
                      : 'bg-cyan-500/15 hover:bg-cyan-500/25 border-cyan-500/50 text-cyan-200'
                  "
                  @click="toggleAgentInActivePicker(agent.name)"
                >
                  <template v-if="activePickerSlot && isAgentSelected(activePickerSlot, agent.name)">
                    <X aria-hidden="true" class="w-3.5 h-3.5" />
                    <span>Quitar de {{ activePickerMeta.phaseBadge }}</span>
                  </template>
                  <template v-else>
                    <Plus aria-hidden="true" class="w-3.5 h-3.5" />
                    <span>Añadir a {{ activePickerMeta.phaseBadge }}</span>
                  </template>
                </button>
              </template>
            </AgentCard>
          </div>
        </div>

        <!-- Dialog Footer -->
        <div class="px-4 sm:px-6 py-3.5 bg-space-950/90 border-t border-space-800 flex items-center justify-between gap-3 shrink-0">
          <span class="text-xs font-mono text-slate-400">
            Seleccionados en {{ activePickerMeta.phaseBadge }}:
            <strong class="text-cyan-300">{{ activePickerSlot ? selectedBySlot[activePickerSlot].length : 0 }}</strong>
          </span>
          <button
            type="button"
            data-test="picker-close-btn"
            class="topology-btn px-5 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-space-950 font-mono text-xs font-bold uppercase tracking-wider transition cursor-pointer"
            @click="closePicker"
          >
            Listo
          </button>
        </div>
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.topology-page {
  --topology-accent: #22d3ee;
  color-scheme: dark light;
  accent-color: var(--topology-accent);
}

.topology-heading {
  text-wrap: balance;
}

.topology-prose {
  text-wrap: pretty;
  overflow-wrap: break-word;
}

.topology-btn,
.topology-icon-btn,
.topology-range {
  min-block-size: 24px;
  min-inline-size: 24px;
}

@media (pointer: coarse) {
  .topology-btn,
  .topology-icon-btn,
  .topology-range {
    min-block-size: 44px;
    min-inline-size: 44px;
  }
}

.topology-btn:focus-visible,
.topology-icon-btn:focus-visible,
.topology-range:focus-visible {
  outline: 2px solid var(--topology-accent);
  outline-offset: 2px;
}

/* Native <dialog> modal scroll containment & backdrop rules */
.picker-dialog[open] {
  display: flex;
  flex-direction: column;
}

.picker-dialog:modal {
  overscroll-behavior: contain;
}

.picker-dialog::backdrop {
  background-color: rgba(2, 6, 23, 0.82);
  backdrop-filter: blur(4px);
  overflow: hidden;
  overscroll-behavior: contain;
}

/* Progressive enhancement fallback for browsers without native CSS accent-color on range slider */
@supports not (accent-color: #22d3ee) {
  .topology-range {
    -webkit-appearance: none;
    appearance: none;
    background: transparent;
  }

  .topology-range::-webkit-slider-runnable-track {
    width: 100%;
    height: 8px;
    background: linear-gradient(
      to right,
      var(--topology-accent) var(--range-progress, 20%),
      #334155 var(--range-progress, 20%)
    );
    border-radius: 4px;
  }

  .topology-range::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: var(--topology-accent);
    margin-top: -4px;
  }
}
</style>
