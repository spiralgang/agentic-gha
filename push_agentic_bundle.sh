#!/usr/bin/env bash
# push_agentic_bundle.sh  —  push the agentic-gha .github/ bundle to all OWNED repos as PRs.
set -uo pipefail
SRC="/home/spiralgang/agentic-gha"
WORK="/tmp/agentic_push"
OWNER="spiralgang"
BRANCH="feat/agentic-gha-workflows"
PR_TITLE="feat: add agentic GitHub Actions workflows (real-LLM, FSM, living-code)"
PR_BODY="$(cat <<'BODY'
Agentic GitHub Actions workflows derived from your ~/ markdown layouts.

- 17 workflows: 6-stage self-driving SDLC loop (examine→plan→build→review→fix→approve), FSM self-compile, living-code matrix, GLM companion, ARIA autorepair, edge codespace, omniscient IDE safety gate, Zhipu orchestrator, termux-ai skills, device-privacy build, main CI, watchdog.
- Shared real-LLM composite action (.github/actions/llm/action.yml): no mock — fails loudly without LLM_API_KEY / ZHIPU_API_KEY.
- Seccomp sandbox reusable workflow (json-py.md).
- Every workflow calls a REAL model and adapts to the repo (stages that need local files skip gracefully).

Required secrets (add in repo Settings → Secrets): LLM_API_KEY, LLM_BASE_URL (optional), LLM_MODEL (optional), ZHIPU_API_KEY.

Triggers:
  gh workflow run sdlc-examine.yml -f cycle=0
  gh workflow run livingcode-matrix.yml -f children=4 -f cycles=2
BODY
)"

mkdir -p "$WORK"
# enumerate owned, non-fork, non-archived repos
mapfile -t REPOS < <(gh repo list "$OWNER" --limit 200 --json name,isFork,isArchived --jq '.[] | select(.isFork==false and .isArchived==false) | .name')

echo "Owned repos to target: ${#REPOS[@]}"
ok=0; skip=0; fail=0
for R in "${REPOS[@]}"; do
  echo "=== $R ==="
  # skip the bundle's own home repo (already has it)
  if [ "$R" = "agentic-gha" ]; then echo "  skip (home repo)"; skip=$((skip+1)); continue; fi
  D="$WORK/$R"
  rm -rf "$D"
  if ! gh repo clone "$OWNER/$R" "$D" -- --depth 1 2>/tmp/cl_$R.log; then
    echo "  clone failed ($(head -1 /tmp/cl_$R.log))"; fail=$((fail+1)); continue
  fi
  # do not clobber existing .github — merge: only add what's missing
  mkdir -p "$D/.github"
  ADDED=0
  for f in $(cd "$SRC" && find .github -type f); do
    if [ ! -f "$D/$f" ]; then
      mkdir -p "$(dirname "$D/$f")"
      cp "$SRC/$f" "$D/$f"
      ADDED=$((ADDED+1))
    fi
  done
  # also ship the living-code engine at repo root (skip if present)
  if [ ! -f "$D/superlab_fsm_living_code.py" ]; then
    cp "$SRC/superlab_fsm_living_code.py" "$D/superlab_fsm_living_code.py"
    ADDED=$((ADDED+1))
  fi
  if [ "$ADDED" -eq 0 ]; then echo "  nothing new to add (already present)"; skip=$((skip+1)); continue; fi
  cd "$D"
  git config user.email "agent@noreply.local"; git config user.name "spiralgang"
  git checkout -b "$BRANCH"
  git add -A
  git commit -q -m "feat: add agentic GitHub Actions workflows bundle"
  if git push -u origin "$BRANCH" 2>/tmp/ps_$R.log; then
    gh pr create --title "$PR_TITLE" --body "$PR_BODY" --head "$BRANCH" --base main 2>/tmp/pr_$R.log \
      || gh pr create --title "$PR_TITLE" --body "$PR_BODY" --head "$BRANCH" --base master 2>>/tmp/pr_$R.log \
      || { echo "  PR create failed ($(head -1 /tmp/pr_$R.log))"; }
    echo "  PR opened (added $ADDED files)"; ok=$((ok+1))
  else
    echo "  push failed ($(head -1 /tmp/ps_$R.log))"; fail=$((fail+1))
  fi
done
echo "DONE: ok=$ok skip=$skip fail=$fail total=${#REPOS[@]}"