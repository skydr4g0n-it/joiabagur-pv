"""Running Alembic in-process must not disable the service's loggers. C18b.

Alembic's `env.py` configures logging from `alembic.ini` with `fileConfig`, whose
default is `disable_existing_loggers=True`. Under the CLI that is harmless — the
process exits straight afterwards. In-process it is not: these migration tests run
Alembic inside the same interpreter as the rest of the suite, so the default left
every `jbg_ai` logger disabled for whatever ran later.

It cost four days of a red suite after C14 and it never looked like what it was.
The two casualties asserted on log output, so they failed with an empty capture
rather than an error; and because they **passed when their own file ran alone**,
the obvious check said the code was fine and the obvious conclusion was
"order-dependent flakiness, like the .NET suite". It was a defect.

No database and no container: this reads the module the way the CLI does.
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from support.paths import ALEMBIC_INI, MIGRATIONS_DIR

CANARY = "jbg_ai.retrieval.orchestrator"


def test_alembic_ini_does_not_disable_the_service_loggers() -> None:
    """Apply the ini exactly as `env.py` does and check a service logger survives."""
    logging.getLogger(CANARY).disabled = False

    fileConfig(str(ALEMBIC_INI), disable_existing_loggers=False)

    assert not logging.getLogger(CANARY).disabled


def test_the_default_would_have_disabled_them() -> None:
    """Pin the reason the argument is there, not merely the call.

    Without this, someone tidying `env.py` drops the keyword as noise and the suite
    goes quietly red again four days later. Restores the logger afterwards, since
    disabling it is the whole point of the assertion.
    """
    canary = logging.getLogger(CANARY)
    canary.disabled = False

    try:
        fileConfig(str(ALEMBIC_INI))
        assert canary.disabled, "the default is no longer destructive; env.py can simplify"
    finally:
        canary.disabled = False
        fileConfig(str(ALEMBIC_INI), disable_existing_loggers=False)


def test_env_module_passes_the_argument() -> None:
    """The behaviour above only protects the suite if `env.py` actually opts out."""
    source = (MIGRATIONS_DIR / "env.py").read_text(encoding="utf-8")

    assert "disable_existing_loggers=False" in source
