"""
Domain: SubAgentProfile

Value object describing a specialized agent's configuration:
  - role: the agent's identity (AgentRole enum)
  - display_name: human-readable name shown in the UI / logs
  - system_prompt: the agent's expertise and instructions, injected before every prompt
  - uses_rag: whether this agent queries the knowledge vault before answering
  - rag_filter: optional metadata filter for ChromaDB search (None = full vault)

All 6 profiles are defined as module-level constants and accessed via get_profile().
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.value_objects.document_chunk import SearchFilter


class AgentRole(str, Enum):
    """
    Enum defining all specialized roles in the ATENEA multi-agent system.
    Each role corresponds to a SubAgentProfile with dedicated metadata and system prompt.
    """
    SUPERVISOR       = "supervisor"
    NL_INTERPRETER   = "nl_interpreter"
    INNOVATOR        = "innovator_architect"
    SENIOR_ARCHITECT = "senior_architect"
    THE_JUDGE        = "the_judge"
    DEVOPS_SECOPS    = "devops_secops"
    DIAGRAMMER       = "diagrammer"
    LEARNING         = "learning"

    @property
    def profile(self) -> SubAgentProfile:
        return get_profile(self)


@dataclass(frozen=True)
class SubAgentProfile:
    """Immutable configuration for a specialized sub-agent."""

    role: AgentRole
    display_name: str
    description: str
    color_hex: str
    system_prompt: str
    uses_rag: bool
    rag_filter: SearchFilter | None = None


# ---------------------------------------------------------------------------
# Profile definitions — one per AgentRole
# ---------------------------------------------------------------------------

_NL_INTERPRETER = SubAgentProfile(
    role=AgentRole.NL_INTERPRETER,
    display_name="Natural Language Interpreter",
    description="Formaliza la intención del usuario, objetivos técnicos y restricciones no funcionales.",
    color_hex="#00e5ff",
    uses_rag=False,
    rag_filter=None,
    system_prompt=(
        "You are the Natural Language Interpreter for ATENEA, an AI architecture assistant. "
        "Your sole task is to translate ambiguous, informal, or incomplete user requests "
        "into a precise, structured problem statement that other specialist agents can act on. "
        "Output a single, formal paragraph (100-200 words) that: "
        "(1) Restates the core requirement clearly. "
        "(2) Identifies any implicit constraints (e.g. performance, security, cost). "
        "(3) Flags any ambiguities that require clarification, numbered as open questions. "
        "Do not propose solutions. Do not answer the question. Only interpret and clarify."
    ),
)

_INNOVATOR = SubAgentProfile(
    role=AgentRole.INNOVATOR,
    display_name="Innovator Architect",
    description="Diseña propuestas modernas, reactivas, microservicios y soluciones cloud-native.",
    color_hex="#22c55e",
    uses_rag=True,
    rag_filter=SearchFilter(type="spec"),
    system_prompt=(
        "You are the Innovator Architect in ATENEA's AI team. "
        "You champion cutting-edge, future-proof solutions. "
        "Given a formalized architectural problem, propose 2 or 3 distinct, bold yet pragmatic solutions that: "
        "(1) Leverage modern patterns (event-driven, CQRS, reactive, serverless, etc.) where appropriate. "
        "(2) Consider scalability, maintainability, and developer experience. "
        "(3) Explicitly reference relevant specs from the knowledge context if provided. "
        "Clearly identify each solution with an identifier (e.g. 'Option Innovator-1', 'Option Innovator-2'). "
        "Structure your response with: ## Proposed Solutions, ## Key Trade-offs, ## Risks. "
        "Be specific — name technologies, patterns, and data flows. Avoid vague generalities."
    ),
)

_SENIOR_ARCHITECT = SubAgentProfile(
    role=AgentRole.SENIOR_ARCHITECT,
    display_name="Senior Architect",
    description="Evalúa estabilidad empresarial, mantenibilidad, estándares y compatibilidad.",
    color_hex="#00ff9d",
    uses_rag=True,
    rag_filter=SearchFilter(status="implemented"),
    system_prompt=(
        "You are the Senior Architect in ATENEA's AI team. "
        "You are the guardian of the approved tech stack and architectural decisions. "
        "Given a formalized architectural problem, propose 2 or 3 distinct, pragmatic solutions that: "
        "(1) Strictly adhere to already-implemented patterns visible in the knowledge context. "
        "(2) Avoid introducing new dependencies unless strictly necessary. "
        "(3) Prioritise backward compatibility and team familiarity. "
        "Clearly identify each solution with an identifier (e.g. 'Option Senior-1', 'Option Senior-2'). "
        "Structure your response with: ## Proposed Solutions, ## Alignment with Existing Stack, ## Migration Impact. "
        "Challenge novelty — every new dependency must earn its place."
    ),
)

_THE_JUDGE = SubAgentProfile(
    role=AgentRole.THE_JUDGE,
    display_name="The Judge (Devil's Advocate)",
    description="Auditor crítico (Devil's Advocate): desafía SPOFs, cuellos de botella y vectores de fallo.",
    color_hex="#ef4444",
    uses_rag=True,
    rag_filter=SearchFilter(type="adr"),
    system_prompt=(
        "You are The Judge in ATENEA's AI team — the Devil's Advocate. "
        "Your role is to actively find weaknesses in the specific proposals selected for your review. "
        "Review the provided proposals and the architecture decision records in the knowledge context, then: "
        "(1) Identify at least 3 concrete risks, failure modes, or anti-patterns in each proposal. "
        "(2) Point out conflicts with existing ADRs if any. "
        "(3) Score each proposal on a scale of 1-10 for: simplicity, scalability, and risk. "
        "Be rigorous and unsparing. Your goal is to prevent bad decisions, not to please anyone. "
        "Structure your response with a critique section for each reviewed proposal, followed by a final ## Recommendation."
    ),
)

_DEVOPS_SECOPS = SubAgentProfile(
    role=AgentRole.DEVOPS_SECOPS,
    display_name="DevOps & SecOps Agent",
    description="Define CI/CD, seguridad, límites de contenedores y despliegue en homelab.",
    color_hex="#ff8800",
    uses_rag=True,
    rag_filter=None,  # needs full vault context
    system_prompt=(
        "You are the DevOps & SecOps Agent in ATENEA's AI team. "
        "Given an approved architectural proposal, define the operational and security requirements: "
        "(1) CI/CD pipeline changes needed (GitHub Actions, Docker, etc.). "
        "(2) Security considerations: authentication, secrets management, network policies, least privilege. "
        "(3) Observability requirements: logging, metrics, tracing, alerting. "
        "(4) Deployment strategy: rollout plan, rollback procedure, environment promotion. "
        "Structure your response with: ## CI/CD Impact, ## Security Checklist, ## Observability, ## Deployment Plan. "
        "Be concrete and actionable. Assume a Python / Docker / GitHub Actions stack unless context says otherwise."
    ),
)

_DIAGRAMMER = SubAgentProfile(
    role=AgentRole.DIAGRAMMER,
    display_name="Diagrammer Agent",
    description="Genera especificaciones y diagramas Mermaid interactivos de componentes y flujos.",
    color_hex="#b347ff",
    uses_rag=True,
    rag_filter=None,  # needs full vault context
    system_prompt=(
        "You are the Diagrammer Agent in ATENEA's AI team. "
        "Given an approved architectural proposal, generate one or more diagrams that visualise it. "
        "You MUST output diagrams as mermaid code blocks (```mermaid ... ```). "
        "Choose the most appropriate diagram type: "
        "  - C4 context or container diagram for system architecture. "
        "  - Sequence diagram for inter-service communication flows. "
        "  - Flowchart for decision logic or pipelines. "
        "  - Class/ER diagram for domain models. "
        "After each diagram, add a brief ## Diagram Notes section explaining key design decisions. "
        "Ensure mermaid syntax is valid and renderable in Obsidian / GitHub Markdown."
    ),
)

_LEARNING = SubAgentProfile(
    role=AgentRole.LEARNING,
    display_name="Learning Agent",
    description="Ingesta y extrae conocimiento semántico de fuentes y documentos hacia el vault.",
    color_hex="#1d4ed8",
    uses_rag=False,
    rag_filter=None,
    system_prompt=(
        "You are the Learning Agent for ATENEA. "
        "Your task is to ingest and summarize external sources (like PDFs or URLs) into the knowledge base. "
        "Usually, your logic is handled natively by the LearnFromSource service, but if invoked via chat, "
        "you provide helpful explanations about the knowledge base and what you have learned."
    ),
)


_SUPERVISOR = SubAgentProfile(
    role=AgentRole.SUPERVISOR,
    display_name="Supervisor",
    description="Orquesta el debate multi-agente, controla el flujo HITL y consolida el consenso.",
    color_hex="#f59e0b",
    uses_rag=False,
    rag_filter=None,
    system_prompt=(
        "You are the orchestrator of ATENEA's AI team. Your role is to coordinate "
        "and delegate tasks to the appropriate specialized sub-agents."
    ),
)


# ---------------------------------------------------------------------------
# Registry (Derived automatically from canonical profile definitions)
# ---------------------------------------------------------------------------

_ALL_PROFILES: tuple[SubAgentProfile, ...] = (
    _SUPERVISOR,
    _NL_INTERPRETER,
    _INNOVATOR,
    _SENIOR_ARCHITECT,
    _THE_JUDGE,
    _DEVOPS_SECOPS,
    _DIAGRAMMER,
    _LEARNING,
)

_PROFILES: dict[AgentRole, SubAgentProfile] = {p.role: p for p in _ALL_PROFILES}

# Integrity check: every role declared in AgentRole must have a profile
assert len(_PROFILES) == len(AgentRole), "Every AgentRole member must have a registered SubAgentProfile"


def get_profile(role: AgentRole) -> SubAgentProfile:
    """Return the SubAgentProfile for ``role``. Always succeeds (all roles are registered)."""
    return _PROFILES[role]


def get_all_profiles() -> list[SubAgentProfile]:
    """Return all registered SubAgentProfile instances in canonical definition order."""
    return list(_ALL_PROFILES)


def get_all_roles() -> list[AgentRole]:
    """Return all registered AgentRole instances in canonical definition order."""
    return [p.role for p in _ALL_PROFILES]
