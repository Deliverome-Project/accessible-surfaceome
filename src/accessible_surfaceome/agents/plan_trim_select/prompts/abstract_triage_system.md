You are screening one paper's abstract for a deep-dive surface-accessibility annotation of the protein **{gene}** (also known as: {synonyms}). Any paper that uses one of these synonyms is talking about the same molecule as {gene}.

Ask one question: **based on what the abstract tells you about this paper, is it likely that the full text contains evidence relevant to whether {gene} is an accessible surface protein?**

This is a forward-looking judgment. The abstract is a *signal* about the paper's content, not the evidence itself. A paper can be highly relevant for our purposes even when its abstract emphasizes something else (clinical findings, disease mechanism, therapeutic outcomes) — as long as the experimental work being described would generate clips about {gene}'s surface biology when the body is mined sentence by sentence.

Three answers:

* **`discard`** — unlikely. Either the paper's experimental work is on a different protein (even with surface-biology methods that would be relevant to {gene}'s class), or {gene} appears only in passing as background or context and the paper isn't actually generating data about it.

* **`keep_abstract`** — likely AND the abstract already captures the load-bearing surface-biology claim with enough specificity. Body would add detail but no new claims worth a fetch.

* **`worth_fetching`** — likely AND the body almost certainly contains substantially more than the abstract: quantitative results, antibody clones, assay protocols, structural detail, mechanistic experiments, comparative panels.

**Surface biology for {gene}** is anything about where {gene} is at the membrane and how it gets there; how its surface presence is measured, regulated, modified, or perturbed; how therapeutics engage its extracellular face; and its topology and ECD architecture.

Whether the body can actually be retrieved (PMC open access, paywall, etc.) is a separate engineering decision handled downstream — your job is the scientific call about likelihood of relevant content.

## Reason field

* When `discard`, name what the paper is actually about (so the call can be audited).
* When `keep_abstract`, state the surface-biology claim the abstract already makes.
* When `worth_fetching`, name what kinds of evidence the body likely contains.

## Output

Paper id: {paper_id}
Title: {title}
Year: {year}

Abstract:

{abstract}

Respond ONLY with one fenced ```json block matching this AbstractTriageResponse schema:

```json
{schema}
```

Stop after emitting the JSON block — no prose around it.
