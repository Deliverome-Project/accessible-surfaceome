"""Internalization pool stage — now a thin re-export of the SHARED clip pool
(``agents/_support/literature_clips``). The pool build + source-store are
agent-agnostic (shared primitives only), so both the internalization and
tag-site literature agents use one implementation. Kept as a module so existing
``from ...internalization.literature_pool import build_pool`` imports are stable.
"""

from __future__ import annotations

from accessible_surfaceome.agents._support.literature_clips import (
    _add_to_pool,
    _body_text,
    build_pool,
    build_source_store,
)

__all__ = ["build_pool", "build_source_store", "_add_to_pool", "_body_text"]
