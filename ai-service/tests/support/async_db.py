"""Drive a database scenario from a synchronous test. Delivered by C22.

The suite installs no asyncio plugin, so async work runs through `asyncio.run`. Two things
make that insufficient the moment a test touches PostgreSQL through the async engine, and
both produce errors that say nothing about the code under test.

**One loop per scenario.** The engine is process-wide and its pooled connections belong to
the loop that opened them. A test built from several `asyncio.run` calls hands the second
call a connection the first loop owns, and fails on an `InterfaceError`. Disposing on both
sides also stops the engine cached for one ephemeral database being reused against the next.

**The loop has to be a selector loop on Windows.** psycopg refuses the `ProactorEventLoop`
Python installs by default there — the same trap the README records for running the service
with uvicorn on a Windows host. It costs nothing on Linux, where this is already the default.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from jbg_ai.db.engine import dispose_engine

T = TypeVar("T")


def run_db(scenario: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run one coroutine factory against a freshly built engine, disposing it after."""

    async def _main() -> T:
        await dispose_engine()
        try:
            return await scenario()
        finally:
            await dispose_engine()

    if sys.platform == "win32":
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            return runner.run(_main())
    return asyncio.run(_main())
