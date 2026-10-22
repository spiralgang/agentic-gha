import os
import ast
import re

def parse_compiled_fsm(path):
    with open(path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    data = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    if name in ('STATES', 'TRANSITIONS', 'INSTRUCTIONS', 'VAULT', 'INITIAL', 'PARAMS', 'NAME'):
                        # Simple evaluation of literals
                        try:
                            data[name] = ast.literal_eval(node.value)
                        except ValueError:
                            pass
    return data

def generate_plans(data):
    name = data.get('NAME', 'UnnamedFSM')
    initial = data.get('INITIAL', 'examine')
    states = data.get('STATES', {})
    transitions = data.get('TRANSITIONS', [])
    
    lines = [f"# FSM: {name}", f"Initial: {initial}", "", "## States"]
    for s, d in states.items():
        lines.append(f"- {s} : {d}")
    
    lines.append("")
    lines.append("## Transitions")
    for (frm, to, guard, action) in transitions:
        action_part = f" | {action}" if action else ""
        lines.append(f"- {frm} -> {to} : {guard}{action_part}")
    
    return "\n".join(lines)

def generate_instructions(data):
    instr = data.get('INSTRUCTIONS', {})
    # Separate the header/intro if it exists
    lines = []
    for k, v in instr.items():
        if k == 'AGENT_INSTRUCTIONS':
            lines.append(f"# AGENT_INSTRUCTIONS\n\n{v}\n")
        else:
            lines.append(f"## {k}\n{v}\n")
    return "\n".join(lines)

def generate_vault(data):
    vault = data.get('VAULT', {})
    lines = []
    for k, v in vault.items():
        if k == 'VAULT':
            lines.append(f"# VAULT\n\n{v}\n")
        else:
            lines.append(f"## {k}\n{v}\n")
    return "\n".join(lines)

def sync_readme(root):
    readme_path = os.path.join(root, 'README.md')
    if not os.path.exists(readme_path):
        return
    
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the table. This is tricky. We'll just scan for workflows and 
    # ensure they are mentioned in the text.
    workflows = []
    wf_dir = os.path.join(root, '.github', 'workflows')
    if os.path.exists(wf_dir):
        workflows = sorted([f for f in os.listdir(wf_dir) if f.endswith('.yml')])
    
    for wf in workflows:
        if wf not in content:
            # Append to a "Workflows" section if it exists, otherwise just add at end
            if "## Workflows" in content:
                content = content.replace("## Workflows", f"## Workflows\n\n- {wf}\n", 1)
            else:
                content += f"\n\n## Workflows\n- {wf}"
                break # Add section once
                
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    root = '/home/bigbirdbloc/agentic-gha'
    compiled_path = os.path.join(root, 'fsm', 'fsm_compiled.py')
    if not os.path.exists(compiled_path):
        print(f"Error: {compiled_path} not found")
        return

    data = parse_compiled_fsm(compiled_path)
    
    specs_dir = os.path.join(root, 'fsm', 'specs')
    os.makedirs(specs_dir, exist_ok=True)
    
    files_to_write = {
        'PLANS.md': generate_plans(data),
        'AGENT_INSTRUCTIONS.md': generate_instructions(data),
        'VAULT.md': generate_vault(data),
    }
    
    for fname, content in files_to_write.items():
        path = os.path.join(specs_dir, fname)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                if f.read() == content:
                    continue
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
            print(f"Updated {fname}")
    
    sync_readme(root)

if __name__ == '__main__':
    main()
