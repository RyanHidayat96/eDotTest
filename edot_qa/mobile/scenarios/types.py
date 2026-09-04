from __future__ import annotations

from pathlib import Path
from typing import Protocol

from edot_qa.mobile.maestro import MaestroResult


class MaestroFlow(Protocol):
    def __call__(
        self,
        flow: str | Path,
        *,
        timeout_seconds: int | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> MaestroResult:
        """Run a Maestro flow through the Pytest fixture wrapper."""

