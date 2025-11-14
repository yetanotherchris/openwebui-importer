#!/usr/bin/env python3
"""Convert Claude exports to open-webui JSON."""

import argparse
import json
import os
import re
import time
import uuid
from datetime import datetime
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
        return datetime.fromtimestamp(float(value))
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


def _content_to_text(parts: list[Any]) -> str:
    reasoning_segments: List[str] = []
    text_segments: List[str] = []
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
                text_segments.append(text)
    segments: List[str] = []
    if reasoning_segments:
        segments.append("\n".join(reasoning_segments))
    if text_segments:
        segments.append("\n\n".join(text_segments))
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
