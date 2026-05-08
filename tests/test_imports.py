"""Test import of all the modules."""

import importlib
import pathlib
import typing

import pytest

import jfrog_api_request as pkg

PKGLOC: typing.Final[pathlib.Path] = pathlib.Path(pkg.__file__).parent


def _gen_modules() -> typing.Iterator[str]:
    for f in PKGLOC.glob("**/*.py"):
        m: typing.Any
        m = f.relative_to(
            PKGLOC.parent,
        ).with_suffix("")
        m = m.parts
        if m[-1] == "__init__":
            m = m[:-1]
        m = ".".join(m)
        yield m


@pytest.mark.parametrize("module", list(_gen_modules()))
def test_module(module: str) -> None:
    """Test import of a module.

    The module is described by his classpath (a.b.c....)
    """
    importlib.import_module(module)
    assert True
