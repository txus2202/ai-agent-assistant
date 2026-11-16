---
type: feature_spec
status: implemented
created: 2026-09-19
tags: [backend, upload, routing, phase4, atenea]
---

# Feature: Direct Agent Invocation & File Upload

## 1. Description
Allow users to upload files and route requests directly to a specific sub-agent or service (e.g., Learning Agent) without passing through the full Supervisor debate flow.

## 2. Requirements
- Expose `POST /api/upload` to handle file uploads (multipart), save to a temporary directory, enforce a 50MB limit, and return the temporary file path.
- The `target_agent` and `attachments` fields must be parsed from the initial WS `START` message.
- If `target_agent == 'supervisor'`, run the normal debate flow.
- If `target_agent == 'learning'`, instantiate `LearnFromSource` for each attachment directly and return the results as WS events.
- If `target_agent` is another specific role, invoke `SubAgentRunner.run()` directly for that role.

## 3. Architecture
- **Presentation**: `routes/upload.py` (REST) and `routes/debate.py` (WS).
- **Application**: Reuse `LearnFromSource.run()` and `SubAgentRunner.run()`.

## 4. Test Plan (TDD)
- `test_upload_api.py`: Verify file size limits, saving, and return paths.
- `test_debate_ws_routing.py`: Verify that specifying `target_agent: "learning"` successfully calls `LearnFromSource` and returns `AGENT_COMPLETED` and `DONE`. Verify that specifying a direct sub-agent role runs only that sub-agent.
