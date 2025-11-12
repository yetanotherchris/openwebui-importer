#!/usr/bin/env python3
"""Convert ChatGPT exports to open-webui JSON."""

import argparse
import json
import os
import re
from typing import Any, Dict, List, Tuple
import time
import uuid
from datetime import datetime

INVALID_RE = re.compile(r"[\ue000-\uf8ff]")


def sanitize_text(text: Any) -> str:
    """Return ``text`` without private-use Unicode characters."""
    if not isinstance(text, str):
        return ""
    return INVALID_RE.sub("", text)

MODEL = "openai/GPT-5"
MODEL_NAME = "OpenAI: GPT-5"
SUBDIR = "chatgpt"


def extract_last_sentence(text: Any) -> str:
    """Return the last sentence of ``text`` if it is a string."""
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    if not cleaned:
        return ""
    matches = re.findall(r"[^.!?]*[.!?]", cleaned, flags=re.DOTALL)
    if matches:
        return matches[-1].strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return lines[-1] if lines else cleaned


def _parts_to_text(parts: List[Any]) -> str:
    """Return concatenated text from ChatGPT message parts."""
    texts: List[str] = []
    for part in parts:
        if isinstance(part, str):
            texts.append(sanitize_text(part))
        elif isinstance(part, dict) and "text" in part:
            val = part.get("text")
            if isinstance(val, str):
                texts.append(sanitize_text(val))
    return "".join(texts)


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
        conv_id = item.get("conversation_id") or item.get("id")
        messages: List[Tuple[str, str, float]] = []
        if isinstance(item.get("chat_messages"), list):
            for idx, msg in enumerate(item["chat_messages"]):
                text = msg.get("text")
                if not text and isinstance(msg.get("content"), list):
                    text = _parts_to_text(msg["content"])
                text = sanitize_text(text)
                if text:
                    role = "user" if idx % 2 == 0 else "assistant"
                    messages.append((role, text, ts))
        elif isinstance(item.get("mapping"), dict):
            mapping = item["mapping"]
            node = None
            current_id = item.get("current_node")
            if current_id and isinstance(mapping.get(current_id), dict):
                node = mapping[current_id]
                stack: List[Tuple[str, str, float]] = []
                while isinstance(node, dict):
                    msg = node.get("message") or {}
                    parts = msg.get("content", {}).get("parts", [])
                    if parts:
                        role = msg.get("author", {}).get("role", "assistant")
                        if role in {"user", "assistant"}:
                            ts_val = msg.get("create_time") or msg.get("timestamp") or ts
                            text = sanitize_text(_parts_to_text(parts))
                            if text:
                                stack.append((role, text, parse_timestamp(ts_val, ts)))
                    parent_id = node.get("parent")
                    if not parent_id:
                        break
                    node = mapping.get(parent_id)
                messages.extend(reversed(stack))
            else:
                node = mapping.get("client-created-root")
                if not isinstance(node, dict):
                    # Some exports don't use the "client-created-root" key. In
                    # those cases, attempt to locate the root node by finding the
                    # entry with no parent value.
                    for val in mapping.values():
                        if isinstance(val, dict) and not val.get("parent"):
                            node = val
                            break
                if isinstance(node, dict):
                    next_ids = node.get("children") or []
                    while next_ids:
                        node = mapping.get(next_ids[0])
                        if not isinstance(node, dict):
                            break
                        msg = node.get("message") or {}
                        parts = msg.get("content", {}).get("parts", [])
                        if parts:
                            role = msg.get("author", {}).get("role", "assistant")
                            if role in {"user", "assistant"}:
                                ts_val = msg.get("create_time") or msg.get("timestamp") or ts
                                text = sanitize_text(_parts_to_text(parts))
                                if text:
                                    messages.append((role, text, parse_timestamp(ts_val, ts)))
                        next_ids = node.get("children") or []
        else:
            messages.append(("user", title, ts))
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


def slugify(text: Any) -> str:
    if not isinstance(text, str):
        text = str(text)
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
        conv_id = conv.get("conversation_id")
        unique = conv_id if conv_id else conv_uuid
        fname = f"{slugify(conv['title'])}_{unique}.json"
        outer = {
            "id": "",
            "user_id": user_id,
            "title": conv.get("title", ""),
            "chat": out
        }
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as fh:
            json.dump([outer], fh, ensure_ascii=False, indent=2)


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Convert ChatGPT exports to open-webui JSON")
    parser.add_argument("files", nargs="+", help="ChatGPT export JSON files")
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
