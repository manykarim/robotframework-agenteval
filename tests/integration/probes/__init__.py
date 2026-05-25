# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Reusable empirical-verification probes (Story 8b.2 / Epic 8 retro NEW norm).

Per `feedback_listener_hook_api_surface_empirical_check`: probes here are
one-off subprocess invocations used to verify RF Listener v3 (or similar)
API-surface behaviors empirically before committing implementation changes
that depend on those surfaces.

NOT registered as pytest tests; invoke directly per each probe's docstring.
"""
