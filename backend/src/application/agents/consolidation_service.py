"""
Application Agent Service: Final Debate Consolidation

Builds the authoritative Spanish Markdown verdict from collected debate outputs
and invokes the supervisor LLM with isolated token usage tracking.
"""
from __future__ import annotations

import asyncio
import time

from src.application.agents.debate_state import DebateState
from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.supervisor_events import EventType, SupervisorEvent
from src.domain.ports.llm_provider import ILLMProvider, invoke_llm_with_usage

CONSOLIDATION_PROMPT = """\
Eres {supervisor_name}, la autoridad máxima y orquestadora del consejo de agentes.
El consejo colegiado de especialistas ha concluido su deliberación.
Genera un documento estructurado en Markdown (300-500 palabras) que consolide todas las perspectivas en un dictamen claro, vinculante y de nivel de producción.

Estructura obligatoria en español:
## 1. Resumen Ejecutivo y Dictamen Estratégico
El enfoque final adoptado y la justificación de la decisión colegiada.

## 2. Decisiones y Enfoques Clave
Síntesis de las propuestas de los agentes proponentes ({proposers_str}), equilibrando sus distintas visiones.

## 3. Mitigación de Riesgos y Evaluación Crítica
Cómo se resuelven de forma concreta y accionable las vulnerabilidades, advertencias y directivas identificadas por el agente evaluador ({evaluator_name}).

## 4. Directivas de Implementación
Criterios y pasos operativos acordes a las aportaciones de los agentes de implementación ({implementers_str}).

## 5. Plan de Acción Inmediato
Pasos concretos y numerados para el equipo.

--- Aportaciones del Consejo ---
{debate_context}
"""


async def run_consolidation(
    state: DebateState,
    default_provider: ILLMProvider,
    default_model: str,
    supervisor_name: str,
    topology: DebateTopology,
) -> SupervisorEvent:
    """Synthesize agent outputs from ``state`` into the final ``DONE`` event."""
    debate_context = "\n\n".join(
        f"### {role}\n{content}" for role, content in state.agent_outputs.items()
    )
    consolidation_prompt = CONSOLIDATION_PROMPT.format(
        supervisor_name=supervisor_name,
        proposers_str=", ".join(topology.proposers),
        evaluator_name=", ".join(topology.evaluators),
        implementers_str=", ".join(topology.implementers),
        debate_context=debate_context,
    )

    start_time = time.perf_counter()
    final_response, usage = await asyncio.to_thread(
        invoke_llm_with_usage, default_provider, consolidation_prompt, default_model
    )
    latency = round(time.perf_counter() - start_time, 2)

    if not usage or usage.get("total", 0) == 0:
        in_tkn = max(1, len(consolidation_prompt) // 4)
        out_tkn = max(1, len(final_response) // 4)
        usage = {"input": in_tkn, "output": out_tkn, "total": in_tkn + out_tkn}

    meta = {
        "model": default_model,
        "prompt_tokens": str(usage.get("input", 0)),
        "completion_tokens": str(usage.get("output", 0)),
        "total_tokens": str(usage.get("total", 0)),
        "latency_seconds": str(latency),
        "tokens": str(usage.get("total", 0)),
    }

    return SupervisorEvent(
        type=EventType.DONE,
        role=supervisor_name,
        content=final_response,
        metadata=meta,
    )

