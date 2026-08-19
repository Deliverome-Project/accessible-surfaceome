"""Measure repo lit-search recall of the KNOWN control papers across the control
set, naive vs tuned queries. Tuning levers: (1) protein-name synonyms (methods
papers rarely use the gene symbol), (2) task vocabulary (ecto-tagged, HiBiT,
pHluorin, surface labeling, knock-in, nanobody...). EuropePMC (keyword) + PubTator
(gene-entity NER). A control paper is 'found' if it appears in the top hits by
PMCID/PMID or a distinctive title substring.
"""
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.europepmc import europepmc_search
from accessible_surfaceome.tools._shared.pubtator import pubtator_search, build_gene_entity_query

http = open_default_client()

# gene -> (aliases, control-paper markers: pmcid set + title substrings)
CTRL = {
    "SELE":    (["SELE", "E-selectin", "CD62E"], {"pmcid": {"PMC10366498"}, "t": ["e-selectin", "hibit"]}),
    "ADRB2":   (["ADRB2", "beta 2 adrenergic", "β2-adrenergic", "beta2 adrenoceptor"], {"pmcid": {"PMC7152755"}, "t": ["adrenergic"]}),
    "CALCR":   (["CALCR", "calcitonin receptor"], {"pmcid": {"PMC5832441"}, "t": ["phase-plate", "calcitonin"]}),
    "GIPR":    (["GIPR", "GIP receptor", "gastric inhibitory"], {"pmcid": {"PMC7438548"}, "t": ["gip receptor", "fluorescent labelling"]}),
    "GLP1R":   (["GLP1R", "GLP-1 receptor", "glucagon-like peptide"], {"pmcid": {"PMC4344312"}, "t": ["glp-1"]}),
    "NPY1R":   (["NPY1R", "neuropeptide Y", "Y1 receptor"], {"pmcid": {"PMC8844075"}, "t": ["neuropeptide y"]}),
    "ITGB1":   (["ITGB1", "integrin beta 1", "beta1 integrin", "β1 integrin", "CD29"], {"pmcid": {"PMC5603536"}, "t": ["ecto-tagged"]}),
    "ITGB5":   (["ITGB5", "integrin beta 5", "αvβ5", "alpha v beta 5"], {"pmcid": set(), "t": ["endonb", "internalization of cell surface"]}),
    "TFRC":    (["TFRC", "transferrin receptor", "TfR", "CD71"], {"pmcid": set(), "t": ["endonb", "internalization of cell surface"]}),
    "AXL":     (["AXL", "AXL receptor"], {"pmcid": set(), "t": ["endonb", "internalization of cell surface"]}),
    "TMEM123": (["TMEM123", "porimin"], {"pmcid": set(), "t": ["endonb", "internalization of cell surface"]}),
    "TRPC5":   (["TRPC5", "transient receptor potential canonical 5"], {"pmcid": {"PMC8878318"}, "t": ["dogcatcher", "loop-friendly"]}),
    "SLC6A4":  (["SLC6A4", "serotonin transporter", "SERT", "hSERT"], {"pmcid": {"PMC4132800"}, "t": []}),
    "SLC6A3":  (["SLC6A3", "dopamine transporter", "hDAT"], {"pmcid": {"PMC6673793"}, "t": []}),
    "EDNRB":   (["EDNRB", "endothelin receptor"], {"pmcid": {"PMC10129325"}, "t": ["endothelin"]}),
    "KCNH2":   (["KCNH2", "hERG", "Kv11.1"], {"pmcid": {"PMC5917007"}, "t": ["kanner"]}),
}

METHODS = ('("epitope tag" OR "HA tag" OR "FLAG tag" OR "Myc tag" OR "ecto-tagged" OR '
           '"epitope-tagged" OR "extracellular epitope" OR "surface labeling" OR '
           '"cell surface expression" OR "knock-in" OR pHluorin OR HiBiT OR HaloTag OR '
           'ALFA OR DogTag OR SpyTag OR bungarotoxin OR nanobody OR "extracellular loop")')
PT_METHODS = "epitope tag extracellular surface labeling knock-in nanobody insertion"


def matched(hits, mk):
    for h in hits:
        pmcid = (h.get("pmcid") or "") if isinstance(h, dict) else ""
        title = ((h.get("title") if isinstance(h, dict) else h.title) or "").lower()
        if pmcid and pmcid in mk["pmcid"]:
            return True
        if any(s in title for s in mk["t"]):
            return True
    return False


def epmc(query, n=25):
    try:
        return europepmc_search(http=http, query=query, page_size=n).get("resultList", {}).get("result", [])
    except Exception:
        return []


def pt(query):
    try:
        return pubtator_search(http=http, query=query).hits
    except Exception:
        return []


rows = []
for gene, (aliases, mk) in CTRL.items():
    alt = "(" + " OR ".join(f'"{a}"' if " " in a else a for a in aliases) + ")"
    e_naive = matched(epmc(f"{gene} epitope tag"), mk)
    e_tuned = matched(epmc(f"{alt} AND {METHODS}"), mk)
    p_naive = matched(pt(build_gene_entity_query(gene, "epitope tag")), mk)
    p_tuned = matched(pt(build_gene_entity_query(gene, PT_METHODS)), mk)
    rows.append((gene, e_naive, e_tuned, p_naive, p_tuned))
    print(f"{gene:9} EPMC naive={'Y' if e_naive else '.'} tuned={'Y' if e_tuned else '.'}   "
          f"PubTator naive={'Y' if p_naive else '.'} tuned={'Y' if p_tuned else '.'}")

n = len(rows)
def rate(i):
    return sum(1 for r in rows if r[i])
print(f"\nRECALL over {n} controls:")
print(f"  EuropePMC   naive {rate(1)}/{n}   tuned {rate(2)}/{n}")
print(f"  PubTator    naive {rate(3)}/{n}   tuned {rate(4)}/{n}")
print(f"  EITHER tuned (EPMC or PubTator): {sum(1 for r in rows if r[2] or r[4])}/{n}")
