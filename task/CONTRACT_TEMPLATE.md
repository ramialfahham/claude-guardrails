# Task contract

Copy this to `.claude/task/contract.md` at the start of a unit of work, fill it
in, and state it back to the owner before writing code.

objective: <one sentence — what this unit of work delivers>

scope_paths:
  - <a path or glob the work may touch, e.g. models/marts/**>
  - <one per line — edits outside this list are drift>

decisions_reserved:
  - <any choice you must NOT make without the owner — or "(none)">

done_when:
  - <the check that proves it is finished, e.g. "dbt build + tests pass in CI">

# Optional — include only when the work touches models / ingestion / consumption:
impact_map: <which downstream models or outputs change, traced with evidence
  (e.g. the output of `dbt ls --select <model>+`), or "(none)" with the reason>

amendments:
  - <date — what changed in this contract, and the owner authority for it>
