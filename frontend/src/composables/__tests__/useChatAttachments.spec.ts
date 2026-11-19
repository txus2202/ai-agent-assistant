import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { debateApiService } from '../../services/debateApiService'
import { useChatAttachments } from '../useChatAttachments'

describe('useChatAttachments', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads learning domains cleanly and falls back safely on error', async () => {
    const spy = vi
      .spyOn(debateApiService, 'listLearningDomains')
      .mockResolvedValueOnce([{ id: 'arch', name: 'Architecture' }])
      .mockRejectedValueOnce(new Error('Network down'))

    const attachments = useChatAttachments()
    await attachments.loadDomains()
    expect(attachments.availableDomains.value).toEqual([{ id: 'arch', name: 'Architecture' }])

    // Keep prior domains / do not throw if endpoint fails
    await attachments.loadDomains()
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('manages file additions, removals, clearing, and multi-file upload', async () => {
    const attachments = useChatAttachments()
    const f1 = new File(['a'], 'doc1.md')
    const f2 = new File(['b'], 'doc2.pdf')

    const mockInput = { files: [f1, f2] as unknown as FileList, value: 'C:\\fakepath\\doc' }
    attachments.handleFileChange({ target: mockInput } as unknown as Event)
    expect(attachments.selectedFiles.value).toHaveLength(2)
    expect(mockInput.value).toBe('')

    attachments.removeFile(0)
    expect(attachments.selectedFiles.value).toHaveLength(1)
    expect(attachments.selectedFiles.value[0]?.name).toBe('doc2.pdf')

    const uploadFn = vi.fn().mockResolvedValue('att-doc2')
    const singleRef = await attachments.uploadSelectedFiles(uploadFn)
    expect(singleRef).toBe('att-doc2')
    expect(uploadFn).toHaveBeenCalledWith(f2)

    attachments.selectedFiles.value = [f1, f2]
    uploadFn.mockResolvedValueOnce('att-1').mockResolvedValueOnce('att-2')
    const multiRefs = await attachments.uploadSelectedFiles(uploadFn)
    expect(multiRefs).toEqual(['att-1', 'att-2'])

    attachments.clearFiles()
    expect(attachments.selectedFiles.value).toHaveLength(0)
    expect(await attachments.uploadSelectedFiles(uploadFn)).toBeNull()
  })
})

