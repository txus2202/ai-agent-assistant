export interface SlideCard {
  title: string
  content: string
  badge?: string
}

export interface Slide {
  index: number
  title: string
  subtitle?: string
  layout: 'hero' | 'cards' | 'split' | 'standard'
  bullets: string[]
  cards: SlideCard[]
  notes?: string
  raw: string
}

export interface PresentationData {
  title: string
  slides: Slide[]
}

const LAYOUT_REGEX = /<!--\s*layout:\s*(hero|cards|split|standard)\s*-->/i
const NOTES_REGEX = /<!--\s*notes:\s*([\s\S]*?)\s*-->/i

function cleanSlideTitle(rawTitle: string): string {
  // Strip "Slide 1:", "Diapositiva 2 -", etc.
  return rawTitle.replace(/^(?:slide|diapositiva)\s*\d+[:\-.]?\s*/i, '').trim() || rawTitle.trim()
}

function parseCards(content: string): SlideCard[] {
  const cards: SlideCard[] = []
  const cardChunks = content.split(/(?=^###\s+)/m)

  for (const chunk of cardChunks) {
    const match = /^###\s+([^\n]+)\n?([\s\S]*)/.exec(chunk.trim())
    if (match && match[1]) {
      const headerRaw = match[1].trim()
      const body = match[2]?.trim() || ''

      // Check if header contains a badge e.g. "PostgreSQL [SSOT]"
      const badgeMatch = /\[([^\]]+)\]/.exec(headerRaw)
      const badge = badgeMatch?.[1] ? badgeMatch[1] : undefined
      const title = headerRaw.replace(/\[[^\]]+\]/, '').trim()

      cards.push({
        title,
        content: body,
        badge
      })
    }
  }

  return cards
}

function parseBullets(content: string): string[] {
  const bullets: string[] = []
  const lines = content.split('\n')

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      bullets.push(trimmed.slice(2).trim())
    }
  }

  return bullets
}

function parseSingleSlide(rawChunk: string, slideIndex: number): Slide | null {
  const trimmed = rawChunk.trim()
  if (!trimmed) return null

  // Extract layout comment
  const layoutMatch = LAYOUT_REGEX.exec(trimmed)
  let layout: 'hero' | 'cards' | 'split' | 'standard' | undefined = layoutMatch?.[1]
    ? (layoutMatch[1].toLowerCase() as 'hero' | 'cards' | 'split' | 'standard')
    : undefined

  // Extract presenter notes
  const notesMatch = NOTES_REGEX.exec(trimmed)
  const notes = notesMatch?.[1] ? notesMatch[1].trim() : undefined

  // Clean raw chunk removing comments for body processing
  const cleanChunk = trimmed
    .replace(LAYOUT_REGEX, '')
    .replace(NOTES_REGEX, '')
    .trim()

  // Extract Title (## or first line)
  let title = `Diapositiva ${slideIndex}`
  let remainingBody = cleanChunk

  const titleMatch = /^##\s+([^\n]+)/m.exec(cleanChunk)
  if (titleMatch?.[1]) {
    title = cleanSlideTitle(titleMatch[1])
    remainingBody = cleanChunk.replace(titleMatch[0], '').trim()
  } else {
    // If no ##, check first non-empty line
    const firstLine = cleanChunk.split('\n')[0]?.trim() || ''
    if (firstLine.startsWith('#')) {
      title = cleanSlideTitle(firstLine.replace(/^#+\s*/, ''))
      remainingBody = cleanChunk.slice(firstLine.length).trim()
    }
  }

  // Extract Subtitle (> blockquote)
  let subtitle: string | undefined
  const subtitleMatch = /(?:^|\n)>\s*([^\n]+)/.exec(remainingBody)
  if (subtitleMatch?.[1]) {
    subtitle = subtitleMatch[1].trim()
    remainingBody = remainingBody.replace(subtitleMatch[0], '').trim()
  }

  // Extract Cards (###)
  const cards = parseCards(remainingBody)

  // Remove card sections from remainingBody so bullets inside cards are not duplicated
  let bodyForBullets = remainingBody
  if (cards.length > 0) {
    const firstCardIdx = remainingBody.search(/^###\s+/m)
    bodyForBullets = firstCardIdx >= 0 ? remainingBody.slice(0, firstCardIdx) : ''
  }

  // Extract Bullets
  const bullets = parseBullets(bodyForBullets)

  // Auto infer layout if not specified
  if (!layout) {
    if (cards.length > 0) {
      layout = 'cards'
    } else if (slideIndex === 1 && (subtitle || bullets.length <= 3)) {
      layout = 'hero'
    } else {
      layout = 'standard'
    }
  }

  return {
    index: slideIndex,
    title,
    subtitle,
    layout,
    bullets,
    cards,
    notes,
    raw: trimmed
  }
}

/**
 * Parses markdown presentation text into structured slides.
 */
export function parsePresentation(rawContent: string): PresentationData {
  if (!rawContent?.trim()) {
    return {
      title: 'Presentación',
      slides: []
    }
  }

  const trimmed = rawContent.trim()

  // 1. Extract Presentation Title from # Title (if present at top)
  let presentationTitle = 'Presentación'
  let contentWithoutMainTitle = trimmed

  const mainTitleMatch = /^#\s+([^\n]+)/m.exec(trimmed)
  if (mainTitleMatch && mainTitleMatch[1]) {
    presentationTitle = mainTitleMatch[1].trim()
    contentWithoutMainTitle = trimmed.replace(mainTitleMatch[0], '').trim()
  }

  // 2. Split into slide chunks
  // Check if slides are delimited by `---`
  let rawSlides: string[] = []

  if (contentWithoutMainTitle.includes('---')) {
    rawSlides = contentWithoutMainTitle
      .split(/\n---\s*(?:\n|$)/)
      .map(s => s.trim())
      .filter(Boolean)
  } else if (/^##\s+(?:slide|diapositiva|\w+)/im.test(contentWithoutMainTitle)) {
    // Legacy / fallback splitting on `## `
    const chunks = contentWithoutMainTitle.split(/(?=^##\s+)/m)
    rawSlides = chunks.map(s => s.trim()).filter(Boolean)
  } else {
    // Single slide
    rawSlides = [contentWithoutMainTitle]
  }

  const slides: Slide[] = []
  let slideCounter = 1

  for (const rawSlide of rawSlides) {
    const parsed = parseSingleSlide(rawSlide, slideCounter)
    if (parsed) {
      slides.push(parsed)
      slideCounter++
    }
  }

  return {
    title: presentationTitle,
    slides
  }
}
