import json
import uuid
import types
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import convert_chatgpt
import convert_claude
import convert_grok

FAKE_TS = 1234567890


def _patch(monkeypatch, module: types.ModuleType):
    # deterministic UUIDs
    counter = {"val": 0}
    def fake_uuid():
        counter["val"] += 1
        return uuid.UUID(int=counter["val"])
    monkeypatch.setattr(uuid, "uuid4", fake_uuid)
    monkeypatch.setattr(module.time, "time", lambda: FAKE_TS)


def _run_conversion(module: types.ModuleType, path: str, monkeypatch):
    _patch(monkeypatch, module)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if module is convert_chatgpt:
        convs = module.parse_chatgpt(data)
    elif module is convert_claude:
        convs = module.parse_claude(data)
    else:
        convs = module.parse_grok(data)
    out, _ = module.build_webui(convs[0], "user")
    return out


def _load_expected(name: str):
    with open(f"tests/expected/{name}_output.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_chatgpt_conversion(monkeypatch):
    result = _run_conversion(convert_chatgpt, "examples/gpt_example.json", monkeypatch)
    expected = _load_expected("chatgpt")
    assert result == expected


def test_claude_conversion(monkeypatch):
    result = _run_conversion(convert_claude, "examples/claude_example.json", monkeypatch)
    expected = _load_expected("claude")
    assert result == expected


def test_claude_thinking_conversion(monkeypatch):
    result = _run_conversion(convert_claude, "examples/claude_thinking_example.json", monkeypatch)
    expected = _load_expected("claude_thinking")
    assert result == expected


def test_claude_tooluse_conversion(monkeypatch):
    # Regression test for tool_use/tool_result content, which used to have no
    # handler at all. A turn whose only content was a tool call and its
    # result (no separate text block) vanished from the import entirely,
    # since _parse_message_list drops any message whose extracted text comes
    # back empty. See examples/claude_tooluse_example.json's fourth message.
    result = _run_conversion(convert_claude, "examples/claude_tooluse_example.json", monkeypatch)
    expected = _load_expected("claude_tooluse")
    assert result == expected
    assert len(result["messages"]) == 5, "the tool-only turn must not be dropped"


def test_grok_conversion(monkeypatch):
    result = _run_conversion(convert_grok, "examples/grok_example.json", monkeypatch)
    expected = _load_expected("grok")
    assert result == expected


def test_invalid_unicode(monkeypatch):
    result = _run_conversion(convert_chatgpt, "examples/invalid_unicode.json", monkeypatch)
    expected = _load_expected("invalid_unicode")
    assert result == expected


def test_reasoning_block_mixed_timestamp_types():
    # _parse_iso_datetime had two branches: an ISO string is always UTC
    # (Claude's exports use "Z"), but a bare number went through
    # datetime.fromtimestamp() with no tz, which uses the *local* system
    # timezone. Comparing one aware and one naive datetime raises TypeError
    # regardless of what the values are, so any thinking block mixing the two
    # timestamp shapes crashed conversion outright.
    part = {
        "type": "thinking",
        "thinking": "Let me think about this.",
        "start_timestamp": "2026-01-01T00:00:00Z",
        "stop_timestamp": 1767225605,
    }
    block = convert_claude._format_reasoning_block(part)
    assert 'duration="5"' in block

