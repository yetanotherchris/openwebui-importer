#!/usr/bin/env python3
"""Convert Claude exports to open-webui JSON."""

import argparse
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

INVALID_RE = re.compile(r"[\ue000-\uf8ff]")


def sanitize_text(text: Any) -> str:
    """Return ``text`` without private-use Unicode characters."""
    if not isinstance(text, str):
        return ""
    return INVALID_RE.sub("", text)

MODEL = "claude_4_5_with_thinking.claude-sonnet-4-5-20250929-think"
MODEL_NAME = "anthropic/claude-4.5-sonnet-with-thinking"
SUBDIR = "claude"


def extract_last_sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    matches = re.findall(r"[^.!?]*[.!?]", cleaned, flags=re.DOTALL)
    if matches:
        return matches[-1].strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return lines[-1] if lines else cleaned


def parse_timestamp(value: Any, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return default


def _parse_iso_datetime(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        # Claude's own start_timestamp/stop_timestamp are always ISO strings
        # with a Z, i.e. UTC. This branch exists for other callers of the
        # same helper, but datetime.fromtimestamp() without a tz interprets
        # the value in the *local* system timezone, not UTC. Mixed with the
        # string branch above (always UTC), that produced two bugs at once:
        # a wrong duration on any machine not set to UTC, and a hard crash
        # when the two were compared, since Python refuses to compare an
        # aware datetime against a naive one. Pinning this to UTC matches the
        # string branch and makes the two comparable.
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    return None


def _format_reasoning_block(part: dict) -> str:
    thinking_text = sanitize_text(part.get("thinking"))
    if not thinking_text:
        return ""
    summary_text = ""
    summaries = part.get("summaries")
    if isinstance(summaries, list):
        for entry in summaries:
            if isinstance(entry, dict):
                candidate = sanitize_text(entry.get("summary"))
            else:
                candidate = sanitize_text(entry)
            if candidate:
                summary_text = candidate
                break
    if not summary_text:
        summary_text = "Thought process"

    start_dt = _parse_iso_datetime(part.get("start_timestamp"))
    stop_dt = _parse_iso_datetime(part.get("stop_timestamp"))
    duration_attr = ""
    if start_dt and stop_dt and stop_dt >= start_dt:
        seconds = max(1, int(round((stop_dt - start_dt).total_seconds())))
        duration_attr = f' duration="{seconds}"'

    done_attr = "false" if part.get("cut_off") else "true"
    quoted_lines = []
    for line in thinking_text.splitlines():
        if line:
            quoted_lines.append(f"> {line}")
        else:
            quoted_lines.append(">")
    quoted_text = "\n".join(quoted_lines) if quoted_lines else ""
    return (
        f'<details type="reasoning" done="{done_attr}"{duration_attr}>'
        f"\n<summary>{summary_text}</summary>\n"
        f"{quoted_text}\n"
        "</details>"
    )


def _format_tool_use(part: dict) -> str:
    name = part.get("name") or "tool"
    tool_input = part.get("input")
    try:
        input_str = json.dumps(tool_input, ensure_ascii=False) if tool_input else ""
    except TypeError:
        input_str = str(tool_input)
    header = f"🔧 used **{name}**"
    return f"{header}\n```json\n{input_str}\n```" if input_str else header


def _format_tool_result(part: dict) -> str:
    content = part.get("content")
    text = ""
    if isinstance(content, list):
        pieces = []
        for entry in content:
            if isinstance(entry, dict) and entry.get("type") == "text":
                piece = sanitize_text(entry.get("text"))
                if piece:
                    pieces.append(piece)
            elif isinstance(entry, str):
                piece = sanitize_text(entry)
                if piece:
                    pieces.append(piece)
        text = "\n".join(pieces)
    elif isinstance(content, str):
        text = sanitize_text(content)
    if not text:
        return ""
    return f"↳ tool result:\n{text}"


def _content_to_text(parts: list[Any]) -> str:
    reasoning_segments: List[str] = []
    # Everything that isn't a "thinking" block, in the order Claude produced
    # it. tool_use and tool_result used to have no handler at all: a real
    # export where the assistant called a tool (web search, code execution,
    # the analysis tool — any of these produce this same content shape) had
    # that content silently discarded. When a turn's ONLY content was a tool
    # call and its result, with the answer arriving in a later turn, the
    # whole message vanished from the import: _parse_message_list drops any
    # message whose extracted text comes back empty. That is not a rendering
    # nuance, it is conversation history disappearing with no error and
    # nothing in the output hinting that anything is missing.
    other_segments: List[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        p_type = part.get("type")
        if p_type == "thinking":
            reasoning = _format_reasoning_block(part)
            if reasoning:
                reasoning_segments.append(reasoning)
        elif p_type == "text":
            text = sanitize_text(part.get("text"))
            if text:
                other_segments.append(text)
        elif p_type == "tool_use":
            block = _format_tool_use(part)
            if block:
                other_segments.append(block)
        elif p_type == "tool_result":
            block = _format_tool_result(part)
            if block:
                other_segments.append(block)
        elif p_type:
            # Anything else (image, document, and whatever Anthropic adds
            # next) is content we don't know how to render, but dropping it
            # with no trace is worse than an honest placeholder: a reader
            # comparing the import against the original at least knows to
            # look, instead of assuming the conversation was this short.
            other_segments.append(f"[unsupported content: type={p_type}]")
    segments: List[str] = []
    if reasoning_segments:
        segments.append("\n".join(reasoning_segments))
    if other_segments:
        segments.append("\n\n".join(other_segments))
    return "\n\n".join(segments) if segments else ""


def _normalize_role(raw_role: Any, index: int) -> str:
    if isinstance(raw_role, str):
        lowered = raw_role.lower()
        if lowered in {"user", "assistant"}:
            return lowered
        if lowered == "human":
            return "user"
        if lowered == "system":
            return "assistant"
    return "assistant" if index % 2 else "user"


def _parse_message_list(msgs: list[Any], default_ts: float) -> List[Tuple[str, str, float]]:
    parsed: List[Tuple[str, str, float]] = []
    for idx, msg in enumerate(msgs):
        if not isinstance(msg, dict):
            continue
        text = ""
        if isinstance(msg.get("content"), list):
            text = _content_to_text(msg["content"])
        if not text:
            text = sanitize_text(msg.get("text"))
        if not text:
            continue
        raw_role = msg.get("role") or msg.get("sender")
        role = _normalize_role(raw_role, idx)
        ts_val = msg.get("created_at") or msg.get("updated_at") or default_ts
        ts_val = parse_timestamp(ts_val, default_ts)
        parsed.append((role, text, ts_val))
    return parsed


def parse_claude(data: Any) -> List[dict]:
    if isinstance(data, dict):
        if "chats" in data:
            convs = data.get("chats")
        else:
            convs = data.get("conversations")
    else:
        convs = data
    if not isinstance(convs, list):
        convs = [convs]

    result = []
    for item in convs:
        conv = item.get("conversation", item) if isinstance(item, dict) else {}
        title = conv.get("title") or item.get("name") or item.get("title") or "Untitled"
        conv_id = conv.get("uuid") or item.get("uuid")
        ts_raw = (
            conv.get("created_at")
            or conv.get("updated_at")
            or item.get("created_at")
            or item.get("updated_at")
            or time.time()
        )
        ts = parse_timestamp(ts_raw, time.time())

        messages: List[Tuple[str, str, float]] = []
        if isinstance(item.get("chat_messages"), list):
            messages.extend(_parse_message_list(item["chat_messages"], ts))
        elif isinstance(conv.get("messages"), list):
            messages.extend(_parse_message_list(conv["messages"], ts))
        elif isinstance(item.get("responses"), list):
            messages.append(("user", title, ts))
            for resp in item["responses"]:
                text = resp.get("response", {}).get("text")
                text = sanitize_text(text)
                if text:
                    messages.append(("assistant", text, ts))
        else:
            messages.append(("user", title, ts))
        if not messages:
            continue
        result.append({
            "title": title,
            "timestamp": ts,
            "messages": messages,
            "conversation_id": conv_id,
        })

    return result


def build_webui(conversation: dict, user_id: str) -> Tuple[Dict[str, Any], str]:
    conv_uuid = str(uuid.uuid4())
    messages_map: Dict[str, Any] = {}
    messages_list: List[Dict[str, Any]] = []
    prev_id: str | None = None
    for role, content, ts in conversation["messages"]:
        msg_id = str(uuid.uuid4())
        clean = sanitize_text(content)
        msg = {
            "id": msg_id,
            "parentId": prev_id,
            "childrenIds": [],
            "role": role,
            "content": clean,
            "timestamp": int(ts),
        }
        if role == "user":
            msg["models"] = [MODEL]
        else:
            msg.update(
                {
                    "model": MODEL,
                    "modelName": MODEL_NAME,
                    "modelIdx": 0,
                    "userContext": None,
                    "lastSentence": extract_last_sentence(clean),
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "done": True,
                }
            )
        if prev_id:
            messages_map[prev_id]["childrenIds"].append(msg_id)
        messages_map[msg_id] = msg
        messages_list.append(msg)
        prev_id = msg_id
    webui = {
        "id": "",
        "title": conversation["title"],
        "models": [MODEL],
        "params": {},
        "history": {"messages": messages_map, "currentId": prev_id},
        "messages": messages_list,
        "tags": [],
        "timestamp": int(conversation["timestamp"] * 1000),
        "files": [],
    }
    if user_id:
        webui["userId"] = user_id
    return webui, conv_uuid


def slugify(text: str) -> str:
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^a-zA-Z0-9_\-]", "", text)
    return text[:50] or "chat"


def convert_file(path: str, user_id: str, outdir: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    conversations = parse_claude(data)
    os.makedirs(outdir, exist_ok=True)
    for conv in conversations:
        out, conv_uuid = build_webui(conv, user_id)
        conv_id = conv.get("conversation_id")
        unique = conv_id if conv_id else conv_uuid
        fname = f"{slugify(conv['title'])}_{unique}.json"
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Convert Claude exports to open-webui JSON")
    parser.add_argument("files", nargs="+", help="Claude export JSON files")
    parser.add_argument("--userid", required=True, help="User ID for output files")
    parser.add_argument("--output-dir", default="output", help="Directory for output JSON files")
    args = parser.parse_args()
    outdir = os.path.join(args.output_dir, SUBDIR)
    for path in args.files:
        try:
            convert_file(path, args.userid, outdir)
        except Exception as exc:
            print(f"Failed to convert {path}: {exc}")


if __name__ == "__main__":
    run_cli()
