"""Build viewer/public/data/gene_names.json from the NCBI triageable TSV.

The viewer's catalog rows carry only ``symbol`` + ``uniprot``; this companion
file maps each symbol to a human-readable gene name + ``|``-separated
synonyms so the catalog search input can match aliases like
``transferrin`` → ``TF`` and the gene-page header can render the name
under the symbol.

Source: ``data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.triageable.tsv``.
Output: ``viewer/public/data/gene_names.json`` shaped as
``{ generated_at, n_genes, names: { SYMBOL: { name, synonyms: [...] } } }``.

Run:
    uv run python scripts/build_gene_names_json.py
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TSV = (
    ROOT
    / "data"
    / "external"
    / "ncbi_gene_info"
    / "Homo_sapiens.protein_coding.with_hgnc.triageable.tsv"
)
OUT = ROOT / "viewer" / "public" / "data" / "gene_names.json"


def main() -> None:
    names: dict[str, dict[str, object]] = {}
    with TSV.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            symbol = row.get("gene_symbol", "").strip()
            if not symbol:
                continue
            name = row.get("description", "").strip()
            raw_syn = row.get("synonyms", "").strip()
            synonyms = (
                [s for s in raw_syn.split("|") if s and s != "-"]
                if raw_syn and raw_syn != "-"
                else []
            )
            names[symbol] = {"name": name, "synonyms": synonyms}

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_genes": len(names),
        "source": "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.triageable.tsv",
        "names": names,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {len(names):,} gene names to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
