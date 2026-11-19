import { resolveWsUrl } from './wsClient'

export interface DebateWsHandlers {
  onOpen: () => void
  onMessage: (rawData: string) => void
  onClose: (event?: CloseEvent) => void
  onError: (event: Event) => void
}

export class DebateWsClient {
  private socket: WebSocket | null = null

  hasSocket(): boolean {
    return this.socket !== null
  }

  get rawSocket(): WebSocket | null {
    return this.socket
  }

  isOpenOrConnecting(): boolean {
    return Boolean(
      this.socket &&
        (this.socket.readyState === WebSocket.OPEN ||
          this.socket.readyState === WebSocket.CONNECTING),
    )
  }

  isOpen(): boolean {
    return this.socket?.readyState === WebSocket.OPEN
  }

  connect(handlers: DebateWsHandlers): string {
    const wsUrl = resolveWsUrl('/ws/debate')
    if (this.isOpenOrConnecting()) {
      return wsUrl
    }

    const socket = new WebSocket(wsUrl)
    this.socket = socket

    socket.onopen = () => {
      handlers.onOpen()
    }

    socket.onmessage = (event: MessageEvent<string>) => {
      handlers.onMessage(String(event.data))
    }

    socket.onclose = (event: CloseEvent) => {
      this.socket = null
      handlers.onClose(event)
    }

    socket.onerror = (event: Event) => {
      handlers.onError(event)
    }

    return wsUrl
  }

  sendJson(payload: unknown): boolean {
    if (!this.isOpen() || !this.socket) {
      return false
    }
    this.socket.send(JSON.stringify(payload))
    return true
  }

  disconnect(): void {
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

export function createDebateWsClient(): DebateWsClient {
  return new DebateWsClient()
}
