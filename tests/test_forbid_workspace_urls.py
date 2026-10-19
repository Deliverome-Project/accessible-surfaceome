"""The public-repo guard against console URLs that embed a workspace or account id."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[1] / "scripts/precommit/forbid_workspace_urls.py"
)
spec = importlib.util.spec_from_file_location("_hook", HOOK)
# spec and spec.loader are Optional; narrow them so the type checker can see that a
# missing hook fails here with a clear message rather than an AttributeError later.
assert spec is not None and spec.loader is not None, f"cannot load {HOOK}"
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _check(tmp_path, text):
    f = tmp_path / "t.md"
    f.write_text(text)
    return hook.main([str(f)])


BLOCKED = [
    "see https://modal.com/apps/becca-19646/main/ap-XYZ",
    "https://modal.com/workspaces/some-org",
    "123456789012.dkr.ecr.us-east-1.amazonaws.com/img",
    "https://dash.cloudflare.com/0123456789abcdef0123456789abcdef",
]
ALLOWED = [
    # A bare run identifier is the recommended way to cite a run: it grants nothing
    # without a workspace token, and it makes a published dataset traceable.
    "Modal app `ap-MOjrLR1lTBpD4jYr0hH7Ng` completed in 33 min",
    "https://modal.com/apps/<workspace>/main/ap-XYZ",
    "dash.cloudflare.com/<your-cloudflare-account-id>",
    "no urls here at all",
]


@pytest.mark.parametrize("text", BLOCKED)
def test_workspace_scoped_urls_are_blocked(tmp_path, text):
    assert _check(tmp_path, text) == 1


@pytest.mark.parametrize("text", ALLOWED)
def test_bare_identifiers_and_placeholders_are_allowed(tmp_path, text):
    assert _check(tmp_path, text) == 0


def test_the_real_leak_from_2026_09_28_would_be_caught(tmp_path):
    """The exact string that reached a public PR comment."""
    leak = (
        "Run [`ap-MOjrLR1l`](https://modal.com/apps/becca-19646/main/"
        "ap-MOjrLR1lTBpD4jYr0hH7Ng), 1/1 shards ok, 62s wall."
    )
    assert _check(tmp_path, leak) == 1


def test_the_rewritten_form_passes(tmp_path):
    fixed = "Run Modal app `ap-MOjrLR1l`, 1/1 shards ok, 62s wall."
    assert _check(tmp_path, fixed) == 0


def test_a_missing_file_does_not_crash_the_hook(tmp_path):
    assert hook.main([str(tmp_path / "nope.md")]) == 0
