---
created: 2026-11-14
updated: 2026-11-14
type: spec
phase: 4
layer: cross-cutting
status: draft
category: meta-project
tags: [knowledge-base, domains, rag, hitl, metis, obsidian, tfm, ai-agent-assistant, atenea]
---

# Feature: Dynamic Knowledge Domains and Hierarchical Vault Architecture

**As an** IT architect or ATENEA operator
**I want to** organize the Obsidian knowledge vault into distinct hierarchical domains (Platform/TFM, Enterprise Architecture, Learned Knowledge, Deliberations) and dynamically create or select target domains during ingestion
**So that** knowledge retrieval is segregated without context contamination, the company's knowledge graph scales organically, and Metis (the learning agent) actively assists in categorizing and curating knowledge under Human-in-the-Loop supervision.

---

## 1. Problem Statement & Motivation

Prior to this feature, all learned documents and session summaries were dumped into a flat `learned/` directory, while platform specifications (`docs/features/`) were mixed with corporate architecture. This resulted in:
1. **Context Contamination:** The RAG retriever returned internal platform implementation details (e.g., FastAPI, Vue 3, WebSockets) when architects inquired about corporate standards for business microservices.
2. **Lack of Knowledge Governance (HITL):** The system ingested documents blindly without prompting the user to classify whether a document was an enterprise standard, external research, or project documentation.
3. **Static Taxonomy:** New architectural areas (e.g., FinOps, Data Engineering, Compliance) could not be established dynamically by either the user or Metis.

---

## 2. Vault Hierarchical Domain Topology

The vault is structured into four core namespaces, plus dynamically added custom domains:

| Domain Slug | Display Name | Purpose | Target Agent Consumers |
| :--- | :--- | :--- | :--- |
| `00_meta_project` | Plataforma & TFM | Documentación interna, specs y arquitectura de `ai-agent-assistant` y `ATENEA`. | Development & Evaluation |
| `01_enterprise_architecture` | Arquitectura Empresarial | Estándares técnicos corporativos, directrices de seguridad, stacks aprobados y ADRs de la empresa. | Hestia (Senior), Sphinx (Judge) |
| `learned` | Investigación y Aprendizaje | Documentación externa, manuales de proveedores cloud y whitepapers asimilados por Metis. | Ícaro (Innovator), Metis |
| `deliberations` | Actas y Deliberaciones | Síntesis de debates colegiados, acuerdos de arquitectura y minutas registradas por Calíope. | Atenea (Supervisor), All |
| `<custom_domain>` | Dominios Extensibles | Dominios creados bajo demanda por el usuario o sugeridos por Metis (ej. `04_data_ai_platform`). | Specific Specialists |

Every domain contains a root **Map of Content (`MOC_<Domain>.md`)** linked from the master dashboard `HOME.md`.

---

## 3. Architecture & Service Contracts

### 3.1 Domain Entity / Value Object

```python
@dataclass(frozen=True)
class KnowledgeDomain:
    id: str                  # e.g., "01_enterprise_architecture"
    name: str                # e.g., "Arquitectura Empresarial"
    description: str         # e.g., "Estándares corporativos y directrices aprobadas"
    path: str                # relative path from vault root
    moc_file: str            # relative path to the MOC file
    document_count: int = 0  # number of .md files inside
    is_system: bool = False  # True for core system domains
```

### 3.2 Domain Management Service

```python
class VaultDomainService:
    @staticmethod
    def list_domains(vault_root: Path) -> list[KnowledgeDomain]:
        """Scan vault_root and return all configured and discovered knowledge domains."""

    @staticmethod
    def create_domain(
        vault_root: Path,
        domain_id: str,
        name: str,
        description: str = "",
    ) -> KnowledgeDomain:
        """
        Create a new domain directory, initialize its MOC file,
        and update HOME.md with the new wikilink.
        """
```

### 3.3 Target Domain Ingestion Contract

`LearnFromSource.run` and `LearnFromSession.run` are enhanced with a `target_domain: str = "learned"` parameter:
- When a document is ingested, it is written to `vault_root / target_domain / {filename}`.
- The YAML frontmatter is automatically injected with `domain: {target_domain}`.
- If the domain has an associated MOC, an entry is appended or refreshed in the MOC.

---

## 4. API Endpoints

### 4.1 `GET /api/learning/domains`
Returns the list of available domains in the vault.
**Response (200 OK):**
```json
[
  {
    "id": "00_meta_project",
    "name": "Plataforma & TFM",
    "description": "Especificaciones y arquitectura de ai-agent-assistant",
    "path": "00_meta_project",
    "moc_file": "00_meta_project/MOC_Project_TFM.md",
    "document_count": 28,
    "is_system": true
  },
  {
    "id": "01_enterprise_architecture",
    "name": "Arquitectura Empresarial",
    "description": "Estándares técnicos y catálogo de tecnologías corporativas",
    "path": "01_enterprise_architecture",
    "moc_file": "01_enterprise_architecture/MOC_Enterprise_Architecture.md",
    "document_count": 8,
    "is_system": true
  },
  {
    "id": "learned",
    "name": "Investigación Externa",
    "description": "Conocimiento adquirido de fuentes externas (PDF/URL)",
    "path": "learned",
    "moc_file": "learned/MOC_Learned_Knowledge.md",
    "document_count": 10,
    "is_system": true
  },
  {
    "id": "deliberations",
    "name": "Actas y Deliberaciones",
    "description": "Acuerdos y actas generadas por Calíope tras debates del consejo",
    "path": "deliberations",
    "moc_file": "deliberations/MOC_Deliberations.md",
    "document_count": 1,
    "is_system": true
  }
]
```

### 4.2 `POST /api/learning/domains`
Creates a new domain dynamically.
**Request Body:**
```json
{
  "id": "04_data_ai_platform",
  "name": "Plataforma de Datos e IA",
  "description": "Directrices de pipelines de datos, MLOps y gobierno de IA"
}
```
**Response (201 Created):** Returns the created `KnowledgeDomain`.

---

## 5. Metis Proactive Curation & HITL Protocol

When a user initiates learning (via WebSocket debate or HTTP session learning):
1. **Explicit Target:** If the user specifies the domain (e.g. *"Aprende esto como estándar corporativo"* or `#enterprise`), Metis routes directly to `01_enterprise_architecture/standards`.
2. **Ambiguous / Unclassified Ingestion:** If no domain is provided, Metis analyzes the content and prompts the user before persisting:
   > *"He analizado el documento '{title}'. Detecto que contiene directrices corporativas. ¿Deseas catalogarlo en 🏢 'Arquitectura Empresarial' (`01_enterprise_architecture`), en 🔬 'Investigación Externa' (`learned`), o prefieres crear un nuevo dominio?"*
3. **Domain Creation Proposal:** If Metis identifies a distinct thematic cluster not covered by existing domains, it suggests creating a new domain with a ready-to-approve slug and name.

---

## 6. Acceptance Criteria

- [x] **AC 1 (Domain Listing):** Calling `VaultDomainService.list_domains()` returns all core domains with accurate document counts.
- [x] **AC 2 (Domain Creation):** Calling `VaultDomainService.create_domain()` creates the folder, the `MOC_<Domain>.md`, and updates `HOME.md`.
- [x] **AC 3 (Targeted Ingestion):** `LearnFromSource.run()` saves the generated `.md` in the specified domain subfolder and persists `domain` in frontmatter.
- [x] **AC 4 (Backward Compatibility):** When no domain is passed, `LearnFromSource` defaults to `"learned"`, guaranteeing existing tests and scripts continue working.
- [x] **AC 5 (API Endpoints):** `GET /api/learning/domains` and `POST /api/learning/domains` respond with proper HTTP status codes and schemas.
- [x] **AC 6 (Multi-Category & Multi-Value RAG Filters):** `SearchFilter` and agent `rag_filter` declarations support single strings as well as lists of categories/types, translating to `$in` queries in ChromaDB.

---

## 7. Multi-Category & Multi-Value RAG Filtering Specification

To prevent context contamination while allowing agents to synthesize across boundaries:
1. `SearchFilter` supports `category` and `domain`, either as a single string (`$eq`) or as a sequence of strings (`$in`).
2. Agents in `agents.yaml` can declare either scalar values or lists under `rag_filter`:
   ```yaml
   rag_filter:
     category:
       - enterprise
       - external-learning
   ```
3. Mapping in vector store:
   - Scalar value `val`: `{"key": {"$eq": str(val)}}`
   - List `[val1, val2]`: `{"key": {"$in": [str(val1), str(val2)]}}`


