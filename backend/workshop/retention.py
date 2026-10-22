# SPDX-License-Identifier: Apache-2.0
"""Count-only retirement; never read clocks or discard protected evidence."""
from copy import deepcopy
from dataclasses import replace
import json

OBSERVATION_LIMIT = 64
RECORD_LIMIT = 256
SEEN_LIMIT = 512
TERMINAL = {'succeeded', 'failed', 'cancelled'}


class RetentionCapacityError(ValueError):
    """No safe retirement exists. Reject the transaction, never erase evidence."""


def lifecycle_signature(observation):
    # Occurrence time is not a lifecycle transition; retain it unchanged on
    # whichever repeat survives. Native/mapping/authority changes ARE material.
    return replace(observation, observed_at=None)


def append_observation(execution, observation, *, discrepancy=False):
    """Keep first, transitions, all distinct terminal and discrepancy facts.

    An exact repeated terminal fact is already represented (including its
    original occurrence time); it is not a new lifecycle fact. Acquisition
    freshness is handled separately by the reducer, never by this function.
    """
    old = execution.observations
    if (not discrepancy and observation.mapped in TERMINAL
            and observation in old):
        return False
    ids = execution.observation_ids or list(range(len(old)))
    next_id = max(execution.next_observation_id, max(ids, default=-1) + 1)
    observations = old + [deepcopy(observation)]
    numbers = ids + [next_id]
    protected = set(execution.protected_observation_ids)
    # Legacy records have no protection index. Conservatively derive it from
    # retained order and discrepancy values rather than inventing provenance.
    for n, item in enumerate(observations):
        if (n == 0 or item.mapped in TERMINAL
                or (n and lifecycle_signature(item) != lifecycle_signature(observations[n-1]))
                or any(d.get('observation') == item for d in execution.discrepancies)):
            protected.add(numbers[n])
    if discrepancy:
        protected.add(next_id)
    while len(observations) > OBSERVATION_LIMIT:
        eligible = next((n for n, seq in enumerate(numbers)
                         if seq not in protected), None)
        if eligible is None:
            raise RetentionCapacityError('Observation capacity contains only protected facts; owner disposition required')
        del observations[eligible]
        del numbers[eligible]
    execution.observations = observations
    execution.observation_ids = numbers
    execution.protected_observation_ids = protected
    execution.next_observation_id = next_id + 1
    return next_id in protected


def retire_records(records):
    while len(records) > RECORD_LIMIT:
        index = next((n for n, record in enumerate(records)
                      if not record.get('retention_protected', False)), None)
        if index is None:
            raise RetentionCapacityError('Metadata capacity contains only protected facts; owner disposition required')
        del records[index]


def retire_seen(seen):
    # Insertion order, NOT LRU: retries do not refresh lifetime. Eviction means
    # precisely the existing first-sighting validation/order path, no tombstone
    # or weakened digest comparison. The complete map is durably serialized.
    while len(seen) > SEEN_LIMIT:
        del seen[next(iter(seen))]


def metadata_key(record):
    if record.get('execution_key') is not None:
        return ('execution', record['execution_key'])
    return ('corroboration', record['protocol'], record.get('trace_id'), record.get('span_id'),
            json.dumps(record.get('resource'), sort_keys=True),
            json.dumps(record.get('scope'), sort_keys=True))


def material_metadata(record):
    # Transport/dedup identity and observation clocks change on every poll, but
    # are not process/task/trace correlations. Surviving records retain these
    # original values unchanged. Never erase an intervening material change.
    transient = {'digest', 'native_id', 'received_at', 'acquired_at', 'occurrence_at',
                 'source_observed_at', 'retention_protected'}
    value = {k: v for k, v in record.items() if k not in transient}
    if value.get('domain') is not None:
        value['domain'] = {k: v for k, v in value['domain'].items() if k != 'revision'}
    if 'attributes' in value:
        value['attributes'] = {k: v for k, v in value['attributes'].items() if k not in {
            'workshop.record.id', 'workshop.cursor', 'workshop.revision',
            'workshop.hermes.board.event_id'}}
    return value
