# SPDX-License-Identifier: Apache-2.0
"""A08 executable red baseline; replaced by the historian implementation."""
from dataclasses import dataclass, field
from .reducer import Reducer


@dataclass
class State:
    reducer: Reducer
    ingests: dict = field(default_factory=dict)
    source_cursors: dict = field(default_factory=dict)
    generations: dict = field(default_factory=dict)


class RecoveryRequired(ValueError):
    pass


class Storage:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError('A08 durable historian')
