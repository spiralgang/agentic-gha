# Architecture Audit: agentic-gha

## Overview
The agentic-gha repository implements a Markdown-driven Finite State Machine (FSM) to orchestrate agentic workflows. The system separates the FSM specification (stored in Markdown files) from the execution engine.

## Components
- **Spec Parser**: Parses `PLANS.md`, `COPILOT_INSTRUCTIONS.md`, `AGENT_INSTRUCTIONS.md`, and `VAULT.md` into a structured `Spec` object.
- **FSM Engine**: Executes the state transitions based on the parsed spec.
- **Knowledge Store**: `VAULT.md` serves as a long-term memory for the agent.

## Analysis
### Strengths
- **Human-Readable Specs**: Using Markdown allows non-developers to modify agent behavior.
- **Decoupling**: The engine is agnostic of the specific business logic defined in the specs.
- **Knowledge Isolation**: The vault provides a clean way to manage context.

### Weaknesses
- **Missing Update Loop**: There is no mechanism for the agent to autonomously update its own FSM specification based on learning or feedback (the missing `spec_updater.py`).
- **Static Transitions**: Transitions are defined statically; there is no dynamic guard evaluation based on runtime environment variables.
- **Manual Verification**: No automated tools to verify that the FSM is free of dead-ends or infinite loops.

## Architectural Bottlenecks
- The primary bottleneck is the **Manual Specification Loop**. The agent cannot "evolve" its workflow without external intervention to edit the Markdown files.

## Recommendation
Implement an autonomous specification update loop that can analyze state failures and propose edits to `PLANS.md`.
