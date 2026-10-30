# SPDX-License-Identifier: Apache-2.0
"""Authoritative read-only HMI wire models. Generate TS with scripts/generate_schema.py."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(max_length=16384)]
Cursor = Annotated[str, Field(pattern=r'^[^:\s]{1,128}:(0|[1-9][0-9]{0,18})$')]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Fact(Contract):
    name: Text
    value: Text


class Item(Contract):
    id: Text
    kind: Literal['role', 'execution', 'task', 'alarm', 'incident', 'diagnostic']
    label: Text
    station: Text
    facts: Annotated[list[Fact], Field(max_length=256)]
    attention: bool
    acknowledge_id: Text | None


class Snapshot(Contract):
    cursor: Cursor
    generated_at: Annotated[float, Field(ge=0)]
    native_write_enabled: Literal[False]
    source_mode: Literal['synthetic', 'approved-local']
    connection_quality: Text
    items: Annotated[list[Item], Field(max_length=10000)]


class HistoryEntry(Contract):
    id: Text
    item_id: Text
    label: Text
    observed_at: float | None
    facts: Annotated[list[Fact], Field(max_length=256)]


class History(Contract):
    cursor: Cursor
    entries: Annotated[list[HistoryEntry], Field(max_length=100)]
    semantics: Literal['historical evidence; bounded excerpt, not current state or verified progress']
    ordering: Literal['per-identity retained order; cross-source ordering uncertain']


class Session(Contract):
    csrf: Text
    permissions: list[Literal['viewer', 'operator']]
    controller_connected: Literal[False]


class Login(Contract):
    token: Annotated[str, Field(min_length=32, max_length=256)]


class Acknowledgement(Contract):
    occurrence_id: Annotated[str, Field(pattern=r'^[1-9][0-9]{0,18}$')]
    position: Literal['operator']
