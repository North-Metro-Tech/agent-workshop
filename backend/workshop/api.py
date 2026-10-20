# SPDX-License-Identifier: Apache-2.0
"""Temporary red-phase skeleton."""
class LocalAPI:
    def __init__(self, reducer):
        self.reducer = reducer

    def __getattr__(self, name):
        raise NotImplementedError('Read-only local facade not implemented: ' + name)
