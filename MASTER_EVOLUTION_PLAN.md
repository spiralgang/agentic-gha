# MASTER EVOLUTION PLAN — Agentic GHA

## Vision
To transform GitHub Actions from static YAML pipelines into a self-evolving, FSM-driven agentic framework that optimizes its own execution paths based on real-time failure analysis and goal achievement.

## Capability Levels
- **L1: Static FSM** (Current) - Workflows follow a predefined state machine.
- **L2: Dynamic Specification** - Ability to modify FSM transitions and states via agent-authored PRs.
- **L3: Self-Optimizing Paths** - GHA analyzes its own run history to propose faster or more reliable state transitions.
- **L4: Autonomous Workflow Synthesis** - Agents synthesize entirely new workflows to meet newly defined high-level goals.

## Evolutionary Roadmap

### Phase 1: Dynamic Specification (L1 $\rightarrow$ L2)
- [ ] **FSM Specification Format**: Formalize the FSM specification (e.g., JSON/YAML) separate from the YAML workflow.
- [ ] **Specification Update Loop**: Implement a workflow that can read an updated FSM spec and automatically update the corresponding `.yml` workflow.
- [ ] **Evolutionary Feedback**: Link failure analysis (e.g., from `ai-agent-review.yml`) back to FSM state transitions.

### Phase 2: Self-Optimization (L2 $\rightarrow$ L3)
- [ ] **Run-Time Analytics**: Collect metrics on state transition latency and failure rates.
- [ ] **Optimization Heuristics**: Implement rules for identifying "bottleneck states".
- [ ] **Autonomous Refactor**: Agent-driven PRs to optimize the FSM based on analytics.

## Tracking
- **Current Level**: 1
- **Next Objective**: Phase 1 - Dynamic Specification (Issue #9).
