"""Migration-specific fixtures. The ephemeral database itself lives in the root conftest.

It moved there when a second package — the POS projection repository — needed the same
throwaway PostgreSQL. Two decisions behind it are worth keeping stated, because both are
easy to get wrong.

**A fresh database per test, not a shared one.** `test_upgrade_downgrade_is_reversible`
mutates the schema. Sharing a database would make these tests order-dependent, which is
exactly the failure mode `CLAUDE.md` records as poison in the .NET suite — where a handful
of tests already disagree between two runs of identical code.

**Skip, do not fail, when Docker is unreachable.** There is no CI running the Python suite
yet, so permanent red on a laptop would teach everyone to ignore red, which costs more than
these tests are worth. The trade-off is real: a green run does not by itself prove the
migration was exercised. Check that the `db` tests ran, not merely that nothing failed.
"""

from __future__ import annotations

import pytest

from support.paths import BOOTSTRAP_SQL


@pytest.fixture
def database_name(database_url: str) -> str:
    """The bare database name, for callers that talk to psql instead of a driver."""
    return database_url.rsplit("/", 1)[1]


@pytest.fixture
def run_bootstrap(postgres_container, database_name: str):
    """Execute the real `bootstrap.sql` with psql inside the container.

    It cannot be run through SQLAlchemy: the script uses psql meta-commands
    (`\\gset`, `\\if`, `\\echo`) that the server never sees. Piping the file's
    actual contents through a heredoc keeps the test honest — it exercises the
    deliverable rather than a re-implementation of it.
    """

    def _run(password: str = "bootstrap-test-password") -> tuple[int, str]:
        sql = BOOTSTRAP_SQL.read_text(encoding="utf-8")
        script = (
            f"psql -U {postgres_container.username} -d {database_name} "
            f"-v ai_password={password} <<'JBG_BOOTSTRAP_EOF'\n{sql}\nJBG_BOOTSTRAP_EOF"
        )
        exit_code, output = postgres_container.exec(["sh", "-c", script])
        return exit_code, output.decode("utf-8", errors="replace")

    return _run
