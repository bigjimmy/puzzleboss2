"""
Migration framework for puzzleboss.

Each migration is a Python module in this package with:
    name        - Short identifier (used in URL: /migrate/<name>)
    description - Human-readable explanation of what it does
    run(conn)   - Execute the migration using the given DB connection

Migrations are one-shot: they can be re-run safely (idempotent) but are
intended to be pruned from the codebase once no longer needed.
"""

import importlib
import pkgutil


def get_all_migrations():
    """Discover and return all migration modules in this package."""
    migrations = {}
    for importer, modname, ispkg in pkgutil.iter_modules(__path__):
        if modname.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{modname}")
        if hasattr(mod, "name") and hasattr(mod, "run"):
            migrations[mod.name] = {
                "module": modname,
                "name": mod.name,
                "description": getattr(mod, "description", ""),
            }
    return migrations


def run_migration(name, conn):
    """Run a named migration. Returns (success, message)."""
    migrations = get_all_migrations()
    if name not in migrations:
        return False, f"Migration '{name}' not found"

    modname = migrations[name]["module"]
    mod = importlib.import_module(f"{__package__}.{modname}")
    return mod.run(conn)
