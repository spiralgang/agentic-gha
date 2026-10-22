"""FSM Specification Loop Manager: Iteratively refine specs based on feedback."""

import os
import logging
from typing import List, Dict, Any
from fsm.spec_updater import SpecUpdater

# Re-using the LLMClient logic from superlab_fsm_living_code.py for consistency
import urllib.request
import json

class LLMClient:
    def __init__(self, model="glm-4-flash", base_url="https://open.bigmodel.cn/api/paas/v4", api_key=None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")

    def chat(self, messages, temperature=0.4, max_tokens=1200) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error calling LLM: {e}"

class SpecLoopManager:
    def __init__(self, spec_dir: str, llm_client: LLMClient):
        self.spec_dir = spec_dir
        self.llm = llm_client
        self.updater = SpecUpdater(spec_dir)

    def refine_specs(self, feedback: str):
        """Analyze feedback and update specs accordingly."""
        # 1. Load current specs
        specs = {}
        for filename in ["AGENT_INSTRUCTIONS.md", "COPILOT_INSTRUCTIONS.md"]:
            path = os.path.join(self.spec_dir, filename)
            if os.path.exists(path):
                with open(path, "r") as f:
                    specs[filename] = f.read()

        # 2. Propose updates
        prompt = f"""You are an FSM Evolution Agent. Based on the following feedback and current specs, propose specific updates.
Feedback: {feedback}

Current Specs:
{json.dumps(specs, indent=2)}

Propose updates in the following format:
FILE: <filename>
ACTION: <update_param|update_instruction|update_vault>
KEY/ID: <key or state_id>
VALUE/TEXT: <new value or text>
---
(Repeat for each update)
"""
        proposal = self.llm.chat([
            {"role": "system", "content": "You provide precise FSM specification updates."},
            {"role": "user", "content": prompt}
        ])

        print(f"PROPOSAL:\n{proposal}")

        # 3. Apply updates
        updates = proposal.split("---")
        for update in updates:
            if not update.strip(): continue
            try:
                lines = update.strip().split("\n")
                data = {}
                for line in lines:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        data[k.strip()] = v.strip()
                
                action = data.get("ACTION")
                key = data.get("KEY/ID")
                val = data.get("VALUE/TEXT")

                if action == "update_param":
                    self.updater.update_param(key, val)
                elif action == "update_instruction":
                    self.updater.update_instruction(key, val)
                elif action == "update_vault":
                    self.updater.update_vault(key, val)
            except Exception as e:
                print(f"Error applying update: {e}")

        return proposal

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python fsm/spec_loop_manager.py 'feedback string'")
        sys.exit(1)
    
    client = LLMClient()
    manager = SpecLoopManager("fsm/specs", client)
    manager.refine_specs(sys.argv[1])
