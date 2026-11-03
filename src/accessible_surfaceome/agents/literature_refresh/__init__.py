"""Incremental literature refresh for published deep-dive records.

A full re-annotation re-reads every paper for a gene (~$1.60/gene). Most genes
gain zero or one relevant paper per quarter, so a refresh only needs to look at
what was published *after* the record was generated:

1. **discover** ($0) — re-run the deterministic kickoff searches with the search
   endpoints' cache bypassed, resolve exact publication dates, and keep papers
   published after the record's generation date that the record does not
   already cite and that name the gene. :mod:`.discover`
2. **screen** (cents) — abstract-triage, fetch, trim and select only those new
   papers, numbering the new claims after the record's existing evidence ids.
3. **impact gate** ($0) — decide from the new claims which builders they can
   affect, and skip the replay when nothing new could change a call.
4. **targeted replay** — re-run only the affected builders (reusing the cached
   outputs of the rest) plus the synthesizer, and diff the result against the
   published record. Nothing is published by default.
"""
