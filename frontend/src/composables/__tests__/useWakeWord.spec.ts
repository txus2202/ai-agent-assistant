import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useWakeWord } from '../useWakeWord'

interface FakeSocket {
  readyState: number
  binaryType: string
  send: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
  onopen: (() => void | Promise<void>) | null
  onmessage: ((ev: { data: string }) => void) | null
  onclose: (() => void) | null
}

describe('useWakeWord', () => {
  let originalWebSocket: typeof WebSocket
  let sockets: FakeSocket[] = []
  let workletPortOnMessage: ((ev: { data: Float32Array }) => void) | null = null
  let trackStopSpy: ReturnType<typeof vi.fn>
  let audioCtxCloseSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    originalWebSocket = globalThis.WebSocket
    sockets = []
    workletPortOnMessage = null
    trackStopSpy = vi.fn()
    audioCtxCloseSpy = vi.fn().mockResolvedValue(undefined)

    class MockSocket {
      readyState = WebSocket.OPEN
      binaryType = 'blob'
      send = vi.fn()
      close = vi.fn()
      onopen: (() => void | Promise<void>) | null = null
      onmessage: ((ev: { data: string }) => void) | null = null
      onclose: (() => void) | null = null
      constructor() {
        sockets.push(this)
      }
    }
    globalThis.WebSocket = MockSocket as unknown as typeof WebSocket

    class MockAudioCtx {
      state = 'running'
      destination = {}
      audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) }
      createMediaStreamSource = vi.fn().mockReturnValue({ connect: vi.fn(), disconnect: vi.fn() })
      createGain = vi.fn().mockReturnValue({ gain: { value: 0 }, connect: vi.fn() })
      resume = vi.fn().mockResolvedValue(undefined)
      close = audioCtxCloseSpy
    }
    vi.stubGlobal('AudioContext', MockAudioCtx)

    class MockWorkletNode {
      connect = vi.fn()
      disconnect = vi.fn()
      port = {
        set onmessage(fn: ((ev: { data: Float32Array }) => void) | null) {
          workletPortOnMessage = fn
        },
        get onmessage() {
          return workletPortOnMessage
        },
      }
    }
    vi.stubGlobal('AudioWorkletNode', MockWorkletNode)

    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: trackStopSpy }],
        }),
      },
    })

    URL.createObjectURL = vi.fn().mockReturnValue('blob:mock')
    URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('captures PCM chunks when open and respects isRecording mute flag', async () => {
    const onSilenceCommand = vi.fn()
    const onHitlDecisionCommand = vi.fn()
    const onHitlRefineCommand = vi.fn()
    const onToggleHitlTargetAgent = vi.fn()
    const onWakeWordInterrupt = vi.fn()
    const onAgentWakeWordSelected = vi.fn()

    let hitlActive = false
    const ww = useWakeWord({
      isHitlRequired: () => hitlActive,
      onSilenceCommand,
      onHitlDecisionCommand,
      onHitlRefineCommand,
      onToggleHitlTargetAgent,
      onWakeWordInterrupt,
      onAgentWakeWordSelected,
    })

    ww.startAutoListen()
    expect(ww.isAutoListenEnabled.value).toBe(true)

    const sock = sockets[0]
    await sock?.onopen?.()

    workletPortOnMessage?.({ data: new Float32Array([0.5, -0.5]) })
    expect(sock?.send).toHaveBeenCalledTimes(1)

    // Suppress streaming while user holds manual recording
    ww.isRecording.value = true
    workletPortOnMessage?.({ data: new Float32Array([0.25, -0.25]) })
    expect(sock?.send).toHaveBeenCalledTimes(1)

    // Voice commands
    sock?.onmessage?.({ data: JSON.stringify({ type: 'SILENCE_VOICE_COMMAND' }) })
    expect(onSilenceCommand).toHaveBeenCalledTimes(1)

    sock?.onmessage?.({
      data: JSON.stringify({ type: 'WAKE_WORD_DETECTED', agent_role: 'senior_architect' }),
    })
    expect(onWakeWordInterrupt).toHaveBeenCalledTimes(1)
    expect(onAgentWakeWordSelected).toHaveBeenCalledWith('senior_architect')

    // HITL target chip toggling & refine voice command
    hitlActive = true
    sock?.onmessage?.({
      data: JSON.stringify({ type: 'WAKE_WORD_DETECTED', agent_role: 'devops_secops' }),
    })
    expect(onToggleHitlTargetAgent).toHaveBeenCalledWith('devops_secops')

    sock?.onmessage?.({ data: JSON.stringify({ type: 'HITL_VOICE_COMMAND', command: 'approve' }) })
    expect(onHitlDecisionCommand).toHaveBeenCalledWith('approve')

    sock?.onmessage?.({ data: JSON.stringify({ type: 'HITL_VOICE_COMMAND', command: 'refine' }) })
    expect(onHitlRefineCommand).toHaveBeenCalledTimes(1)

    ww.stopAutoListen()
    expect(ww.isAutoListenEnabled.value).toBe(false)
    expect(trackStopSpy).toHaveBeenCalledTimes(1)
    expect(audioCtxCloseSpy).toHaveBeenCalledTimes(1)
  })
})

