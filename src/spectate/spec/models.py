from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_PATH = Path(__file__).with_name("spec.schema.json")


def load_schema() -> dict:
    with SCHEMA_PATH.open() as fh:
        return json.load(fh)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UnresolvedHandling(str, Enum):
    SURFACE = "surface"
    FLAG = "flag"
    DROP = "drop"


class ScopedRequired(_Strict):
    handler: str = Field(min_length=1)
    value: str = Field(min_length=1)


RequiredEntry = Annotated[Union[str, ScopedRequired], Field(union_mode="left_to_right")]


class EffectSlots(_Strict):
    required: list[RequiredEntry] = Field(default_factory=list)
    allowed: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)


class NetworkSection(_Strict):
    outbound: EffectSlots | None = None


class FsSection(_Strict):
    read: EffectSlots | None = None
    write: EffectSlots | None = None


class EnvSection(_Strict):
    read: EffectSlots | None = None


class DbSection(_Strict):
    read: EffectSlots | None = None
    write: EffectSlots | None = None


class Spec(_Strict):
    version: Literal[1]
    unresolved_handling: UnresolvedHandling = UnresolvedHandling.SURFACE
    stdlib_auto_allow: bool = True
    network: NetworkSection | None = None
    fs: FsSection | None = None
    subprocess: EffectSlots | None = None
    imports: EffectSlots | None = None
    env: EnvSection | None = None
    db: DbSection | None = None
