"""Unit tests for the version immutability guard (testing-strategy §4.5, U-21/U-22).

Pure, I/O-free tests for ``app.agents.service.assert_mutable``. The HTTP-layer
behaviour (PATCH on a published version returns 409) is covered by the
integration test ``test_update_published_version_returns_409`` (I-3) in
``test_agents_registry.py``.
"""

from __future__ import annotations

import pytest

from app.agents.service import ImmutableVersionError, assert_mutable
from app.models import AgentVersion


def _make_version(*, status: str) -> AgentVersion:
    """Build a detached AgentVersion for unit-testing the pure guard."""
    return AgentVersion(
        id="test-version",
        agent_id="ledger",
        version_number=1 if status == "published" else None,
        semantic_version="1.0.0" if status == "published" else None,
        status=status,
        system_prompt="",
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=1024,
        enabled_tool_ids=[],
        allowed_scopes=[],
    )


def test_assert_mutable_rejects_published_version() -> None:
    """U-21: assert_mutable(published_version) raises ImmutableVersionError."""
    version = _make_version(status="published")
    with pytest.raises(ImmutableVersionError):
        assert_mutable(version)


def test_assert_mutable_allows_draft_version() -> None:
    """U-22: assert_mutable(draft_version) is a no-op (no raise)."""
    version = _make_version(status="draft")
    assert_mutable(version)  # no raise


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
