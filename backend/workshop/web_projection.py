# SPDX-License-Identifier: Apache-2.0
"""Presentation mapping of canonical, redacted domain facts; never native controls."""
from dataclasses import asdict
import json
from .web_contracts import Fact, History, HistoryEntry, Item, Snapshot


def identity(kind, *parts):
    return kind+':'+json.dumps(parts, ensure_ascii=False, separators=(',', ':'))


def text(value):
    if value is None:
        return 'unknown'
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=asdict)


def facts(values, prefix=''):
    result = []
    for name, value in values.items():
        label = prefix+name
        if isinstance(value, dict):
            result.extend(facts(value, label+'.'))
        else:
            rendered = text(value)
            if len(rendered) > 16384:
                rendered = rendered[:16280] + ' [bounded display excerpt; remaining value omitted]'
            result.append(Fact(name=label, value=rendered))
    return result


def item(kind, key, label, station, values, attention=False, acknowledge_id=None):
    return Item(id=key, kind=kind, label=label, station=station, facts=facts(values),
                attention=attention, acknowledge_id=acknowledge_id)


def project(checkpoint, *, now, source_mode):
    domain = checkpoint['projection']
    items = []
    for role in domain['roles']:
        name = role['role']
        items.append(item('role', identity('role', name), name+' · '+role['availability'],
                          'roles', role))
    tasks = {}
    for execution in domain['executions']:
        key = execution['key']
        role = execution['role']
        # Retained objects do not establish current membership or fresh runtime activity.
        items.append(item('execution', identity('execution', key['runtime'], key['native_id']),
                          key['native_id'], role+' / observed work',
                          {**{k:v for k,v in execution.items() if k != 'observations'},
                           'retained_observation_count': len(execution['observations']),
                           'history': 'bounded retained observations available separately; not current state'},
                          bool(execution['discrepancies'])))
        task = execution['task']
        if task:
            task_id = identity('task', task['source_instance'], task['namespace'], task['native_id'])
            tasks[task_id] = item('task', task_id, task['native_id'], 'linked work',
                {**task, 'disposition': 'unknown; linked identity only, not accepted outcome',
                 'provenance': execution['lifecycle'], 'coverage': 'partial'})
    items.extend(tasks.values())
    for alarm in domain['alarms']:
        items.append(item('alarm', identity('alarm', alarm['id']), alarm['rule']['name'],
                          'attention', {'alarm_state': alarm['state'], **alarm},
                          alarm['state'] != 'normal', alarm['id'] if not alarm['acknowledged'] else None))
    for incident in domain['incidents']:
        items.append(item('incident', identity('incident', incident['group'], incident['incident']),
                          incident['group'], 'attention', incident, True))
    for n, ambiguity in enumerate(domain['ambiguities']):
        items.append(item('diagnostic', identity('ambiguity', n), 'Identity ambiguity',
                          'diagnostics', ambiguity, True))
    return Snapshot(cursor=checkpoint['cursor'], generated_at=float(now),
                    native_write_enabled=False, source_mode=source_mode,
                    connection_quality='fresh', items=items)


def history_excerpt(excerpt):
    entries = []
    for row in excerpt['records']:
        if row['kind'] == 'execution-observation':
            key = row['key']
            item_id = identity('execution', key.runtime, key.native_id)
            observation = row['observation']
            entries.append(HistoryEntry(id=identity('history', item_id, row['index']),
                item_id=item_id, label='Retained execution observation',
                observed_at=observation.observed_at,
                facts=facts({'runtime': key.runtime, 'native_id': key.native_id,
                    **asdict(observation), 'acquisition_at': 'not retained per observation',
                    'quality': 'historical; not a current freshness assertion'})))
        else:
            audit = row['audit']
            entries.append(HistoryEntry(id=identity('alarm-audit', row['index']),
                item_id=identity('alarm', audit['id']) if 'id' in audit else identity('alarm-rule', audit['name']),
                label='Workshop-local alarm audit', observed_at=audit['at'],
                facts=facts({**audit, 'source': 'Workshop-owned alarm audit',
                             'evidence_class': 'operator' if audit['action']=='acknowledged' else 'local_condition',
                             'quality': 'historical; not current alarm state'})))
    return History(cursor=excerpt['cursor'], entries=entries,
                   semantics='historical evidence; bounded excerpt, not current state or verified progress',
                   ordering='per-identity retained order; cross-source ordering uncertain')
