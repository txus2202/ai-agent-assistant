---
created: 2026-09-17
updated: 2026-09-17
type: spec
phase: 4
layer: presentation
status: draft
tags: [learning, pdf, url, upload, frontend, vue]
---

# Feature: Learning Agent UI

**As a** user
**I want** to submit a PDF file or a URL from the web interface
**So that** ATENEA learns from it and the new knowledge is immediately available for RAG retrieval.

## Context & Motivation

The backend `LearnFromSource` service already handles the full pipeline (Phase 3). This feature adds the HTTP endpoint to trigger it and the Vue 3 UI to interact with it.

## Backend: `POST /learn`

### PDF upload

```
POST /learn
Content-Type: multipart/form-data

Fields:
  file:       (binary) — the PDF file
  model_name: (str, optional, default from settings)
  provider:   (str, optional, default from settings)
```

### URL ingestion

```
POST /learn
Content-Type: application/json

{
  "url": "https://example.com/article",
  "model_name": "gemini-1.5-flash",
  "provider": "gemini"
}
```

### Response

```json
// 200 Success:
{
  "source": "https://example.com/article",
  "generated_file": "obsidian_vault/learned/2026-09-17_clean-architecture.md",
  "chunks_ingested": 5,
  "errors": []
}

// 200 with errors (extraction failed — no exception raised, consistent with LearnFromSource):
{
  "source": "/tmp/bad.pdf",
  "generated_file": null,
  "chunks_ingested": 0,
  "errors": ["corrupt PDF: ..."]
}

// 422: Missing required field
// 413: File too large (> 50 MB)
```

## Frontend: Learning Panel

> Note: exact visual design deferred to Stitch prototype analysis.
> The following defines the behaviour contract.

### States

```
IDLE        → Empty input. Two tabs: "PDF" and "URL".
UPLOADING   → Progress spinner visible. Input disabled.
SUCCESS     → Green banner: "✓ Learned from [source]. 5 chunks added to vault."
              Shows link to open the generated .md file path.
ERROR       → Red banner: "⚠ Could not extract content: [error message]"
              "Try again" button.
```

### PDF tab behaviour

- Drag & drop zone OR file picker (`.pdf` only, max 50 MB enforced client-side)
- On drop/select: show filename + file size
- "Learn" button triggers `POST /learn` multipart
- Progress: indeterminate spinner (no % — backend doesn't stream progress for `/learn`)

### URL tab behaviour

- Single text input: `placeholder="https://example.com/article"`
- Basic URL validation client-side (must start with `http://` or `https://`)
- "Learn" button triggers `POST /learn` JSON
- Same progress / success / error states as PDF tab

## Acceptance Criteria

### Scenario 1: PDF upload succeeds

```
Given a valid PDF file selected
When user clicks Learn
Then POST /learn is called with multipart/form-data
And success banner shows file name and chunk count
```

### Scenario 2: URL ingestion succeeds

```
Given valid URL "https://example.com"
When user clicks Learn
Then POST /learn is called with JSON body
And success banner shows URL and chunk count
```

### Scenario 3: File too large rejected client-side

```
Given a PDF > 50 MB selected
When user tries to drop it
Then error shown immediately (no HTTP call)
And banner: "File too large. Maximum is 50 MB."
```

### Scenario 4: Extraction failure shown gracefully

```
Given backend returns errors: ["corrupt PDF"]
When response arrives
Then error banner shown: "Could not extract content: corrupt PDF"
And no exception / crash in UI
```

### Scenario 5: Learn during debating is disabled

```
Given a debate is in progress (WebSocket open)
When user navigates to Learning panel
Then Learn button is disabled with tooltip "Please wait for the current debate to finish."
```

## Implementation Notes

- Backend route: `src/presentation/api/routes/learn.py`
- File size limit enforced with FastAPI's `UploadFile` + `request.headers["content-length"]`
- Max file size: 50 MB (configurable via `MAX_LEARN_FILE_MB` env var)
- PDF is saved to a temp directory, passed to `LearnFromSource`, then deleted
- Vue component: `LearnPanel.vue` with sub-components `PdfDropZone.vue` + `UrlInput.vue`
- The "debate in progress" state is tracked via a global Pinia store (`useDebateStore`)
