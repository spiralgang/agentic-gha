"""FSM Specification Updater: Modify .md specs programmatically."""

import os
import re
from typing import Dict, Optional

class SpecUpdater:
    def __init__(self, spec_dir: str):
        self.spec_dir = spec_dir

    def update_param(self, key: str, value: str):
        """Update or add a parameter in COPILOT_INSTRUCTIONS.md."""
        path = os.path.join(self.spec_dir, "COPILOT_INSTRUCTIONS.md")
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("## Parameters\n")

        with open(path, "r") as f:
            lines = f.readlines()

        new_lines = []
        found = False
        for line in lines:
            if line.strip().startswith("-") and key in line:
                new_lines.append(f"- {key}: {value}\n")
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            # Find the Parameters section
            for i, line in enumerate(new_lines):
                if "## Parameters" in line:
                    new_lines.insert(i + 1, f"- {key}: {value}\n")
                    found = True
                    break
            if not found:
                new_lines.append("\n## Parameters\n")
                new_lines.append(f"- {key}: {value}\n")

        with open(path, "w") as f:
            f.writelines(new_lines)

    def update_instruction(self, state_id: str, text: str):
        """Update or add a state instruction in AGENT_INSTRUCTIONS.md."""
        path = os.path.join(self.spec_dir, "AGENT_INSTRUCTIONS.md")
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("")

        with open(path, "r") as f:
            content = f.read()

        # Simple regex to find ## state_id
        pattern = re.compile(rf"## {re.escape(state_id)}.*?\n(.*?)(?=\n## |$)", re.DOTALL)
        
        if pattern.search(content):
            new_content = pattern.sub(f"## {state_id}\n{text}\n", content)
        else:
            new_content = content + f"\n## {state_id}\n{text}\n"

        with open(path, "w") as f:
            f.write(new_content)

    def update_vault(self, entry_name: str, text: str):
        """Update or add a vault entry in VAULT.md."""
        path = os.path.join(self.spec_dir, "VAULT.md")
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write("")

        with open(path, "r") as f:
            content = f.read()

        pattern = re.compile(rf"## {re.escape(entry_name)}.*?\n(.*?)(?=\n## |$)", re.DOTALL)
        
        if pattern.search(content):
            new_content = pattern.sub(f"## {entry_name}\n{text}\n", content)
        else:
            new_content = content + f"\n## {entry_name}\n{text}\n"

        with open(path, "w") as f:
            f.write(new_content)
