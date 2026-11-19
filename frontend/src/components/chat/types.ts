export interface SelectableAgentOption {
  value: string
  label: string
  colorHex?: string
}

export type ArtifactCopyPayload = {
  kind: 'diagram' | 'code' | 'document' | 'presentation'
  content: string
  cardKey: number
}

export type ArtifactOpenPayload =
  | { kind: 'diagram'; code: string; title: string }
  | {
      kind: 'code'
      code: string
      language?: string
      extension?: string
      title: string
    }
  | { kind: 'image'; imageUrl: string; alt?: string; title: string }
  | { kind: 'document'; content: string; title: string }
  | { kind: 'presentation'; content: string; title: string }

export type ArtifactDownloadPayload =
  | { kind: 'code'; code: string; extension?: string; title: string }
  | { kind: 'image'; imageUrl: string; title: string }
  | { kind: 'document-md' | 'document-pdf'; content: string; title: string }
  | {
      kind: 'presentation-pptx' | 'presentation-html' | 'presentation-md'
      content: string
      title?: string
    }

