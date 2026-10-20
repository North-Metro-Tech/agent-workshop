# SPDX-License-Identifier: Apache-2.0
"""Temporary red-phase skeleton, intentionally no implemented reduction."""
class Reducer:
    def register_role(self, *args, **kwargs):
        pass

    def register_feed(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        raise NotImplementedError('Truth-model reduction not implemented: ' + name)
