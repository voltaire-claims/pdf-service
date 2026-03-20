# Copyright (C) 2026 Voltaire Claims
# SPDX-License-Identifier: AGPL-3.0-only

"""Voltaire PDF service core package."""

from importlib.metadata import PackageNotFoundError, packages_distributions
from importlib.metadata import version as _pkg_version

try:
    _dist_name = packages_distributions()[__name__.split(".")[0]][0]
    __version__ = _pkg_version(_dist_name)
except PackageNotFoundError, KeyError, IndexError:
    __version__ = "unknown"
