# VAULT

Long-term knowledge the machine and agents may reference.

## guard_policy
Never merge on an ambiguous verdict. Default to FIX when the review is unclear
or the LLM call fails, so broken code is never merged.

## safety_caps
MAX_FIX bounds the review/fix loop; MAX_CYCLES bounds the whole SDLC loop.

## model_notes
GLM-4-flash is used for all reasoning stages (examine, plan, review) for speed
and cost. Swap it via the model parameter in COPILOT_INSTRUCTIONS.md.
