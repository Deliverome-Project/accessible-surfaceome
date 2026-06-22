from __future__ import annotations

from accessible_surfaceome.tools._shared.ncbi import (
    add_ncbi_api_key_param,
    ncbi_api_keys,
    with_ncbi_api_key_url,
)


def test_ncbi_api_keys_prefers_pool_and_keeps_single_key_fallback(
    monkeypatch,
) -> None:
    monkeypatch.setenv("NCBI_API_KEYS", "key-a, key-b key-a;key-c")
    monkeypatch.setenv("NCBI_API_KEY", "key-d")

    assert ncbi_api_keys() == ("key-a", "key-b", "key-c", "key-d")


def test_add_ncbi_api_key_param_round_robins_pool(monkeypatch) -> None:
    monkeypatch.setenv("NCBI_API_KEYS", "key-a,key-b")
    monkeypatch.delenv("NCBI_API_KEY", raising=False)

    params_1: dict[str, str] = {}
    params_2: dict[str, str] = {}
    params_3: dict[str, str] = {}

    add_ncbi_api_key_param(params_1)
    add_ncbi_api_key_param(params_2)
    add_ncbi_api_key_param(params_3)

    assert params_1["api_key"] == "key-a"
    assert params_2["api_key"] == "key-b"
    assert params_3["api_key"] == "key-a"


def test_with_ncbi_api_key_url_uses_query_separator(monkeypatch) -> None:
    monkeypatch.setenv("NCBI_API_KEYS", "key-a")
    monkeypatch.delenv("NCBI_API_KEY", raising=False)

    assert with_ncbi_api_key_url("https://example.test/path") == (
        "https://example.test/path?api_key=key-a"
    )
    assert with_ncbi_api_key_url("https://example.test/path?db=pubmed") == (
        "https://example.test/path?db=pubmed&api_key=key-a"
    )


def test_no_ncbi_api_key_leaves_params_and_urls_unchanged(monkeypatch) -> None:
    monkeypatch.delenv("NCBI_API_KEYS", raising=False)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)

    params: dict[str, str] = {}
    add_ncbi_api_key_param(params)

    assert params == {}
    assert with_ncbi_api_key_url("https://example.test/path") == (
        "https://example.test/path"
    )
