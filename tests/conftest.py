"""Pytest configuration helpers for the test suite."""

from __future__ import annotations

import asyncio
import inspect

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Item) -> bool | None:
    """Provide asyncio support when pytest-asyncio isn't installed.

    The CI environment may run pytest without loading the ``pytest-asyncio``
    plugin. When that happens, async test functions would normally fail with a
    ``RuntimeError`` complaining that async def tests are unsupported. This
    hook detects that scenario and executes coroutine tests using
    :func:`asyncio.run` so the suite continues to work with or without the
    external plugin.
    """

    if pyfuncitem.config.pluginmanager.hasplugin("pytest_asyncio"):
        return None

    test_function = getattr(pyfuncitem, "obj", None)
    if not inspect.iscoroutinefunction(test_function):
        return None

    asyncio.run(test_function(**pyfuncitem.funcargs))
    return True
