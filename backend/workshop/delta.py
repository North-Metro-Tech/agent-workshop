# SPDX-License-Identifier: Apache-2.0
"""Data-only changes over the existing closed historian codec's values."""
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from difflib import SequenceMatcher


def difference(before, after, *, pack):
    if type(before) is not type(after):
        return ('replace', after)
    if pack(before) == pack(after):
        return ('same',)
    if is_dataclass(after):
        return ('fields', {f.name: difference(getattr(before, f.name), getattr(after, f.name), pack=pack)
                           for f in fields(after) if pack(getattr(before, f.name)) != pack(getattr(after, f.name))})
    if type(after) is dict:
        removed = [key for key in before if key not in after]
        changed = {key: difference(before[key], value, pack=pack) if key in before else ('replace', value)
                   for key, value in after.items() if key not in before or pack(before[key]) != pack(value)}
        predicted = [key for key in before if key in after] + [key for key in after if key not in before]
        return ('dict', removed, changed, list(after) if predicted != list(after) else None)
    if type(after) is list:
        # Preserve the unchanged middle of a retired-oldest/appended-newest
        # stream. Matching serialized values is deterministic and hashable.
        matches = SequenceMatcher(None, [pack(v) for v in before],
                                  [pack(v) for v in after], autojunk=False)
        return ('list', [(a, b, after[c:d]) for kind, a, b, c, d in matches.get_opcodes()
                         if kind != 'equal'])
    return ('replace', after)


def apply_difference(before, patch):
    kind = patch[0]
    if kind == 'same':
        return before
    if kind == 'replace':
        return deepcopy(patch[1])
    if kind == 'fields':
        return replace(before, **{key: apply_difference(getattr(before, key), value)
                                  for key, value in patch[1].items()})
    if kind == 'dict':
        result = dict(before)
        for key in patch[1]:
            del result[key]
        for key, value in patch[2].items():
            result[key] = apply_difference(result.get(key), value)
        return {key: result[key] for key in patch[3]} if patch[3] is not None else result
    if kind == 'list':
        result = list(before)
        for start, end, values in reversed(patch[1]):
            result[start:end] = deepcopy(values)
        return result
    raise ValueError('Unsupported historian delta operation')
