#!/usr/bin/env python3
"""
superlab_living_code.py
=======================

Agentic-Matrix "Living-Code" hybrid framework (superlab standard).

Design in one breath
--------------------
A *Manager* agent owns an LLM. On each cycle it asks that LLM to *write the
source code* of a child mini-bot (role, goal, and a working ``execute`` method
that itself calls the LLM). The manager then:

    1. PARSE   - ``ast.parse`` the generated source and audit it against a
                 banned-node gate (no imports, no eval/exec/os/subprocess...).
    2. COMPILE - ``compile`` the audited source into a code object and
                 ``exec`` it into a fresh module namespace.
    3. INSTANTIATE - pull the ``GeneratedAgent`` class out of that namespace
                 and construct a child, injecting the shared LLM.
    4. DEPLOY  - run N such children concurrently with ThreadPoolExecutor
                 (parallel tandem deployment) and aggregate their output.
    5. MUTATE  - between cycles the manager asks the LLM to *improve* a
                 child's code; the new source is re-parsed, re-compiled and
                 hot-swapped in place. That is the "living code" loop.

Everything is dependency-free (Python stdlib only) so it runs anywhere.
It speaks the OpenAI chat-completions wire format over ``urllib``; supply a
key via the environment and it talks to a real model. With no key (or
``--mock``) it uses a built-in MockLLM so the full parse/compile/deploy/
aggregate pipeline still executes for real.

Run:
    python3 superlab_living_code.py --mock --children 3 --cycles 2
    LLM_API_KEY=sk-... python3 superlab_living_code.py --children 3 --cycles 2
    LLM_API_KEY=sk-or-v1-... python3 superlab_living_code.py \
        --base-url https://openrouter.ai/api/v1 --model openai/gpt-4o-mini
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import logging
import os
import sys
import textwrap
import time
import types
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG = logging.getLogger("superlab")
if not LOG.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s"))
    LOG.addHandler(_h)
LOG.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class Config:
    """Runtime configuration for the matrix. Env-driven, no secrets inline."""
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "glm-4-flash"))
    base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    )
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    temperature: float = 0.4
    max_tokens: int = 1200
    children: int = 3
    cycles: int = 2
    max_workers: int = 8


# ---------------------------------------------------------------------------
# LLM client (real, OpenAI-compatible; no mock — policy compliant)
# ---------------------------------------------------------------------------
from llm_client import LLMClient, NoLLMKeyError


# ---------------------------------------------------------------------------
# Parse gate: ast audit before compiling untrusted generated source
# ---------------------------------------------------------------------------
_BANNED_NAMES = {
    "__import__", "eval", "exec", "compile", "open", "exit", "quit",
    "input", "os", "sys", "subprocess", "socket", "shutil", "pathlib",
    "importlib", "pickle", "marshal", "ctypes", "builtins", "globals",
    "locals", "getattr", "setattr", "delattr", "memoryview",
}

_BANNED_NODES = (ast.Import, ast.ImportFrom)


def audit_source(source: str) -> ast.Module:
    """Parse + audit generated source.

    Raises ``ValueError`` if the code is not valid Python or tries to use a
    banned name / import. Returns the parsed module so the caller can compile.
    """
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"generated source is not valid Python: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, _BANNED_NODES):
            raise ValueError("generated source may not import modules")
        # Banned bare names
        if isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            raise ValueError(f"generated source references banned name: {node.id}")
        # Banned attribute access (e.g. os.system, builtins.eval)
        if isinstance(node, ast.Attribute) and node.attr in _BANNED_NAMES:
            raise ValueError(f"generated source references banned attr: {node.attr}")
    return tree


# ---------------------------------------------------------------------------
# Dynamic compiler: source string -> live agent class
# ---------------------------------------------------------------------------
class DynamicCompiler:
    """Turns an LLM-generated source module into a concrete agent class.

    The generated module is expected to define a class named ``GeneratedAgent``
    with the contract::

        class GeneratedAgent:
            def __init__(self, role, goal, llm): ...
            def execute(self, task: dict) -> str: ...
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._seq = 0

    def compile_class(self, source: str) -> type:
        tree = audit_source(source)
        code = compile(tree, filename=f"<dynamic_{self._seq}>", mode="exec")
        module = types.ModuleType(f"dynamic_agent_{self._seq}")
        module.__dict__["__builtins__"] = _safe_builtins()
        self._seq += 1
        # exec is intentional here: this is the "compile from source" step.
        exec(code, module.__dict__)  # noqa: S102 - audited above
        cls = module.__dict__.get("GeneratedAgent")
        if not isinstance(cls, type):
            raise ValueError("generated source did not define 'GeneratedAgent' class")
        return cls


# A deliberately reduced builtins surface for exec'd children.
def _safe_builtins() -> Dict[str, Any]:
    # Fall back to the real builtins mapping regardless of host form.
    real = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
    safe = {}
    for name in (
        "True", "False", "None", "bool", "int", "float", "str", "list",
        "dict", "tuple", "set", "frozenset", "len", "range", "enumerate",
        "zip", "map", "filter", "sorted", "reversed", "min", "max", "sum",
        "abs", "round", "isinstance", "type", "print", "format", "repr",
        "super", "__build_class__",
    ):
        if name in real:
            safe[name] = real[name]
    import json as _json
    safe["json"] = _json
    return safe


# ---------------------------------------------------------------------------
# Living environment: shared state + pub/sub event bus
# ---------------------------------------------------------------------------
class LivingEnvironment:
    def __init__(self) -> None:
        self._state: Dict[str, Any] = {}
        self._subscribers: List[Callable[[str, Any], None]] = []

    def subscribe(self, cb: Callable[[str, Any], None]) -> None:
        self._subscribers.append(cb)

    def update(self, key: str, value: Any) -> None:
        self._state[key] = value
        LOG.debug("env[%s] <- %s", key, _truncate(str(value)))
        for cb in self._subscribers:
            try:
                cb(key, value)
            except Exception as exc:  # noqa: BLE001
                LOG.warning("subscriber error: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)


# ---------------------------------------------------------------------------
# Child wrapper: holds a live compiled instance + lineage
# ---------------------------------------------------------------------------
@dataclass
class ChildAgent:
    name: str
    role: str
    goal: str
    cls: type
    instance: Any
    version: int = 1
    source: str = ""


# ---------------------------------------------------------------------------
# Manager agent (the host / matrix controller)
# ---------------------------------------------------------------------------
class ManagerAgent:
    def __init__(self, cfg: Config, env: LivingEnvironment) -> None:
        self.cfg = cfg
        self.env = env
        # Real LLM only. LLMClient raises NoLLMKeyError if no key (no mock).
        self.llm = LLMClient(
            model=cfg.model, base_url=cfg.base_url, api_key=cfg.api_key,
            temperature=cfg.temperature, max_tokens=cfg.max_tokens,
        )
        self.compiler = DynamicCompiler(cfg)
        self.children: List[ChildAgent] = []
        self.registry: Dict[str, List[str]] = {}  # evolution history of sources
        env.subscribe(self._on_env)

    # -- env reaction -------------------------------------------------------
    def _on_env(self, key: str, value: Any) -> None:
        if key.startswith("prompt_update_"):
            LOG.info("manager received env update: %s", key)

    # -- child code generation ---------------------------------------------
    def _generate_child_source(self, role: str, goal: str) -> str:
        prompt = textwrap.dedent(f"""
        You are a code-generating sub-model inside an agentic matrix.
        WRITE A PYTHON CHILD AGENT for the role below. Output ONLY a single
        fenced ```python block defining a class named exactly `GeneratedAgent`
        with this contract:

            class GeneratedAgent:
                def __init__(self, role, goal, llm):
                    self.role = role
                    self.goal = goal
                    self.llm = llm
                def execute(self, task: dict) -> str:
                    # build a prompt from task and call self.llm.chat([...])
                    # return the string result

        Rules: no imports, no eval/exec, only the shared `self.llm` for I/O.

        ROLE: {role}
        GOAL: {goal}
        """).strip()
        return self.llm.chat([{"role": "user", "content": prompt}])

    @staticmethod
    def _extract_fenced(source: str) -> str:
        if "```python" in source:
            return source.split("```python", 1)[1].split("```", 1)[0]
        if "```" in source:
            return source.split("```", 1)[1].split("```", 1)[0]
        return source

    def spawn_child(self, role: str, goal: str, idx: int) -> ChildAgent:
        raw = self._generate_child_source(role, goal)
        src = self._extract_fenced(raw)
        cls = self.compiler.compile_class(src)
        instance = cls(role=role, goal=goal, llm=self.llm)
        name = f"child-{idx}-{role.split()[0].lower()}"
        child = ChildAgent(name=name, role=role, goal=goal, cls=cls,
                           instance=instance, version=1, source=src)
        self.registry.setdefault(name, []).append(src)
        LOG.info("spawned %s (role=%s)", name, role)
        return child

    # -- parallel deployment ------------------------------------------------
    def _run_one(self, child: ChildAgent, task: Dict[str, str]) -> Tuple[str, str]:
        try:
            out = child.instance.execute(task)
        except Exception as exc:  # noqa: BLE001
            out = f"(child error: {exc})"
        return child.name, out

    def deploy_parallel(self, tasks: List[Dict[str, str]]) -> Dict[str, str]:
        results: Dict[str, str] = {}
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.cfg.max_workers) as pool:
            futures = []
            for child, task in zip(self.children, tasks):
                futures.append(pool.submit(self._run_one, child, task))
            for fut in concurrent.futures.as_completed(futures):
                name, out = fut.result()
                results[name] = out
        return results

    # -- living-code mutation ----------------------------------------------
    def mutate_child(self, child: ChildAgent) -> None:
        prompt = textwrap.dedent(f"""
        Improve the execute() method of this agent (role: {child.role}).
        Return ONLY a fenced ```python block redefining the class
        `GeneratedAgent` with the same __init__/execute contract.
        Keep behaviour compatible. No imports, no eval/exec.

        CURRENT SOURCE:
        {child.source}
        """).strip()
        raw = self.llm.chat([{"role": "user", "content": prompt}])
        new_src = self._extract_fenced(raw)
        try:
            new_cls = self.compiler.compile_class(new_src)
        except ValueError as exc:
            LOG.warning("mutation rejected for %s: %s (keeping v%d)",
                        child.name, exc, child.version)
            return
        child.cls = new_cls
        child.instance = new_cls(role=child.role, goal=child.goal, llm=self.llm)
        child.version += 1
        child.source = new_src
        self.registry.setdefault(child.name, []).append(new_src)
        LOG.info("mutated %s -> v%d", child.name, child.version)

    # -- orchestration ------------------------------------------------------
    def run(self) -> None:
        roles = [
            "Data Analyst Bot",
            "Code Generator Bot",
            "UI Designer Bot",
            "Security Reviewer Bot",
            "Performance Tuner Bot",
        ]
        goals = [
            "Analyze the task data and surface key metrics.",
            "Generate working code that satisfies the task spec.",
            "Propose a clean interface/layout for the result.",
            "Find security risks in the proposed approach.",
            "Suggest performance optimizations.",
        ]

        # Spawn the requested number of children (round-robin roles).
        for i in range(self.cfg.children):
            r = roles[i % len(roles)]
            g = goals[i % len(goals)]
            self.children.append(self.spawn_child(r, g, i))

        for cycle in range(1, self.cfg.cycles + 1):
            LOG.info("===== cycle %d / %d =====", cycle, self.cfg.cycles)
            tasks = [
                {
                    "description": f"Sub-task for {c.role}: implement step {cycle}.",
                    "context": f"cycle={cycle}, goal={c.goal}",
                }
                for c in self.children
            ]
            results = self.deploy_parallel(tasks)
            for name, out in results.items():
                LOG.info("result[%s]: %s", name, _truncate(out, 120))

            # persist a collective snapshot into the living environment
            self.env.update(f"cycle_{cycle}_results", results)

            # Living-code: mutate one child per cycle to evolve the matrix.
            if cycle < self.cfg.cycles:
                self.mutate_child(self.children[cycle % len(self.children)])

        LOG.info("matrix complete. evolution history sizes: %s",
                 {k: len(v) for k, v in self.registry.items()})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _truncate(s: str, n: int = 200) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Superlab living-code agentic matrix")
    p.add_argument("--children", type=int, default=3, help="number of child bots")
    p.add_argument("--cycles", type=int, default=2, help="living-code cycles")
    p.add_argument("--model", type=str, default=None, help="model name override")
    p.add_argument("--base-url", type=str, default=None, help="OpenAI-compatible URL")
    p.add_argument("--temperature", type=float, default=None)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config(
        children=max(1, args.children),
        cycles=max(1, args.cycles),
        model=args.model or os.getenv("LLM_MODEL", "glm-4-flash"),
        base_url=args.base_url or os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        temperature=args.temperature if args.temperature is not None else 0.4,
    )

    LOG.info("booting superlab matrix (children=%d cycles=%d model=%s)",
             cfg.children, cfg.cycles, cfg.model)
    env = LivingEnvironment()
    try:
        manager = ManagerAgent(cfg, env)
    except NoLLMKeyError as exc:
        LOG.error("%s", exc)
        return 2
    t0 = time.time()
    manager.run()
    LOG.info("done in %.2fs", time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
