"""The installed package version. The single source is pyproject.toml."""

from importlib.metadata import version

BLURBY_VERSION = version("blurby")
