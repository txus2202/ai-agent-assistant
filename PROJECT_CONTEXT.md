# Project Context: AI Software Architecture Assistant

## Overview

This local AI system acts as an expert software architecture team under a **Supervisor Agent Pattern**. It uses its own project repository as the initial Obsidian knowledge vault (Dogfooding) to learn and establish structural indexes (MOCs).

## AI Team Topology (Sub-Agents)

- **Natural Language Interpreter:** Translates ambiguous requests into strict technical prompts.
- **Innovator Architect:** Proposes cutting-edge architectural solutions.
- **Senior Architect:** Adheres strictly to approved tech stacks and in-house patterns.
- **The Judge (Devil's Advocate):** Actively searches for vulnerabilities in proposals.
- **DevOps & SecOps Agent:** Focuses on deployment, CI/CD, and network security.
- **Diagrammer Agent:** Specialized in generating accurate Mermaid.js diagrams from architectural descriptions.
- **Annotator Agent:** Automatically updates the Obsidian vault, generating ADRs and structural MOCs.

## Multi-Provider Support & Privacy

The system supports multiple LLM providers (Google Gemini, Anthropic Claude, OpenAI ChatGPT) via user-provided API keys.

- **User-Defined Routing:** The user (system owner) has full control to assign specific models and tiers to each agent (e.g., assigning a heavy `PRO` model to the Architects, and a fast, cheap `FLASH` model to the Annotator) based on their provided API keys.
- **Privacy Warning:** The UI will evaluate the provided API keys. If standard (non-Enterprise) keys are used, the system will explicitly warn the user that strict data privacy (zero-training retention) cannot be guaranteed by the provider.

## Human-in-the-Loop (HITL)

Before the Supervisor delegates critical tasks, the system must pause execution to ask the user for validation (e.g., clarifying ambiguous requests or approving an architect's proposal before generating final documentation).

## Key Constraints

1. **Privacy & Licensing (Local-First):** Vector databases (ChromaDB) and voice models run 100% locally. For the LLM, the system relies on the Gemini API with dual support:
   - **Enterprise Use (Strict Privacy):** Maximum privacy is guaranteed by connecting to Gemini Enterprise (Vertex AI) or a paid Google AI tier, ensuring corporate data is never used for model training.
   - **Individual Use:** Fully compatible with standard Google AI Pro licenses (AI Studio). _Warning:_ If using the free tier of AI Studio, prompt data may be reviewed by human reviewers and used for model training according to Google's terms of service, which compromises strict privacy.
2. **Decoupling:** Agnostic to the AI provider via Clean Architecture.
