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
    // Format bold **text**
    const formatted = escapeHtml(b).replace(/\*\*([^*]+)\*\*/g, '<strong class="text-cyan-300 font-bold">$1</strong>')
    return `<li class="flex items-start gap-2.5 my-2 text-slate-200 text-base md:text-lg">
      <span class="inline-block w-2 h-2 mt-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(0,229,255,0.6)] shrink-0"></span>
      <span>${formatted}</span>
    </li>`
  }).join('')
  return `<ul class="list-none p-0 my-3">${items}</ul>`
}

function getGridColsClass(count: number): string {
  if (count === 2) return 'grid-cols-1 md:grid-cols-2'
  if (count >= 3) return 'grid-cols-1 md:grid-cols-3'
  return 'grid-cols-1'
}

function renderCardsHtml(cards: Slide['cards']): string {
  if (!cards.length) return ''
  const items = cards.map(c => {
    const formattedContent = escapeHtml(c.content)
      .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-cyan-300 font-bold">$1</strong>')
      .replaceAll('\n- ', '<br/>• ')
      .replace(/^- /g, '• ')

    const badgeHtml = c.badge
      ? `<span class="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/40 text-[11px] font-mono font-bold text-cyan-300 uppercase">${escapeHtml(c.badge)}</span>`
      : ''

    return `<div class="bg-[#050b18]/80 border border-cyan-500/30 rounded-xl p-5 shadow-[0_0_20px_rgba(0,229,255,0.06)] flex flex-col justify-between hover:border-cyan-400 transition-colors">
      <div>
        <div class="flex items-center justify-between gap-2 mb-2.5 border-b border-cyan-500/20 pb-2">
          <h4 class="text-base md:text-lg font-mono font-bold text-cyan-200 uppercase">${escapeHtml(c.title)}</h4>
          ${badgeHtml}
        </div>
        <p class="text-slate-300 text-sm md:text-base leading-relaxed whitespace-pre-line">${formattedContent}</p>
      </div>
    </div>`
  }).join('')

  const gridCols = getGridColsClass(cards.length)
  return `<div class="grid ${gridCols} gap-4 my-4 w-full">${items}</div>`
}

function renderSlideHtml(slide: Slide): string {
  const subtitleHtml = slide.subtitle
    ? `<div class="p-3.5 my-3 bg-cyan-950/30 border-l-4 border-cyan-400 rounded-r-lg text-slate-300 text-base md:text-lg italic font-sans">
        ${escapeHtml(slide.subtitle)}
      </div>`
    : ''

  const bulletsHtml = renderBulletsHtml(slide.bullets)
  const cardsHtml = renderCardsHtml(slide.cards)

  let layoutClass = 'flex flex-col justify-center'
  if (slide.layout === 'hero') {
    layoutClass = 'flex flex-col justify-center items-center text-center'
  }

  return `
    <section class="slide-item ${layoutClass}" data-slide="${slide.index}">
      <div class="w-full max-w-4xl mx-auto">
        <div class="mb-4">
          <span class="text-xs font-mono font-bold tracking-widest text-cyan-400 uppercase">Diapositiva ${slide.index}</span>
          <h2 class="text-2xl md:text-4xl font-mono font-bold text-white tracking-wide mt-1 uppercase text-shadow-glow">
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
  <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
  <style>
    body {
      background-color: #030712;
      color: #f1f5f9;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
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
      box-sizing: border-box;
      animation: fadeIn 0.3s ease-out;
    }
    .slide-item.active {
      display: flex;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: scale(0.98); }
      to { opacity: 1; transform: scale(1); }
    }
    .text-shadow-glow {
      text-shadow: 0 0 15px rgba(0, 229, 255, 0.4);
    }
    @media print {
      body {
        overflow: visible;
        background: #ffffff !important;
        color: #000000 !important;
      }
      .controls, .nav-bar { display: none !important; }
      .slide-stage { display: block; height: auto; }
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
    }
  </style>
</head>
<body>
  <div class="slide-stage">
    ${slidesHtml}

    <!-- Top Branding & Slide Counter -->
    <header class="controls fixed top-4 left-6 right-6 flex items-center justify-between text-xs font-mono text-cyan-400/80 z-50">
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></span>
        <span class="font-bold tracking-wider uppercase text-cyan-300">${title}</span>
      </div>
      <div class="bg-[#050b18]/80 border border-cyan-500/30 rounded-lg px-3 py-1 text-slate-300">
        <span id="current-slide">1</span> / <span>${totalSlides}</span>
      </div>
    </header>

    <!-- Bottom Navigation Bar -->
    <nav class="nav-bar fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 bg-[#050b18]/90 border border-cyan-500/40 rounded-xl px-4 py-2 shadow-2xl z-50">
      <button id="prev-btn" class="px-3 py-1 rounded bg-[#03060c] border border-cyan-500/40 text-cyan-200 hover:text-white cursor-pointer transition-colors font-mono text-xs">
        ◀ Anterior
      </button>
      <div id="dots-container" class="flex items-center gap-1.5 px-2"></div>
      <button id="next-btn" class="px-3 py-1 rounded bg-cyan-500/20 border border-cyan-400 text-cyan-300 hover:bg-cyan-500/30 cursor-pointer transition-colors font-mono text-xs font-bold">
        Siguiente ▶
      </button>
      <button id="fullscreen-btn" class="ml-2 px-2.5 py-1 rounded bg-[#03060c] border border-space-700 text-slate-300 hover:text-white cursor-pointer transition-colors font-mono text-xs" title="Pantalla Completa (F)">
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
          dotsContainer.innerHTML = '';
          for (let i = 1; i <= total; i++) {
            const dot = document.createElement('span');
            dot.className = 'w-2 h-2 rounded-full cursor-pointer transition-all ' +
              (i === currentIdx ? 'bg-cyan-400 scale-125 shadow-[0_0_8px_rgba(0,229,255,0.8)]' : 'bg-slate-600 hover:bg-slate-400');
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

