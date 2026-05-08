"""Provide the jfrog_api_request package."""

import importlib.metadata
import typing

_PKG_METADATA: typing.Final[   # noqa: RUF067
    importlib.metadata.PackageMetadata
] = importlib.metadata.metadata(
    __name__
)

__version__: typing.Final[str | None] = _PKG_METADATA.get("version")
__author__: typing.Final[str | None] = _PKG_METADATA.get("author")
