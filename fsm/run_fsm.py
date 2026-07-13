#!/usr/bin/env python3
"""Compile the repository .md layouts into a runnable FSM and drive it.

Usage:
    python3 run_fsm.py [--spec-dir specs] [--out fsm_compiled.py] [--max-steps 500]

What it proves:
  * PLANS.md        -> the state graph (states + transitions + initial)
  * COPILOT_INSTRUCTIONS.md -> the parameters the machine follows
  * AGENT_INSTRUCTIONS.md   -> per-state behavior text (printed on entry)
  * VAULT.md        -> knowledge entries loaded into the machine context
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _ctx_compact(ctx: dict) -> str:
    keys = ("attempt", "cycle", "verdict", "max_fix", "max_cycles")
    return " ".join(f"{k}={ctx.get(k)}" for k in keys if k in ctx)


def build_hooks():
    from llm_client import LLMClient, NoLLMKeyError

    try:
        llm = LLMClient()  # real; raises NoLLMKeyError if no key
    except NoLLMKeyError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        sys.exit(2)

    def on_enter(state, ctx, instruction):
        first = instruction.strip().splitlines()[0] if instruction.strip() else "(no instruction)"
        print(f"  [ENTER {state}] {first}")

    def on_transition(frm, to, guard, action, ctx):
        tag = guard + (f" | {action}" if action else "")
        print(f"  {frm} --[{tag}]--> {to}   ({_ctx_compact(ctx)})")

    def decide(state, ctx):
        # Real LLM verdict: ask the model whether to APPROVE or FIX this PR.
        if state != "review":
            return {}
        prompt = (
            "You are the review gate of an SDLC FSM. Reply with exactly one "
            "word, either APPROVE or FIX, based on whether the change is safe "
            "to merge. No explanation."
        )
        try:
            verdict = llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0, max_tokens=8,
            ).strip().upper()
        except Exception as exc:  # noqa: BLE001 - never merge on uncertainty
            LOG.error("verdict LLM call failed: %s (defaulting to FIX)", exc)
            return {"verdict": "FIX"}
        if "APPROVE" in verdict:
            return {"verdict": "APPROVE"}
        return {"verdict": "FIX"}  # guard_policy: default FIX on ambiguity

    return on_enter, on_transition, decide


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile + run the markdown-driven FSM")
    ap.add_argument("--spec-dir", default=os.path.join(HERE, "specs"))
    ap.add_argument("--out", default=os.path.join(HERE, "fsm_compiled.py"))
    ap.add_argument("--max-steps", type=int, default=500)
    args = ap.parse_args()

    sys.path.insert(0, HERE)
    from spec_parser import load_specs, Spec  # noqa: E402
    from compiler import compile_to_file, compile_source  # noqa: E402

    spec = load_specs(args.spec_dir)
    errors = spec.validate()
    if errors:
        print("SPEC VALIDATION FAILED:")
        for e in errors:
            print("  -", e)
        return 1

    print(f"Loaded spec '{spec.name}' from {args.spec_dir}")
    print(f"  states   : {', '.join(spec.states)}")
    print(f"  initial  : {spec.initial}")
    print(f"  params   : {spec.params}")
    print(f"  vault    : {', '.join(spec.vault)}")

    src = compile_source(spec)
    out = compile_to_file(spec, args.out)
    print(f"  compiled -> {out} ({len(src)} bytes)")

    # Import the freshly generated module and drive it.
    spec_mod = importlib.util.spec_from_file_location("fsm_compiled", out)
    module = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(module)

    on_enter, on_transition, decide = build_hooks()
    fsm = module.CompiledFSM(on_enter=on_enter, decide=decide,
                             on_transition=on_transition, max_steps=args.max_steps)
    print("\n--- running FSM (parameters from COPILOT_INSTRUCTIONS.md) ---")
    history = fsm.run()
    print("\n--- summary ---")
    print(f"  steps executed : {fsm.steps}")
    print(f"  final state    : {fsm.state}")
    print(f"  transitions    : {len(history)}")
    print(f"  terminal?      : {'yes' if fsm.step() is None else 'no (hit max_steps)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
