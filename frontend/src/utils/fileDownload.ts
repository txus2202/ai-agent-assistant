export function sanitizeFilename(raw?: string, fallback: string = 'archivo'): string {
  const cleaned = (raw || fallback)
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
    .slice(0, 30)
  return cleaned || fallback
}

export function downloadUrlFile(url: string, filename: string): void {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
}

export function downloadBlobFile(
  content: BlobPart,
  filename: string,
  mimeType: string,
): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  try {
    downloadUrlFile(url, filename)
  } finally {
    URL.revokeObjectURL(url)
  }
}

