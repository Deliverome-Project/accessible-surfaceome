"""Publishing must evict the same deployment-scoped keys the Worker reads."""

from accessible_surfaceome.cloud import internalization, surface_annotation


def test_internalization_purge_uses_live_epoch(monkeypatch):
    for name in (
        "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ZONE_ID", "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_KV_RECORD_CACHE_ID",
    ):
        monkeypatch.setenv(name, "test-value")
    monkeypatch.setattr(surface_annotation, "_EPOCH_CACHE", "restored-deployment")
    monkeypatch.setattr(internalization, "_ROUTE_PREFIX", "/surfaceome")
    purged = []
    deleted = []
    monkeypatch.setattr(surface_annotation, "_purge_cf_cache", lambda urls, **kw: purged.extend(urls))
    monkeypatch.setattr(surface_annotation, "_delete_kv_key", lambda key, **kw: deleted.append(key))
    internalization._purge_internalization_cache("TMEM123")
    record_key = "https://surfaceome-api.cache/restored-deployment/surfaceome/v1/internalization/TMEM123"
    assert purged == [record_key, "https://catalog.cache/restored-deployment/v1/catalog"]
    assert deleted == [record_key]
