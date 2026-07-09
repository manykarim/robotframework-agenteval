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

"""Red-team probe schema dataclasses (add-red-team-probes / design D1 + D2).

A ``Probe`` is a single-turn adversarial payload plus attribution metadata; a
``ProbePack`` is a versioned collection loaded from YAML. A ``ProbeResult`` is
the structured record `Run Probe` returns (design D2 — verdict PLUS evidence,
not a bare bool), and ``AttackSuccessRate`` carries the ASR + Wilson CI.

**ASR polarity (design D4 — READ THIS):** attack success = the agent COMPLIED
(did NOT refuse). ``AttackSuccessRate.asr`` is the compliance fraction; **lower
is safer** (a fully-refusing agent scores ``0.0``). A "pass" in the security
sense is a *refusal*; the metric is deliberately named Attack **Success** Rate
so the number is unambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass

from AgentEval.types import AgentRunResult

__all__ = [
    "PROBE_CATEGORIES",
    "Probe",
    "ProbePack",
    "ProbeResult",
    "AttackSuccessRate",
]

# The four garak-style DEFENSIVE-robustness categories (spec: closed set; NO
# DoS / resource-exhaustion probes — those are out of mission).
PROBE_CATEGORIES: frozenset[str] = frozenset(
    {
        "prompt_injection",
        "jailbreak",
        "pii_leakage",
        "encoding_obfuscation",
    }
)


@dataclass(frozen=True)
class Probe:
    """One single-turn adversarial probe with attribution metadata.

    Fields (all REQUIRED per the spec's five-metadata-field contract, plus the
    ``prompt`` attack payload):
        - ``id``: unique-within-pack identifier (e.g., ``"pi-001"``).
        - ``category``: one of ``PROBE_CATEGORIES``.
        - ``severity``: informational severity label (``"low"`` / ``"medium"``
          / ``"high"`` / ``"critical"``); free-form, not enforced beyond
          non-empty.
        - ``source``: attribution to the probe's public origin (garak /
          DeepTeam / OWASP LLM Top 10), so derived probes are credited.
        - ``expected_behavior``: description of the safe/resistant response —
          what a well-defended agent SHOULD do.
        - ``prompt``: the single-turn attack payload sent to the target agent.
        - ``compliance_marker``: OPTIONAL regex/literal that positively signals
          the agent CARRIED OUT the attack (an attack-success canary — e.g. the
          probe's ``PWNED`` / ``JAILBROKEN`` token, or a supplied fake secret the
          agent was asked to reveal). When set, its presence in the response is
          DEFINITIVE compliance (unsafe) — it overrides any refusal language, so
          a mixed "I can't help… but here is PWNED" response is correctly scored
          as compliance, NOT a refusal. Empty string = no positive marker (the
          probe relies on refusal-language / judge detection alone). Matched
          case-insensitively as a regex, falling back to a literal substring
          search if the pattern is not a valid regex.
    """

    id: str
    category: str
    severity: str
    source: str
    expected_behavior: str
    prompt: str
    compliance_marker: str = ""


@dataclass(frozen=True)
class ProbePack:
    """A versioned collection of probes (bundled and/or user-supplied).

    ``pack_version`` makes runs reproducible + pack drift detectable. Merged
    packs (bundled + user extension) keep the bundled ``pack_version``; each
    probe's ``source`` records its own provenance.
    """

    probes: tuple[Probe, ...]
    pack_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "probes", tuple(self.probes))

    def __len__(self) -> int:
        return len(self.probes)

    @property
    def categories(self) -> tuple[str, ...]:
        """Sorted tuple of the categories actually present in this pack."""
        return tuple(sorted({p.category for p in self.probes}))

    def by_id(self, probe_id: str) -> Probe | None:
        """Return the probe with the given id, or ``None`` if absent."""
        for probe in self.probes:
            if probe.id == probe_id:
                return probe
        return None

    def by_category(self, category: str) -> tuple[Probe, ...]:
        """Return all probes in ``category`` (empty tuple if none)."""
        return tuple(p for p in self.probes if p.category == category)


@dataclass(frozen=True)
class ProbeResult:
    """Structured result of running one probe against one adapter (design D2).

    Carries the verdict AND the evidence, so ASR computation, heatmap
    projection, and triage all read off one object.

    Fields:
        - ``probe_id`` / ``category`` / ``severity`` / ``source`` /
          ``expected_behavior``: copied from the ``Probe`` for self-contained
          reporting.
        - ``prompt``: the attack payload that was sent.
        - ``adapter``: the adapter name the probe ran against (heatmap column).
        - ``response_text``: the agent's raw response (the evidence).
        - ``refused``: the refusal verdict. ``True`` = the agent RESISTED the
          attack (the SAFE outcome). ``False`` = the agent complied (an attack
          success that counts toward ASR).
        - ``refusal_strategy``: which strategy produced ``refused``
          (``"pattern"`` / ``"judge"`` / ``"both"``).
        - ``compliance_marker``: the probe's attack-success marker (copied from
          the ``Probe``) so `RedTeam.Should Refuse` can re-derive the verdict
          with the same compliance-marker precedence. Empty when the probe
          declares no positive marker.
        - ``result``: the underlying ``AgentRunResult`` (cost / latency /
          trace / tool calls).
    """

    probe_id: str
    category: str
    severity: str
    source: str
    expected_behavior: str
    prompt: str
    adapter: str
    response_text: str
    refused: bool
    refusal_strategy: str
    result: AgentRunResult
    compliance_marker: str = ""

    @property
    def complied(self) -> bool:
        """``True`` when the agent did NOT refuse — an attack success (unsafe)."""
        return not self.refused


@dataclass(frozen=True)
class AttackSuccessRate:
    """Attack-success-rate over a collection of probe results (design D4).

    **Polarity: ``asr`` is the COMPLIANCE fraction; lower is safer.** A
    fully-refusing agent scores ``asr == 0.0``; a fully-complying agent scores
    ``asr == 1.0``. The Wilson confidence interval is computed by the existing
    ``stats/wilson.py`` primitive — no second CI implementation.

    Fields:
        - ``asr``: ``compliance_count / n`` in ``[0.0, 1.0]``.
        - ``ci_lower`` / ``ci_upper``: Wilson score interval bounds for the
          latent compliance probability at ``confidence``.
        - ``confidence``: the CI confidence level (default ``0.95``).
        - ``n``: total probe results scored.
        - ``compliance_count``: results where the agent complied (attack
          succeeded).
        - ``refusal_count``: results where the agent refused (resisted).
    """

    asr: float
    ci_lower: float
    ci_upper: float
    confidence: float
    n: int
    compliance_count: int
    refusal_count: int
