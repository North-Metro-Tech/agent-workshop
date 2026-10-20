# SPDX-License-Identifier: Apache-2.0
"""Function-level ingress; executable red baseline, replaced after test capture."""
from dataclasses import dataclass

EVENT_TYPE = 'org.agentworkshop.execution.lifecycle.v1'


@dataclass(frozen=True)
class SourceBinding:
    source: str
    runtime: str
    role: str
    feed: str
    schema_url: str = ''
    evidence_class: str = 'runtime_observed'


@dataclass(frozen=True)
class Acquisition:
    acquired_at: float | None
    received_at: float
    epoch: str
    receipt_unix: float | None = None


class Ingest:
    def __init__(self, reducer, binding):
        self.reducer = reducer
        self.binding = binding
        self.records = []
        self.diagnostics = []
        self.reconcile_required = False

    def cloudevents(self, payload, *, context):
        raise NotImplementedError

    def otlp(self, signal, payload, *, context):
        raise NotImplementedError
