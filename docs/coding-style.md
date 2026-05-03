# Coding style

A reader landing on this repo should find what each file does and follow the
algorithm without first subtracting a layer of plumbing. Break the defaults
below when you have a reason.

- **Show the science; hide the plumbing.** Long is fine when it's the algorithm.
- **Names describe what's there.** The tree is the table of contents.
- **One way to do common things.** Re-derivations are how drift starts.
- **Match complexity to need.** Don't engineer for failure modes you don't have.
- **Three similar lines beat a premature abstraction.** If apparent uniformity is shallow, duplicate.
- **Docstrings explain WHY, not WHAT.** Long rationale lives in `docs/reports/`.
- **Imports at the top; no side effects on import.**
- **Trust framework guarantees; validate at real boundaries only.**
- **Every derived artifact carries a traceability manifest.**
- **Tooling is settled** — `uv`, `ruff`, `ty`, `pytest`. Don't reach past it.
