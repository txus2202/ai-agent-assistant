# Guía de Modelos Recomendados por Agente (Balance Beneficio / Tokens)

Este documento detalla la asignación recomendada de modelos de Inteligencia Artificial para cada uno de los 11 agentes del consejo técnico de **A.T.E.N.E.A.** declarados en `agents.yaml`, optimizada bajo el criterio de **equilibrio de Pareto (máximo beneficio técnico con el menor consumo de tokens y coste posible)**.

En un sistema multi-agente donde una deliberación invoca entre 4 y 7 agentes en cascada, esta asignación evita el sobrecoste de modelos masivos (como Opus u o3) en tareas operativas o de formato, concentrando la potencia de razonamiento únicamente donde aporta valor diferencial.

---

## 1. Selección Multi-Proveedor (Equilibrio Coste / Tokens / Rendimiento)

Combina de manera óptima los catálogos de **Anthropic**, **OpenAI** y **Google Gemini**, priorizando modelos de alta eficiencia (`Sonnet`, `Haiku`, `Mini`, `Flash`):

| Agente | Rol / Responsabilidad | Proveedor Recomendado | Modelo Recomendado | Justificación Balance Beneficio / Tokens |
| :--- | :--- | :--- | :--- | :--- |
| **Atenea** (`supervisor`) | Orquestadora suprema, síntesis del debate, arbitraje y veredicto | **Anthropic** | `claude-sonnet-5-5` | Ofrece el 98% de la capacidad de síntesis y juicio de Opus a una quinta parte del coste en tokens. Excelente para la redacción del veredicto final. |
| **Hermes** (`nl_interpreter`) | Desambiguación ágil, estructuración de requisitos y preguntas clave | **Anthropic** | `claude-haiku-5-5` | Consumo de tokens y latencia mínimos (~10x más barato). Ideal para parseo rápido de intenciones y generación estructurada sin ping-pong. |
| **Ícaro** (`innovator_architect`) | Arquitectura vanguardista, cloud-native, reactivo y CQRS | **Anthropic** | `claude-sonnet-5-5` | El modelo con mejor ratio inteligencia/precio para diseñar arquitecturas de vanguardia y matrices de riesgos con criterio técnico sólido. |
| **Hestia** (`senior_architect`) | Arquitectura pragmática, estabilidad corporativa y alineación RAG | **OpenAI** | `gpt-5.4-mini` *(o `claude-sonnet-5-5`)* | Al recibir el contexto de estándares inyectado por RAG, un modelo ligero como `5.4-mini` basta para sintetizar sin gastar en razonamientos pesados. |
| **Sphinx** (`the_judge`) | Auditora implacable, Abogada del Diablo, detección de SPOFs y scoring | **Anthropic** | `claude-sonnet-5-5` | `o3` genera miles de tokens de razonamiento oculto en cada auditoría. `Sonnet-5-5` detecta SPOFs y contradicciones de ADRs con rigor despiadado y bajo coste. |
| **Hefesto** (`devops_secops`) | DevSecOps, modelado STRIDE, Zero-Trust y pipelines CI/CD | **Anthropic** | `claude-sonnet-5-5` | Precisión quirúrgica en seguridad, análisis SCA y configuración de pipelines IaC (Docker/K8s) sin necesidad de pagar el tier prémium. |
| **Aracne** (`diagrammer`) | Tejedora de diagramas interactivos en Mermaid.js | **Gemini** *(o Anthropic)* | `gemini-3.8-flash` *(o `claude-haiku-5-5`)* | Generar código Mermaid no requiere un modelo gigante. Modelos rápidos producen sintaxis limpia, simétrica y válida para Draw.io a coste insignificante. |
| **Metis** (`learning`) | Ingesta semántica de PDFs/URLs extensas, síntesis y memoria | **Gemini** | `gemini-3.8-flash` | Su ventana de 1M de tokens ingiere libros o PDFs completos en un solo paso, ahorrando particionado complejo a una tarifa de tokens ultra-baja. |
| **Fídias** (`fídias`) | Diseñador UX/UI, maquetador HTML5/CSS y recursos visuales | **Gemini** | `gemini-3.8-flash` | La maquetación de layouts HTML5/CSS/JS vainilla es rápida y visualmente impecable con modelos Flash, ahorrando costes frente a modelos pesados. |
| **Dédalo** (`dedalo`) | Full-stack developer, Clean Code (TypeScript, Go, Python, Java) | **Anthropic** | `claude-sonnet-5-5` | El referente absoluto del sector en ratio calidad/coste para programación, testing unitario y Clean Code sin divagaciones innecesarias. |
| **Calíope** (`caliope`) | Redactora técnica, manuales, actas de reuniones y Markdown | **Gemini** *(o Anthropic)* | `gemini-3.8-flash` *(o `claude-haiku-5-5`)* | Los documentos largos consumen muchos tokens de salida (`completion`). Un modelo Flash/Haiku abarata un 80% el coste manteniendo alta calidad redactora. |

---

## 2. Selección Exclusiva en GEMINI (Google AI Studio / Capa Activa)

Distribución optimizada dentro del catálogo de **Google Gemini**, aprovechando su capa gratuita/económica y reservando los modelos `Pro` únicamente para los agentes donde el razonamiento profundo es indispensable:

| Agente | Rol | Modelo Gemini Recomendado | Justificación Balance Beneficio / Tokens |
| :--- | :--- | :--- | :--- |
| **Atenea** (`supervisor`) | Orquestadora / Supervisora | `gemini-3.1-pro-preview` *(o `gemini-pro-latest`)* | **Tier Razonamiento Máximo:** Reserva la cuota `Pro` para el agente que debe arbitrar, resolver empates técnicos y formular la síntesis definitiva. |
| **Hermes** (`nl_interpreter`) | Intérprete ágil | `gemini-3.8-flash` *(o `gemini-3.1-flash-lite`)* | **Tier Rápido/Económico:** Máxima velocidad de respuesta interactiva en el chat con coste de tokens prácticamente nulo. |
| **Ícaro** (`innovator_architect`) | Arquitecto Vanguardista | `gemini-3.7-flash` | **Tier Híbrido (*Thinking*):** Combina el bajo coste de Flash con el razonamiento profundo para explorar patrones cloud-native y trade-offs audaces. |
| **Hestia** (`senior_architect`) | Arquitecta Corporativa | `gemini-3.6-flash` *(o `gemini-3.8-flash`)* | **Tier Rápido/Económico:** Muy eficiente evaluando el contexto corporativo devuelto por ChromaDB sin sobreconsumo de cuota. |
| **Sphinx** (`the_judge`) | Auditora implacable | `gemini-3.1-pro-preview` *(o `gemini-4-argon`)* | **Tier Razonamiento Máximo:** La detección rigurosa de cuellos de botella y contradicciones temporales justifica plenamente el uso del tier Pro. |
| **Hefesto** (`devops_secops`) | DevSecOps / Seguridad | `gemini-3.8-flash` | **Tier Rápido/Económico:** Excelente rendimiento validando pipelines CI/CD y políticas de seguridad sin necesidad de saturar la cuota Pro. |
| **Aracne** (`diagrammer`) | Diagramación Mermaid.js | `gemini-3.8-flash` | **Tier Rápido/Económico:** Entrega sintaxis Mermaid.js impecable de forma instantánea sin gastar tokens de razonamiento. |
| **Metis** (`learning`) | Aprendizaje e Ingesta RAG | `gemini-3.8-flash` | **Tier Rápido/Económico:** Ingesta masiva de documentos en ventana de contexto amplia con el menor coste por millón de tokens del mercado. |
| **Fídias** (`fídias`) | Diseño UX/UI y Maquetación | `gemini-3.8-flash` | **Tier Rápido/Económico:** Maquetación limpia en HTML/CSS y emisión directa de directivas visuales con velocidad y economía extrema. |
| **Dédalo** (`dedalo`) | Desarrollador Full-Stack | `gemini-3.7-flash` | **Tier Híbrido (*Thinking*):** Ideal para programación y Clean Code; resuelve problemas algorítmicos complejos con tarifa de modelo Flash. |
| **Calíope** (`caliope`) | Redacción y Documentación | `gemini-3.8-flash` | **Tier Rápido/Económico:** Al generar manuales y actas extensas, el coste por token de salida se reduce drásticamente sin perder elocuencia. |

---

### Resumen del Ahorro Estimado en Debates
- **Reducción de coste/tokens estimada:** Entre un **65% y un 80%** frente a una configuración de gama alta ciega (`Opus / o3 / Pro` en todos los roles).
- **Reducción de latencia media por turno:** De ~8-12 segundos a **~1.5-3 segundos** en agentes como Hermes, Aracne, Calíope y Fídias.

