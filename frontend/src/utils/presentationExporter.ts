import type { PresentationData, Slide } from './slideParser'
import PptxGenJS from 'pptxgenjs'

function escapeHtml(str: string): string {
  return str
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function renderBulletsHtml(bullets: string[]): string {
  if (!bullets.length) return ''
  const items = bullets.map(b => {
    const formatted = escapeHtml(b).replace(/\*\*([^*]+)\*\*/g, '<strong class="pres-bold">$1</strong>')
    return `<li class="pres-bullet-item">
      <span class="pres-bullet-dot"></span>
      <span>${formatted}</span>
    </li>`
  }).join('')
  return `<ul class="pres-bullet-list">${items}</ul>`
}

function getGridColsClass(count: number): string {
  if (count === 2) return 'pres-grid-2'
  if (count >= 3) return 'pres-grid-3'
  return 'pres-grid-1'
}

function renderCardsHtml(cards: Slide['cards']): string {
  if (!cards.length) return ''
  const items = cards.map(c => {
    const formattedContent = escapeHtml(c.content)
      .replace(/\*\*([^*]+)\*\*/g, '<strong class="pres-bold">$1</strong>')
      .replaceAll('\n- ', '<br/>• ')
      .replace(/^- /g, '• ')

    const badgeHtml = c.badge
      ? `<span class="pres-card-badge">${escapeHtml(c.badge)}</span>`
      : ''

    return `<div class="pres-card">
      <div>
        <div class="pres-card-header">
          <h4 class="pres-card-title">${escapeHtml(c.title)}</h4>
          ${badgeHtml}
        </div>
        <p class="pres-card-body">${formattedContent}</p>
      </div>
    </div>`
  }).join('')

  const gridCols = getGridColsClass(cards.length)
  return `<div class="pres-grid ${gridCols}">${items}</div>`
}

function renderSlideHtml(slide: Slide): string {
  const subtitleHtml = slide.subtitle
    ? `<div class="pres-subtitle">${escapeHtml(slide.subtitle)}</div>`
    : ''

  const bulletsHtml = renderBulletsHtml(slide.bullets)
  const cardsHtml = renderCardsHtml(slide.cards)

  const layoutClass = slide.layout === 'hero' ? 'pres-slide-content pres-layout-hero' : 'pres-slide-content'

  return `
    <section class="slide-item ${layoutClass}" data-slide="${slide.index}">
      <div class="pres-slide-inner">
        <div class="pres-slide-header">
          <span class="pres-slide-kicker">Diapositiva ${slide.index}</span>
          <h2 class="pres-slide-title text-shadow-glow">
            ${escapeHtml(slide.title)}
          </h2>
        </div>
        ${subtitleHtml}
        ${cardsHtml}
        ${bulletsHtml}
      </div>
    </section>
  `
}

export function generateStandalonePresentationHtml(data: PresentationData): string {
  const title = escapeHtml(data.title || 'Presentación Atenea')
  const slidesHtml = data.slides.map(renderSlideHtml).join('\n')
  const totalSlides = data.slides.length

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body {
      background-color: #030712;
      color: #f1f5f9;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      overflow: hidden;
    }
    .slide-stage {
      width: 100vw;
      height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      padding: 1rem;
    }
    .slide-item {
      display: none;
      width: 90vw;
      max-width: 1100px;
      min-height: 580px;
      aspect-ratio: 16 / 9;
      background: #080f20;
      border: 1px solid rgba(0, 229, 255, 0.35);
      border-radius: 1.25rem;
      padding: 3rem;
      box-shadow: 0 0 50px rgba(0, 229, 255, 0.15);
      animation: fadeIn 0.3s ease-out;
      overflow-y: auto;
    }
    .slide-item.active { display: flex; }
    .pres-slide-content { flex-direction: column; justify-content: center; }
    .pres-layout-hero { align-items: center; text-align: center; }
    .pres-slide-inner { width: 100%; max-width: 56rem; margin-inline: auto; }
    .pres-slide-header { margin-bottom: 1rem; }
    .pres-slide-kicker {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #22d3ee;
    }
    .pres-slide-title {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: clamp(1.5rem, 3vw, 2.25rem);
      font-weight: 700;
      color: #ffffff;
      letter-spacing: 0.025em;
      text-transform: uppercase;
      margin: 0.25rem 0 0;
    }
    .text-shadow-glow { text-shadow: 0 0 15px rgba(0, 229, 255, 0.4); }
    .pres-subtitle {
      padding: 0.875rem;
      margin-block: 0.75rem;
      background: rgba(8, 51, 68, 0.3);
      border-left: 4px solid #22d3ee;
      border-radius: 0 0.5rem 0.5rem 0;
      color: #cbd5e1;
      font-size: 1.0625rem;
      font-style: italic;
    }
    .pres-bullet-list { list-style: none; padding: 0; margin-block: 0.75rem; }
    .pres-bullet-item {
      display: flex;
      align-items: flex-start;
      gap: 0.625rem;
      margin-block: 0.5rem;
      color: #e2e8f0;
      font-size: 1.0625rem;
      line-height: 1.5;
    }
    .pres-bullet-dot {
      display: inline-block;
      width: 0.5rem;
      height: 0.5rem;
      margin-top: 0.5rem;
      border-radius: 9999px;
      background-color: #22d3ee;
      box-shadow: 0 0 8px rgba(0, 229, 255, 0.6);
      flex-shrink: 0;
    }
    .pres-bold { color: #67e8f9; font-weight: 700; }
    .pres-grid { display: grid; gap: 1rem; margin-block: 1rem; width: 100%; grid-template-columns: 1fr; }
    @media (min-width: 768px) {
      .pres-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .pres-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
    .pres-card {
      background: rgba(5, 11, 24, 0.8);
      border: 1px solid rgba(6, 182, 212, 0.3);
      border-radius: 0.75rem;
      padding: 1.25rem;
      box-shadow: 0 0 20px rgba(0, 229, 255, 0.06);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: border-color 0.2s ease;
    }
    .pres-card:hover { border-color: #22d3ee; }
    .pres-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
      margin-bottom: 0.625rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid rgba(6, 182, 212, 0.2);
    }
    .pres-card-title {
      margin: 0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 1rem;
      font-weight: 700;
      color: #a5f3fc;
      text-transform: uppercase;
    }
    .pres-card-badge {
      padding: 0.125rem 0.5rem;
      border-radius: 0.25rem;
      background: rgba(8, 51, 68, 0.8);
      border: 1px solid rgba(6, 182, 212, 0.4);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 11px;
      font-weight: 700;
      color: #67e8f9;
      text-transform: uppercase;
    }
    .pres-card-body {
      margin: 0;
      color: #cbd5e1;
      font-size: 0.9375rem;
      line-height: 1.625;
      white-space: pre-line;
    }
    .controls {
      position: fixed;
      top: 1rem;
      left: 1.5rem;
      right: 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.75rem;
      color: rgba(34, 211, 238, 0.85);
      z-index: 50;
    }
    .pres-brand { display: flex; align-items: center; gap: 0.5rem; }
    .pres-brand-dot {
      width: 0.625rem;
      height: 0.625rem;
      border-radius: 9999px;
      background-color: #22d3ee;
      animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }
    .pres-brand-title { font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: #67e8f9; }
    .pres-counter {
      background: rgba(5, 11, 24, 0.8);
      border: 1px solid rgba(6, 182, 212, 0.3);
      border-radius: 0.5rem;
      padding: 0.25rem 0.75rem;
      color: #cbd5e1;
    }
    .nav-bar {
      position: fixed;
      bottom: 1.5rem;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 0.75rem;
      background: rgba(5, 11, 24, 0.92);
      border: 1px solid rgba(6, 182, 212, 0.4);
      border-radius: 0.75rem;
      padding: 0.5rem 1rem;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
      z-index: 50;
    }
    .pres-btn {
      padding: 0.25rem 0.75rem;
      border-radius: 0.25rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.75rem;
      cursor: pointer;
      transition: background-color 0.2s, color 0.2s;
    }
    .pres-btn-prev {
      background: #03060c;
      border: 1px solid rgba(6, 182, 212, 0.4);
      color: #a5f3fc;
    }
    .pres-btn-prev:hover { color: #ffffff; }
    .pres-btn-next {
      background: rgba(6, 182, 212, 0.2);
      border: 1px solid #22d3ee;
      color: #67e8f9;
      font-weight: 700;
    }
    .pres-btn-next:hover { background: rgba(6, 182, 212, 0.32); }
    .pres-btn-fullscreen {
      margin-left: 0.5rem;
      padding: 0.25rem 0.625rem;
      background: #03060c;
      border: 1px solid #334155;
      color: #cbd5e1;
    }
    .pres-btn-fullscreen:hover { color: #ffffff; }
    .pres-dots { display: flex; align-items: center; gap: 0.375rem; padding-inline: 0.5rem; }
    .pres-dot {
      width: 0.5rem;
      height: 0.5rem;
      border-radius: 9999px;
      cursor: pointer;
      background-color: #475569;
      transition: transform 0.2s, background-color 0.2s;
    }
    .pres-dot:hover { background-color: #94a3b8; }
    .pres-dot.is-active {
      background-color: #22d3ee;
      transform: scale(1.25);
      box-shadow: 0 0 8px rgba(0, 229, 255, 0.8);
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: scale(0.98); }
      to { opacity: 1; transform: scale(1); }
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    @media print {
      body {
        overflow: visible;
        background: #ffffff !important;
        color: #000000 !important;
      }
      .controls, .nav-bar { display: none !important; }
      .slide-stage { display: block; height: auto; padding: 0; }
      .slide-item {
        display: block !important;
        page-break-after: always;
        break-after: page;
        margin: 2rem auto;
        border: 1px solid #ccc;
        box-shadow: none;
        background: #f8fafc !important;
        color: #000 !important;
      }
      .pres-slide-title, .pres-card-title, .pres-bullet-item, .pres-card-body { color: #0f172a !important; }
      .pres-card { background: #ffffff !important; border-color: #cbd5e1 !important; box-shadow: none !important; }
    }
  </style>
</head>
<body>
  <div class="slide-stage">
    ${slidesHtml}

    <!-- Top Branding & Slide Counter -->
    <header class="controls">
      <div class="pres-brand">
        <span class="pres-brand-dot"></span>
        <span class="pres-brand-title">${title}</span>
      </div>
      <div class="pres-counter">
        <span id="current-slide">1</span> / <span>${totalSlides}</span>
      </div>
    </header>

    <!-- Bottom Navigation Bar -->
    <nav class="nav-bar">
      <button id="prev-btn" class="pres-btn pres-btn-prev">
        ◀ Anterior
      </button>
      <div id="dots-container" class="pres-dots"></div>
      <button id="next-btn" class="pres-btn pres-btn-next">
        Siguiente ▶
      </button>
      <button id="fullscreen-btn" class="pres-btn pres-btn-fullscreen" title="Pantalla Completa (F)">
        ⛶
      </button>
    </nav>
  </div>

  <script>
    (function() {
      let currentIdx = 1;
      const total = ${totalSlides};
      const slides = document.querySelectorAll('.slide-item');
      const currentEl = document.getElementById('current-slide');
      const dotsContainer = document.getElementById('dots-container');

      function updateSlide(newIdx) {
        if (newIdx < 1 || newIdx > total) return;
        currentIdx = newIdx;
        slides.forEach(s => s.classList.remove('active'));
        const target = document.querySelector('.slide-item[data-slide="' + currentIdx + '"]');
        if (target) target.classList.add('active');
        if (currentEl) currentEl.textContent = currentIdx;

        // Update dots
        if (dotsContainer) {
          dotsContainer.replaceChildren();
          for (let i = 1; i <= total; i++) {
            const dot = document.createElement('span');
            dot.className = i === currentIdx ? 'pres-dot is-active' : 'pres-dot';
            dot.onclick = () => updateSlide(i);
            dotsContainer.appendChild(dot);
          }
        }
      }

      document.getElementById('prev-btn')?.addEventListener('click', () => updateSlide(currentIdx - 1));
      document.getElementById('next-btn')?.addEventListener('click', () => updateSlide(currentIdx + 1));

      document.getElementById('fullscreen-btn')?.addEventListener('click', () => {
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen().catch(() => {});
        } else {
          document.exitFullscreen().catch(() => {});
        }
      });

      window.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
          updateSlide(currentIdx + 1);
        } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
          updateSlide(currentIdx - 1);
        } else if (e.key.toLowerCase() === 'f') {
          if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
          } else {
            document.exitFullscreen().catch(() => {});
          }
        }
      });

      updateSlide(1);
    })();
  </script>
</body>
</html>`
}

export function downloadPresentationHtml(data: PresentationData, filename?: string): void {
  try {
    const htmlContent = generateStandalonePresentationHtml(data)
    const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const safeName = (filename || data.title || 'presentacion').toLowerCase().replace(/[^a-z0-9_-]/g, '_')
    link.download = `${safeName}.html`
    document.body.appendChild(link)
    link.click()
    setTimeout(() => {
      link.remove()
      URL.revokeObjectURL(url)
    }, 1500)
  } catch (err) {
    console.error('Failed to download presentation HTML:', err)
  }
}

export function downloadPresentationMarkdown(rawContent: string, filename?: string): void {
  try {
    const blob = new Blob([rawContent], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const safeName = (filename || 'presentacion').toLowerCase().replace(/[^a-z0-9_-]/g, '_')
    link.download = `${safeName}.md`
    document.body.appendChild(link)
    link.click()
    setTimeout(() => {
      link.remove()
      URL.revokeObjectURL(url)
    }, 1500)
  } catch (err) {
    console.error('Failed to download presentation markdown:', err)
  }
}

function renderPptxSubtitle(
  pSlide: ReturnType<PptxGenJS['addSlide']>,
  pres: PptxGenJS,
  subtitle: string,
  isHero: boolean,
  currentY: number,
  marginX: number,
  contentWidth: number
): number {
  const subH = 0.6
  pSlide.addShape(pres.ShapeType.rect, {
    x: marginX,
    y: currentY,
    w: contentWidth,
    h: subH,
    fill: { color: '081C38' },
    line: { color: '00E5FF', width: 1 }
  })

  pSlide.addText(subtitle, {
    x: marginX + 0.2,
    y: currentY,
    w: contentWidth - 0.4,
    h: subH,
    fontSize: 11,
    fontFace: 'Arial',
    color: 'BAE6FD',
    italic: true,
    valign: 'middle',
    align: isHero ? 'center' : 'left',
    fit: 'shrink'
  })

  return currentY + subH + 0.25
}

function calculatePptxContentHeights(
  hasCards: boolean,
  hasBullets: boolean,
  availableHeight: number,
  currentY: number
): { cardsHeight: number; bulletsHeight: number; bulletsY: number } {
  if (hasCards && hasBullets) {
    const cardsHeight = Math.min(2.8, (availableHeight - 0.2) * 0.52)
    const bulletsHeight = availableHeight - cardsHeight - 0.2
    return { cardsHeight, bulletsHeight, bulletsY: currentY + cardsHeight + 0.2 }
  }
  if (hasCards) {
    return { cardsHeight: Math.min(availableHeight, 4.2), bulletsHeight: 0, bulletsY: currentY }
  }
  if (hasBullets) {
    return { cardsHeight: 0, bulletsHeight: availableHeight, bulletsY: currentY }
  }
  return { cardsHeight: 0, bulletsHeight: 0, bulletsY: currentY }
}

function renderPptxCards(
  pSlide: ReturnType<PptxGenJS['addSlide']>,
  pres: PptxGenJS,
  cards: Slide['cards'],
  currentY: number,
  cardsHeight: number,
  marginX: number,
  contentWidth: number
): void {
  const count = cards.length
  if (count === 0) return

  const gap = count === 2 ? 0.4 : 0.3
  const cardWidth = (contentWidth - gap * (count - 1)) / count

  cards.forEach((card, idx) => {
    const cardX = marginX + idx * (cardWidth + gap)

    pSlide.addShape(pres.ShapeType.rect, {
      x: cardX,
      y: currentY,
      w: cardWidth,
      h: cardsHeight,
      fill: { color: '0A162B' },
      line: { color: '1E3A5F', width: 1 }
    })

    const titleText = card.badge ? `${card.title.toUpperCase()}  [${card.badge}]` : card.title.toUpperCase()
    pSlide.addText(titleText, {
      x: cardX + 0.15,
      y: currentY + 0.12,
      w: cardWidth - 0.3,
      h: 0.38,
      fontSize: count >= 3 ? 11 : 12,
      fontFace: 'Arial',
      color: '00E5FF',
      bold: true,
      fit: 'shrink'
    })

    const cleanContent = card.content.replace(/\*\*([^*]+)\*\*/g, '$1')
    pSlide.addText(cleanContent, {
      x: cardX + 0.15,
      y: currentY + 0.52,
      w: cardWidth - 0.3,
      h: Math.max(0.8, cardsHeight - 0.62),
      fontSize: count >= 3 ? 9.5 : 10.5,
      fontFace: 'Arial',
      color: 'E2E8F0',
      valign: 'top',
      lineSpacing: 16,
      fit: 'shrink'
    })
  })
}

function getBulletFontSize(isHero: boolean, bulletCount: number): number {
  if (isHero) return 13
  return bulletCount > 5 ? 11 : 12.5
}

function renderPptxBullets(
  pSlide: ReturnType<PptxGenJS['addSlide']>,
  bullets: string[],
  isHero: boolean,
  bulletsY: number,
  bulletsHeight: number,
  marginX: number,
  contentWidth: number
): void {
  const bulletCount = bullets.length
  if (bulletCount === 0) return

  const fontSize = getBulletFontSize(isHero, bulletCount)
  const bulletsText = bullets.map(b => ({
    text: b.replace(/\*\*([^*]+)\*\*/g, '$1'),
    options: {
      bullet: true,
      color: 'E2E8F0',
      fontSize,
      breakLine: true
    }
  }))

  pSlide.addText(bulletsText, {
    x: isHero ? marginX + 1.2 : marginX,
    y: bulletsY,
    w: isHero ? contentWidth - 2.4 : contentWidth,
    h: bulletsHeight,
    valign: 'top',
    lineSpacing: bulletCount > 5 ? 18 : 22,
    align: isHero ? 'center' : 'left',
    fit: 'shrink'
  })
}

function renderPptxNotes(
  pSlide: ReturnType<PptxGenJS['addSlide']>,
  notes: string,
  marginX: number,
  contentWidth: number
): void {
  pSlide.addText(`Nota: ${notes}`, {
    x: marginX,
    y: 6.95,
    w: contentWidth,
    h: 0.35,
    fontSize: 9,
    fontFace: 'Courier New',
    color: '64748B',
    fit: 'shrink'
  })
}

/**
 * Exports presentation slides to Microsoft PowerPoint (.pptx) format.
 * Applies Atenea's cybernetic theme with high contrast, elegant cards, and clear typography.
 * Uses LAYOUT_WIDE (13.33 x 7.5 inches) with strict bounding boxes and fit: 'shrink'
 * to guarantee no element or text overflows the slide.
 */
export async function exportPresentationPptx(data: PresentationData, filename?: string): Promise<void> {
  const pres = new PptxGenJS()
  pres.layout = 'LAYOUT_WIDE'

  const total = data.slides.length
  const marginX = 0.8
  const contentWidth = 11.73

  data.slides.forEach((slide) => {
    const pSlide = pres.addSlide()
    pSlide.background = { color: '050B18' }

    // Top Category Header
    pSlide.addText(`DIAPOSITIVA ${slide.index} / ${total}  |  ATENEA COUNCIL`, {
      x: marginX,
      y: 0.42,
      w: contentWidth,
      h: 0.3,
      fontSize: 9,
      fontFace: 'Courier New',
      color: '00E5FF',
      bold: true
    })

    const isHero = slide.layout === 'hero'
    const titleH = isHero ? 0.75 : 0.65

    // Slide Title
    pSlide.addText(slide.title.toUpperCase(), {
      x: marginX,
      y: 0.75,
      w: contentWidth,
      h: titleH,
      fontSize: isHero ? 26 : 21,
      fontFace: 'Arial',
      color: 'FFFFFF',
      bold: true,
      align: isHero ? 'center' : 'left',
      fit: 'shrink'
    })

    let currentY = 0.75 + titleH + 0.15

    if (slide.subtitle) {
      currentY = renderPptxSubtitle(pSlide, pres, slide.subtitle, isHero, currentY, marginX, contentWidth)
    }

    const hasNotes = Boolean(slide.notes)
    const maxBottom = hasNotes ? 6.75 : 7.05
    const availableHeight = Math.max(1.8, maxBottom - currentY)

    const hasCards = Boolean(slide.cards && slide.cards.length > 0)
    const hasBullets = Boolean(slide.bullets && slide.bullets.length > 0)

    const { cardsHeight, bulletsHeight, bulletsY } = calculatePptxContentHeights(
      hasCards,
      hasBullets,
      availableHeight,
      currentY
    )

    if (hasCards && slide.cards && slide.cards.length > 0) {
      renderPptxCards(pSlide, pres, slide.cards, currentY, cardsHeight, marginX, contentWidth)
    }

    if (hasBullets && slide.bullets && slide.bullets.length > 0) {
      renderPptxBullets(pSlide, slide.bullets, isHero, bulletsY, bulletsHeight, marginX, contentWidth)
    }

    if (slide.notes) {
      renderPptxNotes(pSlide, slide.notes, marginX, contentWidth)
    }
  })

  const safeName = (filename || data.title || 'presentacion').toLowerCase().replace(/[^a-z0-9_-]/g, '_')
  const fileName = `${safeName}.pptx`

  if (typeof window !== 'undefined' && typeof document !== 'undefined' && typeof pres.write === 'function') {
    try {
      const blobData = (await pres.write({ outputType: 'blob' })) as Blob
      const blob = new Blob([blobData], {
        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = fileName
      document.body.appendChild(link)
      link.click()
      setTimeout(() => {
        link.remove()
        URL.revokeObjectURL(url)
      }, 1500)
      return
    } catch (writeErr) {
      console.warn('pres.write blob download fallback to pres.writeFile:', writeErr)
    }
  }

  await pres.writeFile({ fileName })
}

