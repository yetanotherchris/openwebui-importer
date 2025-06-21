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

MODEL = "anthropic/claude-3.7-sonnet"
MODEL_NAME = "Claude 3.7 Sonnet"


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


def _parse_message_list(msgs: list[Any], default_ts: float) -> List[Tuple[str, str, float]]:
    parsed: List[Tuple[str, str, float]] = []
    for idx, msg in enumerate(msgs):
        if not isinstance(msg, dict):
            continue
        text = msg.get("text")
        if not text and isinstance(msg.get("content"), list):
            parts = [p.get("text", "") for p in msg.get("content", [])]
            text = "".join(parts)
        if not text:
            continue
        role = msg.get("role") or msg.get("sender")
        if role not in {"user", "assistant"}:
            role = "assistant" if idx % 2 else "user"
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
                if text:
                    messages.append(("assistant", text, ts))
        else:
            messages.append(("user", title, ts))

        result.append({"title": title, "timestamp": ts, "messages": messages})

    return result


def build_webui(conversation: dict, user_id: str) -> Tuple[Dict[str, Any], str]:
    conv_uuid = str(uuid.uuid4())
    messages_map: Dict[str, Any] = {}
    messages_list: List[Dict[str, Any]] = []
    prev_id: str | None = None
    for role, content, ts in conversation["messages"]:
        msg_id = str(uuid.uuid4())
        msg = {
            "id": msg_id,
            "parentId": prev_id,
            "childrenIds": [],
            "role": role,
            "content": content,
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
                    "lastSentence": extract_last_sentence(content),
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
        fname = f"{slugify(conv['title'])}_{conv_uuid}.json"
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Convert Claude exports to open-webui JSON")
    parser.add_argument("files", nargs="+", help="Claude export JSON files")
    parser.add_argument("--userid", required=True, help="User ID for output files")
    parser.add_argument("--output-dir", default="output", help="Directory for output JSON files")
    args = parser.parse_args()
    for path in args.files:
        try:
            convert_file(path, args.userid, args.output_dir)
        except Exception as exc:
            print(f"Failed to convert {path}: {exc}")


if __name__ == "__main__":
    run_cli()
