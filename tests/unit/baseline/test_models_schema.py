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

"""Unit tests: models + schema (de)serialization (tasks 6.1, 6.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from AgentEval.baseline import schema as _schema
from AgentEval.baseline.models import (
    ContinuousEvidence,
    MetricsBaseline,
    ProportionEvidence,
    RunContext,
)
from AgentEval.errors import BaselineSchemaError

_CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "metrics-baseline-schema.json"


def _baseline(*, timestamp: str = "2026-07-09T00:00:00+00:00") -> MetricsBaseline:
    return MetricsBaseline(
        schema_version=1,
        metrics={
            "pass_rate": ProportionEvidence(successes=45, trials=50, value=0.9, k=None),
            "pass_at_1": ProportionEvidence(successes=45, trials=50, value=0.9, k=1),
            "cost_usd": ContinuousEvidence(
                samples=(0.01, 0.02, 0.03), value=0.02, total=0.06, mean=0.02, p50=0.02, p95=0.03
            ),
        },
        extra_metrics={"custom": 1.5},
        run_context=RunContext(
            model="claude-sonnet-4-6",
            adapter_name="GenericAdapter",
            adapter_version="1.0.0",
            library_version="0.0.1",
            timestamp=timestamp,
            git_sha="abc123",
            git_dirty=False,
        ),
    )


def test_serialize_is_deterministic_and_sorted() -> None:
    text = _schema.serialize(_baseline())
    assert text.endswith("\n")
    parsed = json.loads(text)
    # sorted keys: schema_version comes after run_context/metrics/extra_metrics alphabetically.
    assert list(parsed.keys()) == ["extra_metrics", "metrics", "run_context", "schema_version"]
    # Re-serializing the same baseline is byte-identical.
    assert _schema.serialize(_baseline()) == text


def test_deterministic_reserialization_differs_only_by_timestamp() -> None:
    a = _schema.serialize(_baseline(timestamp="2026-07-09T00:00:00+00:00"))
    b = _schema.serialize(_baseline(timestamp="2026-07-09T11:11:11+00:00"))
    # Only the timestamp line differs.
    diff = [(x, y) for x, y in zip(a.splitlines(), b.splitlines(), strict=True) if x != y]
    assert len(diff) == 1
    assert "timestamp" in diff[0][0]


def test_round_trip_load() -> None:
    text = _schema.serialize(_baseline())
    loaded = _schema.load(text)
    assert loaded.schema_version == 1
    assert isinstance(loaded.metrics["pass_rate"], ProportionEvidence)
    assert loaded.metrics["pass_rate"].successes == 45
    assert isinstance(loaded.metrics["cost_usd"], ContinuousEvidence)
    assert loaded.metrics["cost_usd"].samples == (0.01, 0.02, 0.03)
    assert loaded.extra_metrics == {"custom": 1.5}
    assert loaded.run_context.model == "claude-sonnet-4-6"


def test_redaction_at_write_boundary() -> None:
    b = MetricsBaseline(
        schema_version=1,
        metrics={"pass_rate": ProportionEvidence(successes=1, trials=1, value=1.0)},
        extra_metrics={},
        run_context=RunContext(model="sk-ant-SECRETKEY0123456789abcdef", library_version="0.0.1"),
    )
    text = _schema.serialize(b)
    assert "sk-ant-SECRETKEY" not in text
    assert "[REDACTED]" in text


def test_future_schema_version_raises() -> None:
    text = _schema.serialize(_baseline())
    data = json.loads(text)
    data["schema_version"] = 99
    with pytest.raises(BaselineSchemaError) as exc:
        _schema.load(json.dumps(data))
    assert "99" in str(exc.value)
    assert exc.value.field_name == "schema_version"


def test_missing_required_field_raises_naming_field() -> None:
    text = _schema.serialize(_baseline())
    data = json.loads(text)
    del data["metrics"]
    with pytest.raises(BaselineSchemaError) as exc:
        _schema.load(json.dumps(data))
    assert exc.value.field_name == "metrics"


def test_unparseable_json_raises() -> None:
    with pytest.raises(BaselineSchemaError):
        _schema.load("{not valid json")


def test_missing_nested_metric_field_raises_schema_error_not_keyerror() -> None:
    # LOW-1: a proportion metric missing `successes` used to leak KeyError:'successes'
    # out of load(); it must raise the structured BaselineSchemaError naming the field.
    data = {
        "schema_version": 1,
        "metrics": {"pass_rate": {"kind": "proportion", "trials": 10, "value": 0.9}},
        "extra_metrics": {},
        "run_context": {},
    }
    with pytest.raises(BaselineSchemaError) as exc:
        _schema.load(json.dumps(data))
    assert exc.value.field_name == "metrics.pass_rate.successes"


def test_successes_greater_than_trials_raises_at_load_time() -> None:
    # LOW-1: successes > trials used to load OK and only blow up later in Wilson;
    # it must be rejected at load time with the numeric constraint named.
    data = {
        "schema_version": 1,
        "metrics": {"pass_rate": {"kind": "proportion", "successes": 20, "trials": 10, "value": 0.9}},
        "extra_metrics": {},
        "run_context": {},
    }
    with pytest.raises(BaselineSchemaError) as exc:
        _schema.load(json.dumps(data))
    assert exc.value.field_name == "metrics.pass_rate.successes"
    assert "successes <= trials" in str(exc.value)


def test_non_numeric_metric_field_raises_schema_error_not_valueerror() -> None:
    # LOW-1: successes="oops" used to leak ValueError from int(); raise BaselineSchemaError.
    data = {
        "schema_version": 1,
        "metrics": {"pass_rate": {"kind": "proportion", "successes": "oops", "trials": 10, "value": 0.9}},
        "extra_metrics": {},
        "run_context": {},
    }
    with pytest.raises(BaselineSchemaError) as exc:
        _schema.load(json.dumps(data))
    assert exc.value.field_name == "metrics.pass_rate.successes"


def test_proportion_value_out_of_range_raises() -> None:
    data = {
        "schema_version": 1,
        "metrics": {"pass_rate": {"kind": "proportion", "successes": 5, "trials": 10, "value": 1.9}},
        "extra_metrics": {},
        "run_context": {},
    }
    with pytest.raises(BaselineSchemaError) as exc:
        _schema.load(json.dumps(data))
    assert exc.value.field_name == "metrics.pass_rate.value"


def test_continuous_samples_not_a_list_raises() -> None:
    data = {
        "schema_version": 1,
        "metrics": {"cost_usd": {"kind": "continuous", "samples": "nope", "value": 0.1}},
        "extra_metrics": {},
        "run_context": {},
    }
    with pytest.raises(BaselineSchemaError) as exc:
        _schema.load(json.dumps(data))
    assert exc.value.field_name == "metrics.cost_usd.samples"


def test_unknown_metric_kind_raises() -> None:
    data = {
        "schema_version": 1,
        "metrics": {"weird": {"kind": "mystery", "value": 1.0}},
        "extra_metrics": {},
        "run_context": {},
    }
    with pytest.raises(BaselineSchemaError):
        _schema.load(json.dumps(data))


# --- Nullish-input fuzz (task 6.5) ----------------------------------------- #


@pytest.mark.parametrize("nullish", [None, "", False, 0])
def test_nullish_run_context_fields_load(nullish: object) -> None:
    data = {
        "schema_version": 1,
        "metrics": {"pass_rate": {"kind": "proportion", "successes": 1, "trials": 1, "value": 1.0, "k": None}},
        "extra_metrics": {},
        "run_context": {"model": nullish, "git_dirty": nullish},
    }
    loaded = _schema.load(json.dumps(data))
    assert loaded.run_context.model == nullish


def test_missing_run_context_key_defaults_to_none() -> None:
    data = {
        "schema_version": 1,
        "metrics": {"pass_rate": {"kind": "proportion", "successes": 1, "trials": 1, "value": 1.0}},
        "extra_metrics": {},
        "run_context": {},  # every key missing
    }
    loaded = _schema.load(json.dumps(data))
    assert loaded.run_context.model is None
    assert loaded.run_context.git_sha is None


# --- Contract-schema smoke test (task 5.1) --------------------------------- #


def test_emitted_baseline_validates_against_published_schema() -> None:
    import jsonschema

    schema = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    payload = json.loads(_schema.serialize(_baseline()))
    jsonschema.validate(payload, schema)  # raises on mismatch
