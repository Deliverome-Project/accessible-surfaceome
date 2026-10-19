# `terminal_c` rows vs the C-terminal cleavage annotations

`terminal_c_cleavage.tsv` — every one of the 1,068 `terminal_c` rows in
`tag_site_public` (981 deterministic, 87 not), each against UniProt's
`Propeptide` and GPI `Lipidation`, with the NetGPI call alongside for
corroboration. Built by
[`scripts/audit/audit_terminal_c_cleavage.py`](../../../scripts/audit/audit_terminal_c_cleavage.py).

The terminal lane decided from the DeepTMHMM topology string alone: the chain
ends extracellular, so propose a C-terminal tag. A GPI-anchored protein's
precursor C-terminus is removed at the ω-site and replaced by the anchor, so
that residue is not on the mature protein — and the string ends extracellular
either way.

## Counts

| | |
|---|---|
| deterministic `terminal_c` rows | 981 |
| refused — C-terminus inside a cleaved span | **116** |
|  · GPI by UniProt *and* called by NetGPI | 112 |
|  · GPI by UniProt `Lipidation`, **missed by NetGPI** | 3 — ITLN1 (ω 298), TECTA (ω 2091), TECTB (ω 305) |
|  · non-GPI C-terminal propeptide | 1 — CLN3 (436-438) |
| NetGPI-anchored but UniProt-silent, so not refused | 3 — CLCA4, GML, GPC5 |

Non-GPI is reported separately on purpose: CLN3's 3-residue cleaved tail is
still cleaved, so the refusal is right, but it is not the population the fix was
measured on.

## Why UniProt is the source and NetGPI is not

The two disagree by 3 in each direction, and the disagreements are not
symmetric in quality.

UniProt's extra three each carry a curated `Lipidation` **and** a `Propeptide`.
NetGPI's extra three are **GML**, with no ω-site at all, and **GPC5**, which
reports ω = 27 of 572 residues — a number in whichever form was submitted rather
than the canonical frame these records are numbered against. Only CLCA4 is a
real miss.

So UniProt is strictly better on the disagreements, at no new dependency: the
features list is already fetched for the hazard veto. NetGPI stays as
corroboration, read via `--gpi-set`, never by the gate. Resolving a predicted
ω-site into the record's frame is the sha256-of-sequence problem, not a column
read.

The list itself is `gpi_set.tsv` (159 genes with ω-sites) in
`deliverome-analysis` at `analysis/sprint4/s4e9-orf-design-fg-panel/`, commit
`d541e6a6` — on branches only, never on that repo's `main`.

## Three sources, and only one of them can locate the cleavage

A later cross-check against **UniProt keyword KW-0336** (144 reviewed human
entries) separates two questions that read as one:

| source | answers | for the gate |
|---|---|---|
| KW-0336 keyword | *whether* a protein is GPI-anchored | not enough |
| `Propeptide` / GPI `Lipidation` features | *where* the cleavage is | **what the gate reads** |
| NetGPI `gpi_set.tsv` | predicted, in the submitted form's numbering | corroboration only |

Membership is not the annotation. **GML and GPC5 carry KW-0336 and still have no
locating feature**, so the keyword says "GPI" while the feature table cannot say
where — which is exactly why `cleaved_c_terminus` reads features and not
keywords.

The three sources disagree in every direction, and the counts are a trap:
the `terminal_c` split is **115 deterministic / 10 literature** under NetGPI and
**116 / 9** under KW-0336, both totalling 125. That agreement is a coincidence —
the sets differ by ISLR. And there are two distinct 116s here that overlap on only
114 rows: the 116 *refused* rows, and the 116 KW-0336 deterministic rows. They
differ by CLN3 and PRSS8 (refused, not in KW-0336) versus GML and GPC5 (in
KW-0336, not refused). Quote which 116 you mean.

**ISLR is a NetGPI false positive.** NetGPI calls it anchored at ω 403 with
likelihood 0.220, its lowest band. UniProt gives it no `Propeptide` and no
`Lipidation`, and its `Chain` runs 19-428 — the whole mature protein to the
C-terminus, which is not the shape of a GPI precursor. It is absent from KW-0336.
So Islr-GFP working as a C-terminal fusion is unremarkable rather than a
counterexample, and the literature count on genuinely anchored genes is **9**.
**PRSS8** runs the other way: a real GPI protein with both features that KW-0336
omits. No single membership list is complete.

## Not republished

Fixed in code (`cfbcaee42`); `tag_site_public` still carries all 116. Correcting
them needs the paced AFDB re-derive — ~9 s/request, since AFDB `/files/`
IP-bans bursts.
