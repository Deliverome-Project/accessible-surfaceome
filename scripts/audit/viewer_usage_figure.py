"""Slide figure: is the Surfaceome viewer being used?

Pulls Cloudflare Web Analytics (cookie-free RUM, adaptively sampled) for
``surfaceome.deliverome.org`` over the last 90 days — just inside the
13 weeks the account's GraphQL API serves — plus the Zenodo data record's download count,
and renders a three-panel summary:

  a. visits and page views by region (US, Europe, Asia, other)
  b. page views by country (top 10)
  c. page views by part of the viewer (catalog, gene pages, API docs, ...)

A "visit" is a page load that arrived from outside the site (Cloudflare's
definition), the closest cookie-free proxy for a person-session; there is no
unique-visitor count. Numbers are sampled estimates.

Needs CLOUDFLARE_API_TOKEN (Account Analytics: Read) + CLOUDFLARE_ACCOUNT_ID.

Usage::

    uv run python scripts/audit/viewer_usage_figure.py
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import httpx
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.container import BarContainer

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)
from accessible_surfaceome.env import load_env

OUT_DIR = Path("data/analysis/viewer_usage")
VIEWER = "surfaceome.deliverome.org"
# UN geoscheme continents; Western Asia (IL, TR, Gulf states) counts as Asia.
EUROPE = set(
    "AD AL AT BA BE BG BY CH CY CZ DE DK EE ES FI FR GB GR HR HU IE IS IT LI LT "
    "LU LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SK SM UA VA XK".split()
)
ASIA = set(
    "AE AF AM AZ BD BH BN BT CN GE HK ID IL IN IQ IR JO JP KG KH KR KW KZ LA LB "
    "LK MM MN MO MV MY NP OM PH PK PS QA SA SG SY TH TJ TL TM TR TW UZ VN YE".split()
)
REGIONS = ["United States", "Europe", "Asia", "Other"]
ZENODO_CONCEPT = "20805383"
SECTIONS = {
    "": "Catalog (home)",
    "api": "API docs",
    "benchmark": "SurfaceBench",
    "prompts": "Prompts",
    "compare": "Compare",
    "reproducibility": "Reproducibility",
    "privacy": "Other",
}

QUERY = """
query($acc: string!, $since: Date!) { viewer { accounts(filter:{accountTag:$acc}) {
  # Grouping both by date and requestHost keeps Cloudflare's adaptive sampling
  # fine-grained; a bare country rollup returns a handful of coarse rows.
  countries: rumPageloadEventsAdaptiveGroups(limit: 10000, filter:{date_geq:$since, requestHost:"%s"}) {
    count sum { visits } dimensions { date requestHost countryName } }
  paths: rumPageloadEventsAdaptiveGroups(limit: 10000, filter:{date_geq:$since, requestHost:"%s"}) {
    count dimensions { date requestHost requestPath } }
}}}
""" % (VIEWER, VIEWER)


def fetch_rum(since: dt.date) -> dict:
    r = httpx.post(
        "https://api.cloudflare.com/client/v4/graphql",
        headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
        json={
            "query": QUERY,
            "variables": {
                "acc": os.environ["CLOUDFLARE_ACCOUNT_ID"],
                "since": since.isoformat(),
            },
        },
        timeout=60,
    )
    body = r.json()
    if body.get("errors"):
        raise SystemExit(f"Cloudflare GraphQL error: {body['errors']}")
    return body["data"]["viewer"]["accounts"][0]


def zenodo_unique_downloads() -> int | None:
    try:
        r = httpx.get(
            f"https://zenodo.org/api/records/{ZENODO_CONCEPT}",
            follow_redirects=True,
            timeout=30,
        )
        return int(r.json()["stats"]["unique_downloads"])
    except httpx.HTTPError, KeyError, ValueError:
        return None


def region_of(country: str) -> str:
    if country == "US":
        return "United States"
    if country in EUROPE:
        return "Europe"
    if country in ASIA:
        return "Asia"
    return "Other"


def section_of(path: str) -> str:
    seg = path.strip("/")
    if "/" in seg:
        return "Other"
    return SECTIONS.get(seg.lower(), "Gene pages")


def main() -> None:
    load_env()
    today = dt.date.today()
    # Exactly 13 weeks back sits on the API's retention edge, where the
    # per-day country query intermittently returns no rows at all.
    since = today - dt.timedelta(days=90)
    rum = fetch_rum(since)
    if not rum["countries"] or not rum["paths"]:
        raise SystemExit("Cloudflare returned no RUM rows; retry or shorten the window")

    countries = pd.DataFrame(
        {
            "country": g["dimensions"]["countryName"],
            "views": g["count"],
            "visits": g["sum"]["visits"],
        }
        for g in rum["countries"]
    )
    countries = (
        countries.groupby("country", as_index=False)[["views", "visits"]]
        .sum()
        .sort_values("views", ascending=False)
    )
    countries["region"] = countries["country"].map(region_of)
    regions = (
        countries.groupby("region")[["visits", "views"]]
        .sum()
        .reindex(REGIONS, fill_value=0)
        .reset_index()
    )
    regions_long = regions.melt(
        id_vars="region", var_name="metric", value_name="n"
    ).replace({"metric": {"visits": "Visits", "views": "Page views"}})
    paths = pd.DataFrame(
        {"path": g["dimensions"]["requestPath"], "views": g["count"]}
        for g in rum["paths"]
    )
    paths["section"] = paths["path"].map(section_of)
    sections = (
        paths.groupby("section", as_index=False)["views"]
        .sum()
        .sort_values("views", ascending=False)
    )
    sections = sections[sections["section"] != "Other"].reset_index(drop=True)
    genes = paths.loc[paths["section"] == "Gene pages", "path"].str.strip("/")
    n_genes = genes.str.upper().nunique()

    total_views, total_visits = (
        int(countries["views"].sum()),
        int(countries["visits"].sum()),
    )
    n_countries = countries["country"].nunique()
    zen = zenodo_unique_downloads()

    setup_plotting_style(font_scale=1.4)
    fig = plt.figure(figsize=(16, 9))
    grid = fig.add_gridspec(2, 2, height_ratios=[1, 1], width_ratios=[1.35, 1])
    ax_a = fig.add_subplot(grid[:, 0])
    ax_b = fig.add_subplot(grid[0, 1])
    ax_c = fig.add_subplot(grid[1, 1])

    sns.barplot(
        data=regions_long,
        x="region",
        y="n",
        hue="metric",
        hue_order=["Visits", "Page views"],
        palette=[COLORS["primary"], COLORS["secondary"]],
        ax=ax_a,
    )
    for bars in (c for c in ax_a.containers if isinstance(c, BarContainer)):
        ax_a.bar_label(
            bars,
            labels=[f"{b.get_height():,.0f}" for b in bars],
            fontsize=13,
            padding=3,
        )
    ax_a.set_ylim(0, regions_long["n"].max() * 1.1)
    ax_a.set_xlabel("")
    ax_a.set_ylabel("Visits and page views, last 90 days")
    ax_a.legend(title=None, frameon=False, loc="upper right")
    ax_a.text(0, 1.03, "a", transform=ax_a.transAxes, fontsize=22, fontweight="bold")
    sns.despine(ax=ax_a, top=True, right=True)

    top = countries.head(10)
    sns.barplot(data=top, y="country", x="views", color=COLORS["primary"], ax=ax_b)
    ax_b.set_ylabel("")
    ax_b.set_xlabel(f"Page views ({n_countries} countries total)")
    ax_b.text(
        -0.25, 1.03, "b", transform=ax_b.transAxes, fontsize=22, fontweight="bold"
    )
    sns.despine(ax=ax_b, top=True, right=True)

    sns.barplot(
        data=sections, y="section", x="views", color=COLORS["secondary"], ax=ax_c
    )
    ax_c.set_ylabel("")
    ax_c.set_xlabel(f"Page views by section ({n_genes}+ distinct genes opened)")
    for i, n in enumerate(sections["views"]):
        ax_c.text(n, i, f" {n:,}", va="center", fontsize=12)
    ax_c.set_xlim(0, sections["views"].max() * 1.18)
    ax_c.text(
        -0.25, 1.03, "c", transform=ax_c.transAxes, fontsize=22, fontweight="bold"
    )
    sns.despine(ax=ax_c, top=True, right=True)

    headline = (
        f"~{total_visits:,} visits  ·  ~{total_views:,} page views  ·  "
        f"{n_countries} countries"
        + (f"  ·  {zen} unique dataset downloads (Zenodo)" if zen else "")
    )
    fig.text(
        0.01,
        0.975,
        "People are using the Surfaceome",
        fontsize=26,
        fontweight="bold",
        va="top",
    )
    fig.text(0.01, 0.925, headline, fontsize=17, color=COLORS["neutral"], va="top")
    fig.text(
        0.01,
        0.01,
        f"Cloudflare Web Analytics (cookie-free, sampled estimates), {since:%b %d} – {today:%b %d, %Y}. "
        "A visit is a page load arriving from outside the site; there is no unique-person count.",
        fontsize=11,
        color=COLORS["neutral"],
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.88))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    save_figure(fig, "viewer_usage_sab", OUT_DIR, formats=("pdf", "png"))
    regions.to_csv(OUT_DIR / "viewer_usage_regions.tsv", sep="\t", index=False)
    plot_regions_compact(regions_long)
    print(headline)


def plot_regions_compact(regions_long: pd.DataFrame) -> None:
    """Panel a alone at 6 x 3.5 in, for dropping into a slide beside text."""
    setup_plotting_style(font_scale=1.0)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    sns.barplot(
        data=regions_long,
        x="region",
        y="n",
        hue="metric",
        hue_order=["Visits", "Page views"],
        palette=[COLORS["primary"], COLORS["secondary"]],
        ax=ax,
    )
    for bars in (c for c in ax.containers if isinstance(c, BarContainer)):
        ax.bar_label(
            bars,
            labels=[f"{b.get_height():,.0f}" for b in bars],
            fontsize=11,
            padding=2,
        )
    ax.set_ylim(0, regions_long["n"].max() * 1.15)
    ax.set_xlabel("")
    ax.set_ylabel("Count, last 90 days", fontsize=12)
    ax.tick_params(labelsize=11)
    ax.legend(title=None, frameon=False, loc="upper right", fontsize=11)
    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()
    save_figure(fig, "viewer_usage_regions", OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
