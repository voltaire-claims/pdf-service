# Copyright (C) 2026 Voltaire Claims
# SPDX-License-Identifier: AGPL-3.0-only

"""Gunicorn settings for the shell-free hardened runtime."""

import os

bind = "0.0.0.0:80"
workers = int(os.environ.get("GUNICORN_WORKERS") or "4")
timeout = int(os.environ.get("GUNICORN_TIMEOUT") or "120")
