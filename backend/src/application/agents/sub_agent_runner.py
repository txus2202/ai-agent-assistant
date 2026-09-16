"""
Application Agent: SubAgentRunner

Executes a single specialized sub-agent:
  1. Load the SubAgentProfile for the requested role
  2. If uses_rag: query the vault and build context block
  3. Build prompt: system_prompt + context + user_request
  4. Call llm_provider.complete()
  5. Return SubAgentResponse

Lives in application/agents/ alongside the Supervisor (Feature 5).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.application.services.query_vault import QueryVault
from src.domain.agents.agent_role import AgentRole
from src.domain.agents.sub_agent_profiles import get_profile
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.llm_provider import ILLMProvider
from src.domain.value_objects.document_chunk import DocumentChunk


@dataclass
class SubAgentResponse:
    """Result returned by SubAgentRunner.run()."""

    role: AgentRole
    content: str
    context_chunks: list[DocumentChunk] = field(default_factory=list)


class SubAgentRunner:
    """Stateless runner for a single sub-agent invocation."""

    @staticmethod
    def run(
        role: AgentRole,
        user_request: str,
        llm_provider: ILLMProvider,
        document_store: IDocumentStore,
        model_name: str,
    ) -> SubAgentResponse:
        """
        Run a sub-agent for the given role.

        Args:
            role:           The AgentRole determining which profile and prompts to use.
            user_request:   The (already formalized) user request to process.
            llm_provider:   ILLMProvider to call for completion.
            document_store: Store used for RAG retrieval.
            model_name:     Model to use for the LLM call.

        Returns:
            SubAgentResponse with the agent's content and RAG chunks used.
        """
        profile = get_profile(role)

        # ── 1. RAG retrieval ──────────────────────────────────────────────
        context_chunks: list[DocumentChunk] = []
        context_block = ""

        if profile.uses_rag:
            context_chunks = QueryVault.run(
                query=user_request,
                document_store=document_store,
                filter=profile.rag_filter,
            )
            context_block = QueryVault.chunks_to_context(context_chunks)

        # ── 2. Build prompt ───────────────────────────────────────────────
        parts: list[str] = [profile.system_prompt]
        if context_block:
            parts.append(context_block)
        parts.append(f"## User Request\n{user_request}")

        prompt = "\n\n".join(parts)

        # ── 3. LLM call ───────────────────────────────────────────────────
        content = llm_provider.complete(prompt, model_name)

        return SubAgentResponse(
            role=role,
            content=content,
            context_chunks=context_chunks,
        )
