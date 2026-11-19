"""
Application Agent Service: Triage Classification

Classifies incoming user requests into execution modes:
  - direct_chat: supervisor replies directly without invoking specialist council
  - single_agent: direct delegation to a single registered specialist
  - adaptive_debate: full or custom-planned multi-stage debate flow
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository
from src.domain.ports.llm_provider import ILLMProvider

logger = logging.getLogger(__name__)

_GREETING_PATTERNS: tuple[str, ...] = (
    r"^hola\b",
    r"^buenos d[ií]as\b",
    r"^buenas tardes\b",
    r"^buenas noches\b",
    r"^qui[eé]n eres\b",
    r"^qu[eé] haces\b",
    r"^c[oó]mo est[aá]s\b",
    r"^pres[eé]ntate\b",
    r"^presenta\b",
    r"^qui[eé]nes sois\b",
    r"^qui[eé]nes son\b",
)


@dataclass(frozen=True)
class TriageDecision:
    """Routing decision produced by triage analysis."""

    mode: str  # "direct_chat" | "single_agent" | "adaptive_debate"
    target_agent: str | None = None
    skip_interpreter: bool = False
    reasoning: str = ""
    execution_plan: tuple[str, ...] = ()


def _parse_triage_json(raw: str) -> dict[str, Any] | None:
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        logger.debug("Failed to parse triage JSON response", exc_info=True)
        return None


def _is_direct_chat_greeting(req_clean: str) -> bool:
    return any(re.search(pattern, req_clean) for pattern in _GREETING_PATTERNS)


def _build_triage_prompt(
    user_request: str,
    supervisor_name: str,
    interpreter_name: str,
    agent_catalog: IAgentCatalogRepository,
) -> str:
    specialists = [
        p for p in agent_catalog.get_all_profiles()
        if not p.is_supervisor
        and p.display_name.lower() != interpreter_name.lower()
        and p.id != interpreter_name
    ]
    specialists_lines = "\n".join(
        f'   - "{p.display_name}" ({p.id}): {p.description}'
        for p in specialists
    )
    specialist_names_union = " | ".join(f'"{p.display_name}"' for p in specialists) + " | null"

    return f"""\
Eres {supervisor_name}. Analiza la petición del usuario y clasifica la intención para determinar la estrategia de ejecución óptima del consejo de agentes:

1. "direct_chat": Saludos, preguntas directas a {supervisor_name} sobre quién es o su consejo, dudas conceptuales rápidas o reflexiones donde NO se requiere un trabajo técnico ni un debate.
2. "single_agent": El usuario solicita expresamente una tarea acotada a un único especialista:
{specialists_lines}
3. "adaptive_debate": Problemas o requerimientos que necesitan deliberación colegiada del consejo. Opcionalmente puedes definir un plan dinámico de etapas en "execution_plan" seleccionando entre: "interpreters", "proposers", "evaluators", "implementers".
   - Si no especificas plan (dejas "execution_plan": null), se seguirá el flujo natural y completo del consejo (intérprete -> debate de proponentes en paralelo -> evaluador -> implementadores).
   - En "adaptive_debate", el plan recomendado es null para deliberar con las propuestas en paralelo de los agentes proponentes, a menos que el usuario pida expresamente saltarse dicha fase.
   - skip_interpreter=false: La petición es vaga, coloquial o requiere desambiguación y formalización de requisitos por parte de {interpreter_name}.
   - skip_interpreter=true: La petición ya incluye requisitos estrictos, métricas, componentes y restricciones bien definidas.

Responde ÚNICAMENTE un objeto JSON válido con este formato:
{{
  "mode": "direct_chat" | "single_agent" | "adaptive_debate",
  "target_agent": {specialist_names_union},
  "skip_interpreter": true | false,
  "execution_plan": null | ["interpreters", "proposers", "evaluators", "implementers"],
  "reasoning": "Breve justificación de 1 frase"
}}

Petición del usuario:
{user_request}
"""


def _decision_from_parsed_payload(
    parsed: dict[str, Any],
    agent_catalog: IAgentCatalogRepository,
) -> TriageDecision:
    target_str = parsed.get("target_agent")
    target_agent: str | None = None
    if target_str:
        try:
            target_agent = agent_catalog.get_profile(str(target_str)).display_name
        except KeyError:
            target_agent = str(target_str)

    raw_plan = parsed.get("execution_plan")
    plan_tuple = tuple(str(x) for x in raw_plan) if isinstance(raw_plan, list) else ()
    return TriageDecision(
        mode=str(parsed.get("mode", "adaptive_debate")),
        target_agent=target_agent,
        skip_interpreter=bool(parsed.get("skip_interpreter", False)),
        reasoning=str(parsed.get("reasoning", "")),
        execution_plan=plan_tuple,
    )


def classify_intent(
    user_request: str,
    llm_provider: ILLMProvider,
    model_name: str,
    supervisor_name: str,
    interpreter_name: str,
    agent_catalog: IAgentCatalogRepository | None = None,
) -> TriageDecision:
    """Determine execution strategy for a user request via lightweight heuristics and LLM triage."""
    if agent_catalog is None:
        raise ValueError("agent_catalog must be provided to classify_intent()")

    if _is_direct_chat_greeting(user_request.strip().lower()):
        return TriageDecision(
            mode="direct_chat",
            reasoning=f"Saludo o consulta directa a {supervisor_name}",
        )

    triage_prompt = _build_triage_prompt(user_request, supervisor_name, interpreter_name, agent_catalog)
    try:
        raw_res = llm_provider.complete(triage_prompt, model_name)
        parsed = _parse_triage_json(raw_res)
        if parsed and "mode" in parsed:
            return _decision_from_parsed_payload(parsed, agent_catalog)
    except Exception:
        logger.warning("LLM triage failed; defaulting to standard adaptive_debate", exc_info=True)

    return TriageDecision(
        mode="adaptive_debate",
        target_agent=None,
        skip_interpreter=False,
        reasoning="Fallback estándar",
    )

