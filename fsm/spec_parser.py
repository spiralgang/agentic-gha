"""Markdown-driven FSM spec parser.

Parses the repository's `.md` layouts into a validated Spec:

  PLANS.md               -> state graph (states + transitions + initial)
  COPILOT_INSTRUCTIONS.md-> parameters (the knobs the machine follows)
  AGENT_INSTRUCTIONS.md  -> per-state behavior text (what to do on entry)
  VAULT.md               -> long-term knowledge entries (context store)

Grammar
-------
PLANS.md:
    # FSM: <name>
    Initial: <state>
    ## States
    - <state_id> : <optional description>
    ## Transitions
    - <from> -> <to> : <guard_expr> [| <action>]

COPILOT_INSTRUCTIONS.md:
    ## Parameters
    - <key>: <value>        (int/float/bool/str auto-inferred)

AGENT_INSTRUCTIONS.md:
    ## <state_id> [description]
    <free text until next '## '>

VAULT.md:
    ## <entry_name>
    <free text until next '## '>
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Spec:
    name: str = "UnnamedFSM"
    initial: str = ""
    states: Dict[str, str] = field(default_factory=dict)
    transitions: List[Tuple[str, str, str, str]] = field(default_factory=list)
    params: Dict[str, object] = field(default_factory=dict)
    instructions: Dict[str, str] = field(default_factory=dict)
    vault: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.states:
            errors.append("no states defined (PLANS.md ## States)")
        if self.initial and self.initial not in self.states:
            errors.append(f"initial state '{self.initial}' not in states")
        for (frm, to, guard, _action) in self.transitions:
            if frm not in self.states:
                errors.append(f"transition from unknown state '{frm}'")
            if to not in self.states:
                errors.append(f"transition to unknown state '{to}'")
        return errors


# --------------------------------------------------------------------------
# low-level markdown helpers
# --------------------------------------------------------------------------
def _sections(text: str) -> List[Tuple[Optional[str], str]]:
    """Return [(heading, body), ...]; the first body before any heading has
    heading=None."""
    out: List[Tuple[Optional[str], str]] = []
    cur_head: Optional[str] = None
    cur_body: List[str] = []
    for line in text.splitlines():
        m = re.match(r"^#+\s*(.*?)\s*$", line)
        if m:
            out.append((cur_head, "\n".join(cur_body).strip()))
            cur_head = m.group(1)
            cur_body = []
        else:
            cur_body.append(line)
    out.append((cur_head, "\n".join(cur_body).strip()))
    return [(h, b) for (h, b) in out if h is not None or b]


def _coerce(value: str) -> object:
    v = value.strip()
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() in ("null", "none", ""):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v


def _first_heading(text: str) -> Optional[str]:
    for line in text.splitlines():
        m = re.match(r"^#\s*(.*?)\s*$", line)
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------
# per-file parsers
# --------------------------------------------------------------------------
def parse_plans(text: str, spec: Spec) -> None:
    head = _first_heading(text) or ""
    m = re.search(r"FSM:\s*(\S+)", head)
    if m:
        spec.name = m.group(1)
    # Initial: line
    for line in text.splitlines():
        mi = re.match(r"^[Ii]nitial:\s*(\S+)", line.strip())
        if mi:
            spec.initial = mi.group(1)
            break
    for heading, body in _sections(text):
        if heading.lower().startswith("states"):
            for line in body.splitlines():
                line = line.strip()
                if not line or not line.startswith("-"):
                    continue
                content = line[1:].strip()
                if ":" in content:
                    sid, desc = content.split(":", 1)
                    spec.states[sid.strip()] = desc.strip()
                else:
                    spec.states[content.strip()] = ""
        elif heading.lower().startswith("transition"):
            for line in body.splitlines():
                line = line.strip()
                if not line or not line.startswith("-"):
                    continue
                content = line[1:].strip()
                mt = re.match(r"^(\w+)\s*->\s*(\w+)\s*:\s*(.+)$", content)
                if not mt:
                    continue
                frm, to, rest = mt.group(1), mt.group(2), mt.group(3)
                if "|" in rest:
                    guard, action = rest.split("|", 1)
                else:
                    guard, action = rest, ""
                spec.transitions.append((frm, to, guard.strip(), action.strip()))


def parse_params(text: str, spec: Spec) -> None:
    for heading, body in _sections(text):
        if heading.lower().startswith("parameter"):
            for line in body.splitlines():
                line = line.strip()
                if not line or not line.startswith("-"):
                    continue
                content = line[1:].strip()
                if ":" in content:
                    k, v = content.split(":", 1)
                    spec.params[k.strip()] = _coerce(v)


def _parse_named_sections(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for heading, body in _sections(text):
        key = heading.strip().split()[0]  # first word is the id
        out[key] = body
    return out


def parse_instructions(text: str, spec: Spec) -> None:
    spec.instructions.update(_parse_named_sections(text))


def parse_vault(text: str, spec: Spec) -> None:
    spec.vault.update(_parse_named_sections(text))


# --------------------------------------------------------------------------
# entrypoint: load a directory of .md layouts
# --------------------------------------------------------------------------
def load_specs(spec_dir: str) -> Spec:
    spec = Spec()
    files = sorted(os.listdir(spec_dir))
    for fname in files:
        if not fname.lower().endswith((".md", ".markdown")):
            continue
        path = os.path.join(spec_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        low = fname.lower()
        if "plans" in low:
            parse_plans(text, spec)
        elif "copilot" in low or "instructions" in low and "agent" not in low:
            # COPILOT_INSTRUCTIONS first; AGENT handled below
            if "copilot" in low:
                parse_params(text, spec)
        elif "agent" in low:
            parse_instructions(text, spec)
        elif "vault" in low:
            parse_vault(text, spec)
    return spec
