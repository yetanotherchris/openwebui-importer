#!/usr/bin/env python3
"""Convert Grok exports to open-webui JSON."""

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

MODEL = "x-ai/grok-4"
MODEL_NAME = "Grok 4"
SUBDIR = "grok"


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


def parse_grok(data: Any) -> List[dict]:
    convs = data.get("conversations") if isinstance(data, dict) and "conversations" in data else [data]
    result = []
    for item in convs:
        obj = item.get("conversation", item)
        title = obj.get("title") or "Untitled"
        ts_raw = obj.get("create_time") or obj.get("modify_time") or time.time()
        ts = parse_timestamp(ts_raw, time.time())
        conv_id = obj.get("conversation_id") or obj.get("id")
        mapping = item.get("mapping") or obj.get("mapping") or data.get("mapping")
        responses = item.get("responses")
        messages: List[Tuple[str, str, float]] = []
        if isinstance(responses, list):
            def sort_key(resp: Any) -> float:
                ts_val = resp.get("response", {}).get("create_time")
                return parse_timestamp(ts_val, ts)

            responses_sorted = sorted(
                [r for r in responses if isinstance(r, dict)], key=sort_key
            )
            for resp in responses_sorted:
                inner = resp.get("response", {})
                text = inner.get("message")
                text = sanitize_text(text)
                if not text:
                    continue
                sender = inner.get("sender") or "assistant"
                role = "user" if str(sender).lower() == "human" else "assistant"
                ts_val = inner.get("create_time")
                messages.append((role, text, parse_timestamp(ts_val, ts)))
        elif isinstance(mapping, dict):
            root_node = mapping.get("client-created-root")
            if isinstance(root_node, dict):
                part = root_node.get("message", {}).get("content", {}).get("parts", [])
                if part:
                    messages.append(("user", sanitize_text(part[0]), ts))
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
                messages.append((role, sanitize_text(parts[0]), parse_timestamp(ts_val, ts)))
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
    conversations = parse_grok(data)
    os.makedirs(outdir, exist_ok=True)
    for conv in conversations:
        out, conv_uuid = build_webui(conv, user_id)
        conv_id = conv.get("conversation_id")
        unique = conv_id if conv_id else conv_uuid
        fname = f"{slugify(conv['title'])}_{unique}.json"
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Convert Grok exports to open-webui JSON")
    parser.add_argument("files", nargs="+", help="Grok export JSON files")
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
