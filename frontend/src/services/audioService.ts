import { httpClient } from './httpClient'

export interface TranscriptionResponse {
  text?: string
}

export const audioService = {
  transcribeAudio(blob: Blob, filename: string = 'recording.webm'): Promise<TranscriptionResponse> {
    const formData = new FormData()
    formData.append('file', blob, filename)
    return httpClient.postFormData<TranscriptionResponse>('/api/audio/transcribe', formData)
  },

  synthesizeSpeech(text: string, addSilence: boolean = false, signal?: AbortSignal): Promise<ArrayBuffer> {
    return httpClient.requestArrayBuffer('/api/audio/synthesize', {
      method: 'POST',
      json: { text, add_silence: addSilence },
      signal,
    })
  },
}

