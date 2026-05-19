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

"""Bundled reference MCP servers (Story 3.1).

Tiny FastMCP-style echo server used by Phase-1 integration tests + as
the canonical example for the README quickstart. Runs in-process
(`in_memory` transport) OR as a subprocess (`stdio` transport via
`python -m AgentEval.mcp.bundled.echo`).
"""
