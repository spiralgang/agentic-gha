# FSM: RepoSDLC

Initial: examine

## States
- examine : survey the repository and pick a task issue
- plan : write a concrete development plan
- build : implement the change and open a PR
- review : GLM reviews the PR and returns a verdict
- fix : apply review fixes to the branch
- approve : approve, merge, close, and loop
- evolve : analyze the system and update its own specs

## Transitions
- examine -> plan : True
- plan -> build : True
- build -> review : True | attempt = 0
- review -> fix : verdict == 'FIX' | attempt += 1
- review -> approve : verdict == 'APPROVE'
- fix -> review : attempt < max_fix
- fix -> approve : attempt >= max_fix
- approve -> examine : cycle < max_cycles | cycle += 1
- approve -> evolve : cycle >= max_cycles
- evolve -> examine : True | cycle = 0
