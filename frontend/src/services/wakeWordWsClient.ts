import { resolveWsUrl } from './wsClient'

export interface WakeWordWsHandlers {
  onOpen: () => void | Promise<void>
  onMessage: (rawData: string) => void
  onClose: () => void
}

export class WakeWordWsClient {
  private socket: WebSocket | null = null

  isOpen(): boolean {
    return this.socket?.readyState === WebSocket.OPEN
  }

  connect(handlers: WakeWordWsHandlers): string {
    const wsUrl = resolveWsUrl('/ws/audio/wake-word')
    const socket = new WebSocket(wsUrl)
    socket.binaryType = 'arraybuffer'
    this.socket = socket

    socket.onopen = () => handlers.onOpen()

    socket.onmessage = (event: MessageEvent<string>) => {
      handlers.onMessage(String(event.data))
    }

    socket.onclose = () => {
      this.socket = null
      handlers.onClose()
    }

    return wsUrl
  }

  sendAudio(buffer: ArrayBuffer): void {
    if (this.isOpen() && this.socket) {
      this.socket.send(buffer)
    }
  }

  sendReset(): void {
    if (this.isOpen() && this.socket) {
      this.socket.send(JSON.stringify({ type: 'RESET' }))
    }
  }

  close(): void {
    if (!this.socket) {
      return
    }
    this.socket.onclose = null
    this.socket.onerror = null
    this.socket.onmessage = null
    this.socket.close()
    this.socket = null
  }
}

export function createWakeWordWsClient(): WakeWordWsClient {
  return new WakeWordWsClient()
}
