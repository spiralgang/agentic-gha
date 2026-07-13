# AGENT_INSTRUCTIONS

Per-state behavior the machine follows on entry.

## examine
Survey the repository. List open issues labeled agent-task. Summarize the repo
purpose, tech stack, and the selected issue in 3-5 lines. Pick the first open
task and move to planning.

## plan
Read the selected issue. Produce a concrete plan: files to create/modify,
approach, expected behavior. Create the feature branch and push it.

## build
Implement the change per the plan. Commit, push, and open a PR against main
labeled agent-task. Hand off to review.

## review
Run GLM-4 over the PR diff. Output a verdict: APPROVE or FIX. Attach the review
as a PR comment. The machine branches on that verdict.

## fix
Apply the review feedback to the branch. Commit and push. Loop back to review
until attempt reaches max_fix, then force-approve.

## approve
Approve and squash-merge the PR, close the issue. Increment cycle and, if
cycle < max_cycles, return to examine to start a new task.
