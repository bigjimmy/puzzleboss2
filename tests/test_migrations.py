#!/usr/bin/env python3
"""Migration discovery, and idempotence of the newuser migrations.

Run with: pytest tests/test_migrations.py -v
"""

from unittest.mock import MagicMock

import pytest

import migrations


def _conn(column_present):
    cursor = MagicMock()
    cursor.fetchone.return_value = ("password",) if column_present else None
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_every_module_is_discoverable_with_a_unique_name():
    found = migrations.get_all_migrations()
    assert found, "no migrations discovered"
    for name, info in found.items():
        assert info["name"] == name
        assert info["description"]
    assert len({v["module"] for v in found.values()}) == len(found)


def test_unknown_migration_is_refused():
    ok, msg = migrations.run_migration("this_does_not_exist", MagicMock())
    assert ok is False
    assert "not found" in msg


@pytest.mark.parametrize("name,ddl", [
    ("drop_newuser_password_column", "DROP COLUMN password"),
    ("add_newuser_provisioned_at", "ADD COLUMN provisioned_at"),
])
def test_newuser_migrations_are_idempotent(name, ddl):
    # Already applied: no DDL, still reports success.
    already = name.startswith("drop") is False  # add_*: column present => done
    conn, cursor = _conn(column_present=already)
    ok, msg = migrations.run_migration(name, conn)
    assert ok is True
    assert "already" in msg.lower() or "nothing" in msg.lower()
    assert ddl not in " ".join(str(c.args[0]) for c in cursor.execute.call_args_list)

    # Not yet applied: DDL runs and is committed.
    conn, cursor = _conn(column_present=not already)
    ok, msg = migrations.run_migration(name, conn)
    assert ok is True
    assert ddl in " ".join(str(c.args[0]) for c in cursor.execute.call_args_list)
    conn.commit.assert_called()
