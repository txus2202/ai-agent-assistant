import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createTtsAudioEngine } from '../useTtsAudio'
import { useTtsPlaybackQueue, type TtsPlaybackBridge } from '../useTtsPlaybackQueue'

describe('useTtsAudio & useTtsPlaybackQueue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('tracks reading roles symmetrically and groups atenea with supervisor', () => {
    const started: string[] = []
    const ended: string[] = []
    const afterStop = vi.fn()

    const engine = createTtsAudioEngine({
      onRoleReadingStart: (role) => started.push(role),
      onRoleReadingEnd: (role) => ended.push(role),
      onAfterStop: afterStop,
    })

    engine.addReadingAgentRole('Atenea')
    expect(engine.isAgentReading('supervisor')).toBe(true)
    expect(engine.isAgentReading('atenea')).toBe(true)
    expect(started).toEqual(['supervisor'])

    engine.activeTtsRole.value = 'supervisor'
    engine.removeReadingAgentRole('Atenea')
    expect(engine.isAgentReading('supervisor')).toBe(false)
    expect(engine.activeTtsRole.value).toBeNull()
    expect(ended).toEqual(['Atenea'])

    const stopCb = vi.fn()
    const unsubscribe = engine.onTtsStop(stopCb)
    engine.isTtsPlaying.value = true
    engine.stopTts()

    expect(engine.isTtsPlaying.value).toBe(false)
    expect(stopCb).toHaveBeenCalledTimes(1)
    expect(afterStop).toHaveBeenCalledTimes(1)

    unsubscribe()
    engine.stopTts()
    expect(stopCb).toHaveBeenCalledTimes(1)
  })

  it('parses streaming text chunks, suppresses raw code fences and emits spoken fallback', () => {
    const engine = createTtsAudioEngine()
    const chunks: Array<{ text: string; role?: string }> = []
    const unsub = engine.onTtsChunkReady((text, role) => {
      chunks.push({ text, role })
    })

    engine.feedTtsStreamingChunk('```mermaid\ngraph TD;\n  A-->B;\n```', 'diagrammer')
    engine.flushTtsStreamingBuffer('diagrammer')

    expect(chunks.length).toBeGreaterThanOrEqual(1)
    expect(chunks[0]?.text).not.toContain('graph TD')
    expect(chunks[0]?.role).toBe('diagrammer')

    chunks.length = 0
    engine.resetTtsStreamState()
    engine.feedTtsStreamingChunk('Diseño validado correctamente.', 'supervisor')
    expect(chunks).toEqual([{ text: 'Diseño validado correctamente.', role: 'supervisor' }])

    unsub()
  })

  it('queues synthesized sentences and aborts inflight prefetch when stopped', async () => {
    const playChunkMock = vi.fn().mockResolvedValue(undefined)
    const bridge: TtsPlaybackBridge = reactive({
      isVoiceOutputEnabled: true,
      isTtsPlaying: false,
      activeTtsRole: null,
      addReadingAgentRole: vi.fn(),
      removeReadingAgentRole: vi.fn(),
      playTtsAudioChunk: playChunkMock,
      stopTts: vi.fn(() => {
        bridge.isTtsPlaying = false
      }),
    })

    const receivedSignals: AbortSignal[] = []
    const deferred: { resolve?: (buf: ArrayBuffer) => void } = {}
    const synthMock = vi.fn((_text: string, _silence: boolean, signal?: AbortSignal) => {
      if (signal) receivedSignals.push(signal)
      return new Promise<ArrayBuffer>((resolve) => {
        deferred.resolve = resolve
      })
    })

    const queue = useTtsPlaybackQueue(bridge, synthMock)
    queue.playVoiceResponse('Arquitectura confirmada.', 'senior_architect')

    expect(bridge.isTtsPlaying).toBe(true)
    expect(bridge.activeTtsRole).toBe('senior_architect')
    expect(synthMock).toHaveBeenCalledTimes(1)
    expect(receivedSignals[0]?.aborted).toBe(false)

    // Trigger stop while prefetch is in progress -> aborts controller
    bridge.isTtsPlaying = false
    expect(receivedSignals[0]?.aborted).toBe(true)

    deferred.resolve?.(new ArrayBuffer(8))
    await Promise.resolve()
    expect(playChunkMock).not.toHaveBeenCalled()
  })
})
