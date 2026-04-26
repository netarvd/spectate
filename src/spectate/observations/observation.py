from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

UNRESOLVED = "*"


@dataclass(frozen=True, slots=True, order=True)
class Observation:
    category: str
    parameter: str
    file: Path
    line: int
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_unresolved(self) -> bool:
        return self.parameter == UNRESOLVED
