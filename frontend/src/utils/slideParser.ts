export interface SlideCard {
  title: string
  content: string
  badge?: string
}

export type SlideLayout = 'hero' | 'cards' | 'split' | 'standard'

export interface Slide {
  index: number
  title: string
  subtitle?: string
  layout: SlideLayout
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
const NOTES_COMMENT_START_REGEX = /<!--\s*notes:\s*/i

function extractNotes(content: string): { notes?: string; cleaned: string } {
  const match = NOTES_COMMENT_START_REGEX.exec(content)
  if (!match) {
    return { cleaned: content }
  }
  const contentStart = match.index + match[0].length
  const endComment = content.indexOf('-->', contentStart)
  if (endComment === -1) {
    return { cleaned: content }
  }
  const notes = content.slice(contentStart, endComment).trim()
  const cleaned = (content.slice(0, match.index) + content.slice(endComment + 3)).trim()
  return { notes: notes || undefined, cleaned }
}

function cleanSlideTitle(rawTitle: string): string {
  // Strip "Slide 1:", "Diapositiva 2 -", etc.
  return rawTitle.replace(/^(?:slide|diapositiva)\s*\d+[:\-.]?\s*/i, '').trim() || rawTitle.trim()
}

function parseCards(content: string): SlideCard[] {
  const cards: SlideCard[] = []
  const cardChunks = content.split(/(?=^###\s+)/m)

  for (const chunk of cardChunks) {
    const trimmedChunk = chunk.trim()
    if (!trimmedChunk.startsWith('###')) continue

    const firstNewline = trimmedChunk.indexOf('\n')
    const firstLine = firstNewline === -1 ? trimmedChunk : trimmedChunk.slice(0, firstNewline)
    const headerRaw = firstLine.replace(/^###\s+/, '').trim()
    if (!headerRaw) continue

    const body = firstNewline === -1 ? '' : trimmedChunk.slice(firstNewline + 1).trim()

    const openBracket = headerRaw.indexOf('[')
    const closeBracket = headerRaw.indexOf(']', openBracket)
    let badge: string | undefined
    let title = headerRaw

    if (openBracket !== -1 && closeBracket > openBracket) {
      badge = headerRaw.slice(openBracket + 1, closeBracket).trim()
      title = (headerRaw.slice(0, openBracket) + headerRaw.slice(closeBracket + 1)).trim()
    }

    cards.push({
      title,
      content: body,
      badge: badge || undefined,
    })
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

function extractSlideTitle(cleanChunk: string, slideIndex: number): { title: string; remainingBody: string } {
  const titleMatch = /^##\s+([^\n]+)/m.exec(cleanChunk)
  if (titleMatch?.[1]) {
    return {
      title: cleanSlideTitle(titleMatch[1]),
      remainingBody: cleanChunk.replace(titleMatch[0], '').trim()
    }
  }

  const firstLine = cleanChunk.split('\n')[0]?.trim() || ''
  if (firstLine.startsWith('#')) {
    return {
      title: cleanSlideTitle(firstLine.replace(/^#+\s*/, '')),
      remainingBody: cleanChunk.slice(firstLine.length).trim()
    }
  }

  return {
    title: `Diapositiva ${slideIndex}`,
    remainingBody: cleanChunk
  }
}

function resolveSlideLayout(
  explicitLayout: SlideLayout | undefined,
  slideIndex: number,
  cardsCount: number,
  hasSubtitle: boolean,
  bulletsCount: number
): SlideLayout {
  if (explicitLayout) return explicitLayout
  if (cardsCount > 0) return 'cards'
  if (slideIndex === 1 && (hasSubtitle || bulletsCount <= 3)) return 'hero'
  return 'standard'
}

function parseSingleSlide(rawChunk: string, slideIndex: number): Slide | null {
  const trimmed = rawChunk.trim()
  if (!trimmed) return null

  // Extract layout comment
  const layoutMatch = LAYOUT_REGEX.exec(trimmed)
  const explicitLayout = layoutMatch?.[1]
    ? (layoutMatch[1].toLowerCase() as SlideLayout)
    : undefined

  // Extract presenter notes without backtracking regex
  const { notes, cleaned: withoutNotes } = extractNotes(trimmed)

  // Clean raw chunk removing comments for body processing
  const cleanChunk = withoutNotes
    .replace(LAYOUT_REGEX, '')
    .trim()

  // Extract Title (## or first line)
  const { title, remainingBody: afterTitleBody } = extractSlideTitle(cleanChunk, slideIndex)
  let remainingBody = afterTitleBody

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
  const layout = resolveSlideLayout(explicitLayout, slideIndex, cards.length, Boolean(subtitle), bullets.length)

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
  if (mainTitleMatch?.[1]) {
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
