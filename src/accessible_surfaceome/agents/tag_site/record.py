"""Who owns which field of a tag-sites record.

One ``viewer/public/tag-sites/{SYMBOL}.json`` is written by two independent
pipelines — the deterministic one (`scripts/regenerate_tag_sites.py`) and the
literature agent (`scripts/regenerate_tag_site_lit.py`) — and each used to
rebuild the record's top level from scratch. Whatever the other had written was
erased, silently, with nothing in the output to say so.

That is not hypothetical; it happened three times in one day:

* ``publish_tag_sites`` deleted every D1 row for a gene before inserting, so
  syncing a literature-only file removed the gene's deterministic rows;
* running the deterministic lanes across the control panel took every gene from
  "stamped with the prompt that produced it" back to "no provenance" — the
  literature SITES were preserved and their provenance was not, which is the
  worst combination, because the sites then look current and cannot be dated;
* ``rejected`` was added to the schema and the model promptly filled it with its
  own editorial notes, because nothing declared the field was the pipeline's.

The fix is not a longer list of keys to remember in each script. It is one
place that says who owns what, a merge both writers go through, and a test that
fails when a new field is added without an owner — so the next field cannot
repeat this by omission.
"""

from __future__ import annotations

from typing import Any, Literal

Owner = Literal["deterministic", "literature", "shared"]

#: Identity of the record. Either writer may set these; they must agree.
SHARED_KEYS: tuple[str, ...] = ("gene_symbol", "uniprot_acc", "has_data", "sites")

#: Written only by the deterministic pipeline.
DETERMINISTIC_KEYS: tuple[str, ...] = ("isoform_pins", "ortholog_pins")

#: Written only by the literature agent — its prompt provenance and its own
#: account of the run. The provenance rule makes these mandatory, so erasing
#: them is not a cosmetic loss: a record with sites and no prompt_sha claims to
#: be current and cannot be checked.
LITERATURE_KEYS: tuple[str, ...] = (
    "schema_version",
    "prompt_sha",
    "prompt_version",
    "model",
    "generated_at",
    "literature_notes",
    "literature_rejected",
)

_OWNER_OF: dict[str, Owner] = {
    **{k: "shared" for k in SHARED_KEYS},
    **{k: "deterministic" for k in DETERMINISTIC_KEYS},
    **{k: "literature" for k in LITERATURE_KEYS},
}


def owner_of(key: str) -> Owner | None:
    """Which pipeline owns ``key``, or None when it is unclassified."""
    return _OWNER_OF.get(key)


def unclassified(record: dict[str, Any]) -> list[str]:
    """Keys in ``record`` that no pipeline claims.

    A new top-level field must be given an owner here, or the next write by the
    other pipeline drops it without a word."""
    return sorted(k for k in record if k not in _OWNER_OF)


def merge(
    existing: dict[str, Any] | None,
    updates: dict[str, Any],
    *,
    owner: Owner,
) -> dict[str, Any]:
    """Apply ``updates`` from ``owner`` onto ``existing``, keeping the rest.

    The writer supplies the shared identity and the keys it owns; every key
    owned by the OTHER pipeline is carried across untouched. An unclassified key
    is also carried across — losing data is worse than carrying a field whose
    owner nobody declared, and the test is what forces it to be declared.
    """
    base = dict(existing or {})
    foreign = {k: v for k, v in base.items() if _OWNER_OF.get(k) not in (owner, "shared")}
    merged = {**base, **updates}
    # updates must not silently drop another owner's fields, even if the writer
    # passed an exhaustive-looking dict.
    for k, v in foreign.items():
        if k not in updates:
            merged[k] = v
    return merged
