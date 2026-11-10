# System Architecture

## Architectural Pattern

The system uses a **Modular Monolith** architecture based on **Clean Architecture** (Hexagonal Architecture / Ports and Adapters). The goal is to isolate business logic from implementation details (UI, Databases, External APIs).

# System Architecture

## Application Layers

1. **Domain:** Core entities (`ArchitectureSolution`, `Task`, `Agent`, `User`) and abstract interfaces (Ports like `ILLMProvider`, `IUserRepository`, `IPasswordHasher`, `ITokenService`). Zero framework dependencies.
2. **Application:** Use Cases (`GenerateArchitectureDesign`, `AuthService`). Coordinates business logic.
3. **Infrastructure:** Implements domain interfaces. Includes adapters for:
   - AI Providers: `GeminiAdapter`, `OpenAIAdapter`, `AnthropicAdapter` (routed via Google ADK / Langchain abstractions).
   - Databases: ChromaDB, Obsidian Local File System, SQLite and PostgreSQL repositories (`SqliteDebateRepository`, `SQLiteUserRepository`, `PostgreSQLUserRepository`).
   - Security: Argon2id password hashing (`Argon2idPasswordHasher`), HMAC-SHA256 JWT tokens (`JwtTokenService`).
   - Voice: Whisper.cpp, Piper.
4. **Presentation:** FastAPI controllers, WebSockets, Typer CLI, and the Vue 3 web client. Session management via HttpOnly cookies and Bearer tokens.

## Multimodal RAG Strategy

- **Text:** Local `.md` files are chunked and embedded directly into ChromaDB.
- **Images:** Architectural diagrams linked in Obsidian are passed to Gemini via a hidden prompt for textual transcription.

## Documentation Strategy

- **API Documentation:** FastAPI natively auto-generates OpenAPI/Swagger UI at the `/docs` endpoint.
- **Backend & Architecture:** **MkDocs (Material theme)** combined with `mkdocstrings` reads the Python codebase for docstrings and the Obsidian vault for architectural `.md` files, generating a unified static site.
- **Frontend:** **VitePress** is used to document Vue 3 components, Pinia state management, and WebSocket workflows.

## Development Methodology

- **SDD (Spec-Driven Development):** Features defined in `docs/features/*.md`.
- **TDD (Test-Driven Development):** Red-Green-Refactor cycles using Pytest.
