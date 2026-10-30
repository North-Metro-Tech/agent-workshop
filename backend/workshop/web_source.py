# SPDX-License-Identifier: Apache-2.0
"""Existing Phase 2 approved-board adapter bound to the service's SERIAL writer.

Only constructed by explicit --approved-local serve. No scope discovery, new
boards, native mutation, terminal, transcripts, hooks or scheduler surfaces.
"""
from pathlib import Path
from workshop_collectors.hermes_runtime import HermesRuntime, initial_state, runtime_binding
from workshop_collectors.hermes_work import HermesWork, approved_scope, linux_process_probe
from workshop_collectors.outbox import Outbox


class ApprovedSource:
    def __init__(self, directory):
        self.scope = approved_scope()
        binding = runtime_binding(self.scope)
        self.observer = HermesRuntime(HermesWork(self.scope, process_probe=linux_process_probe), binding)
        self.initial = initial_state(binding, self.scope)
        self.outbox = Outbox((directory / 'service-outbox.db').absolute(), binding=binding,
            clock_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())

    def acquire(self, storage, *, now):
        # Drain at most the existing outbox's configured bound, never spin in a
        # transaction. Collector acquisition and delivery are serial loop calls.
        for _ in range(64):
            if self.outbox.deliver_one(storage, received_at=now) is None:
                break
        observation = self.observer.observe(board=self.scope.board, acquired_at=now)
        self.outbox.enqueue(observation)
        self.outbox.deliver_one(storage, received_at=now)

    def close(self):
        self.outbox.close()
