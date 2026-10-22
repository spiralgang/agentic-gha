# agentic-gha — Agentic GitHub Actions Workflows

Every markdown file in `~/` is wired into a real, autonomous GitHub Actions
runner. **Every workflow calls a REAL LLM** (no mock) through the shared
`.github/actions/llm/action.yml` composite action, which posts to
`${{ secrets.LLM_BASE_URL }}/chat/completions` with `${{ secrets.LLM_API_KEY }}`
and **fails loudly** if the key is missing. Mocking is forbidden by policy.

## Source `.md` (in `~/`)  ->  workflows it drives

| `~/` markdown | role | workflow(s) generated |
|---|---|---|
| `fsm/specs/PLANS.md` | FSM state graph | `fsm-self-compile.yml` (compiled -> runnable `CompiledFSM`) |
| `fsm/specs/COPILOT_INSTRUCTIONS.md` | FSM parameters (max_fix, max_cycles, model) | `fsm-self-compile.yml`, `sdlc-*.yml` (caps) |
| `fsm/specs/AGENT_INSTRUCTIONS.md` | per-state behavior | `sdlc-examine/plan/build/review/fix/approve.yml` |
| `fsm/specs/VAULT.md` | long-term knowledge (guard_policy, safety_caps) | `sdlc-review.yml` (default-FIX), `sdlc-fix.yml` (max_fix), `agentic-watchdog.yml` |
| `HERMES.md` (Main CI + GLM Companion) | CI + GLM coding companion | `main-ci.yml`, `hermes-glm-companion.yml` |
| `superlab_living_code.py` (the living-code matrix doc) | manager writes/compiles child agents | `livingcode-matrix.yml` |
| `AIra.md` (ARIA v4 autorepair) | failure capture -> /fix | `aria-autorepair.yml` |
| `dev/DEVICE-PRIVACY/docs/EDGE_PANEL.md` | edge codespace copilot | `edge-agentic-panel.yml` |
| `dev/OMNISCIENT-Agentic-AI-Sandbox-Mod-L/README.md` | agentic IDE + safety gate | `omniscient-agentic-ide.yml` |
| `dev/zhipu-bigmodel-android10-apk/{README,INTERNATIONAL_AI_README}.md` | 20+ provider orchestration | `zhipu-orchestrator.yml` |
| `dev/termux-ai-TODO.md` (10 skills) | Termux-AI skill runner | `termux-ai-skills.yml` |
| `dev/DEVICE-PRIVACY/README.md` (+ `STORAGE.md`) | on-device build + AI triage | `device-privacy-build.yml` |
| `json-py.md` | seccomp sandbox profile | `reusable/reusable-seccomp-run.yml` (sandbox substrate) |

## The self-driving SDLC loop (6 stages, repeat)

`examine -> plan -> build -> review -> fix -> approve -> (cycle++) -> examine`

- `sdlc-examine.yml` — REAL LLM surveys repo, picks an `agent-task` issue.
- `sdlc-plan.yml` — REAL LLM writes a file-level plan; creates the branch.
- `sdlc-build.yml` — REAL LLM emits the code patch; opens a PR.
- `sdlc-review.yml` — REAL GLM-4 reviews; verdict APPROVE/FIX (default FIX).
- `sdlc-fix.yml` — REAL LLM fixes per review; loops until `max_fix`, then force-approve.
- `sdlc-approve.yml` — squash-merge, close issue, advance cycle (stops at `max_cycles`).

Each stage hands to the next via `gh workflow run` and a shared `dispatch.json`
artifact. The whole thing is bounded (never infinite) and refuses to merge on
ambiguous/unsafe signals.

## Required repository secrets

- `LLM_API_KEY` (required by every agentic workflow via the `llm` action)
- `LLM_BASE_URL` (optional, defaults to Zhipu GLM-4)
- `LLM_MODEL` (optional, defaults to `glm-4-flash`)
- `ZHIPU_API_KEY` (GLM companion / orchestrator)
- `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD` (Omniscient signed build)
- `SDLC_MAX_FIX` (optional, default 3), `SDLC_MAX_CYCLES` (optional, default 10)

## Run it

Push this directory to a GitHub repo as the repo root (or merge `.github/`
into your existing repo). Add the secrets above, then trigger:

    gh workflow run sdlc-examine.yml -f cycle=0
    gh workflow run livingcode-matrix.yml -f children=4 -f cycles=2
    gh workflow run fsm-self-compile.yml

No secrets -> the workflows error out (no silent mock). That is the policy.
