"""Tests for user-scoped notification queries."""

from kairos.db.bandit import bandit_user_id


def test_bandit_user_id_default_namespace():
    assert bandit_user_id(None) == "__default__"
    assert bandit_user_id("user-abc") == "user-abc"
