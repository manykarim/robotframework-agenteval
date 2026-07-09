# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Conversational metrics unit tests (add-multi-turn-conversation-testing Task 5.2)."""

from __future__ import annotations

import pytest

from AgentEval.conversation.library import ConversationLibrary
from AgentEval.metrics.library import MetricsLibrary


def _three_turn_conv(lib: ConversationLibrary) -> object:
    conv = lib.start_conversation(adapter="native-mock")
    lib.send_message(conv, "one")
    lib.send_message(conv, "two")
    lib.send_message(conv, "three")
    return conv


def test_get_conversation_results_order_and_length(lib: ConversationLibrary) -> None:
    metrics = MetricsLibrary()
    conv = _three_turn_conv(lib)
    results = metrics.get_conversation_results(conv)
    assert len(results) == 3
    assert results[0].response_text == "echo:one"
    assert results[2].response_text.startswith("echo:")


def test_existing_metric_keywords_aggregate_over_conversation(lib: ConversationLibrary) -> None:
    metrics = MetricsLibrary()
    conv = _three_turn_conv(lib)
    results = metrics.get_conversation_results(conv)
    cost = metrics.get_cost_total(results)
    assert cost == pytest.approx(0.03)  # 3 turns * 0.01
    p95 = metrics.get_latency_p95(results)
    assert p95 >= 0.0


def test_get_turn_count_on_handle_and_transcript(lib: ConversationLibrary) -> None:
    metrics = MetricsLibrary()
    conv = _three_turn_conv(lib)
    assert metrics.get_turn_count(conv) == 3
    transcript = lib.get_conversation_transcript(conv)
    assert metrics.get_turn_count(transcript) == 3
    assert len(metrics.get_conversation_results(transcript)) == 3


def test_metrics_reject_non_conversation_input() -> None:
    metrics = MetricsLibrary()
    with pytest.raises(TypeError):
        metrics.get_turn_count("not a conversation")
