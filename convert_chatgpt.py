#!/usr/bin/env python3
"""Convert ChatGPT exports to open-webui JSON."""

import argparse
import json
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

MODEL = "openai/chatgpt-4o-latest"
MODEL_NAME = "ChatGPT 4o (latest)"


def extract_last_sentence(text: str) -> str:
    """Return the last sentence of ``text``."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    matches = re.findall(r"[^.!?]*[.!?]", cleaned, flags=re.DOTALL)
    if matches:
        return matches[-1].strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return lines[-1] if lines else cleaned


def parse_timestamp(value: Any, default: float) -> float:
    """Convert ``value`` to a Unix timestamp."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return default


def parse_chatgpt(data: Any) -> List[dict]:
    conversations = data if isinstance(data, list) else [data]
    result = []
    for item in conversations:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or "Untitled"
        ts_raw = item.get("create_time") or item.get("update_time") or time.time()
        ts = parse_timestamp(ts_raw, time.time())
        messages: List[Tuple[str, str, float]] = []
        if isinstance(item.get("chat_messages"), list):
            for idx, msg in enumerate(item["chat_messages"]):
                text = msg.get("text")
                if not text and isinstance(msg.get("content"), list):
                    parts = [p.get("text", "") for p in msg["content"]]
                    text = "".join(parts)
                if text:
                    role = "user" if idx % 2 == 0 else "assistant"
                    messages.append((role, text, ts))
        elif isinstance(item.get("mapping"), dict):
            mapping = item["mapping"]
            root = mapping.get("client-created-root")
            if isinstance(root, dict):
                part = root.get("message", {}).get("content", {}).get("parts", [])
                if part:
                    messages.append(("user", part[0], ts))
            other_nodes = [v for k, v in mapping.items() if k != "client-created-root"]

            def sort_key(node: Any) -> float:
                ts_val = node.get("message", {}).get("create_time") or node.get("message", {}).get("timestamp")
                return parse_timestamp(ts_val, ts)

            other_nodes.sort(key=sort_key)
            for node in other_nodes:
                if not isinstance(node, dict):
                    continue
                msg = node.get("message", {})
                parts = msg.get("content", {}).get("parts", [])
                if not parts:
                    continue
                role = msg.get("author", {}).get("role", "assistant")
                ts_val = msg.get("create_time") or msg.get("timestamp") or ts
                messages.append((role, parts[0], parse_timestamp(ts_val, ts)))
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
    conversations = parse_chatgpt(data)
    os.makedirs(outdir, exist_ok=True)
    for conv in conversations:
        out, conv_uuid = build_webui(conv, user_id)
        fname = f"{slugify(conv['title'])}_{conv_uuid}.json"
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Convert ChatGPT exports to open-webui JSON")
    parser.add_argument("files", nargs="+", help="ChatGPT export JSON files")
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
