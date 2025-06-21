import argparse
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Tuple
from jsonschema import validate, ValidationError

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schemas")

with open(os.path.join(SCHEMA_DIR, "chatgpt-schema.json"), "r", encoding="utf-8") as f:
    CHATGPT_SCHEMA = json.load(f)
with open(os.path.join(SCHEMA_DIR, "grok-schema.json"), "r", encoding="utf-8") as f:
    GROK_SCHEMA = json.load(f)
with open(os.path.join(SCHEMA_DIR, "claude-schema.json"), "r", encoding="utf-8") as f:
    CLAUDE_SCHEMA_EXAMPLE = json.load(f)

MODEL_MAP = {
    "ChatGPT": "openai/chatgpt-4o-latest",
    "Grok": "x-ai/grok-3",
    "Claude": "anthropic/claude-3.7-sonnet",
}
MODEL_NAME_MAP = {
    "ChatGPT": "ChatGPT 4o (latest)",
    "Grok": "Grok 3",
    "Claude": "Claude 3.7 Sonnet",
}


def detect_format(
    data: Any,
    *,
    validate_schema: bool = False,
    forced_format: str | None = None,
) -> str:
    if forced_format:
        normalized = forced_format.lower()
        if normalized == "chatgpt":
            if validate_schema and isinstance(data, list):
                validate(instance=data, schema=CHATGPT_SCHEMA)
            return "ChatGPT"
        if normalized == "grok":
            if validate_schema and isinstance(data, dict):
                validate(instance=data, schema=GROK_SCHEMA)
            return "Grok"
        if normalized == "claude":
            if validate_schema and isinstance(data, (list, dict)):
                validate(instance=data, schema=CLAUDE_SCHEMA_EXAMPLE)
            return "Claude"
        raise ValueError(f"Unknown forced format: {forced_format}")

    if isinstance(data, list):
        if validate_schema:
            try:
                validate(instance=data, schema=CHATGPT_SCHEMA)
                return "ChatGPT"
            except ValidationError:
                pass
        if data and isinstance(data[0], dict):
            item = data[0]
            if "mapping" in item:
                return "ChatGPT"
            if "chat_messages" in item and "uuid" not in item:
                return "ChatGPT"
            if (
                ("title" in item or "name" in item)
                and any(k in item for k in ("create_time", "update_time"))
            ):
                return "ChatGPT"
            if {"uuid", "chat_messages"}.issubset(item.keys()):
                return "Claude"

    if isinstance(data, dict):
        if validate_schema:
            try:
                validate(instance=data, schema=GROK_SCHEMA)
                return "Grok"
            except ValidationError:
                pass
        if "meta" in data and "chats" in data:
            return "Claude"
        if "conversations" in data:
            conversations = data.get("conversations")
            if isinstance(conversations, list) and conversations:
                first = conversations[0]
                if isinstance(first, dict) and {"conversation", "responses"}.issubset(first.keys()):
                    return "Claude"
            return "Grok"
        if "title" in data and "mapping" in data:
            return "ChatGPT"
        if "name" in data and "chat_messages" in data:
            return "ChatGPT"
    raise ValueError("Unknown export format")


def extract_last_sentence(text: str) -> str:
    """Return the last sentence of ``text``.

    Falls back to the last non-empty line if no sentence ending
    punctuation is found.
    """
    cleaned = text.strip()
    if not cleaned:
        return ""
    matches = re.findall(r"[^.!?]*[.!?]", cleaned, flags=re.DOTALL)
    if matches:
        return matches[-1].strip()
    # No punctuation; use the last non-empty line
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return lines[-1] if lines else cleaned


def parse_chatgpt(data: Any) -> List[dict]:
    conversations = data if isinstance(data, list) else [data]
    result = []
    for item in conversations:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or "Untitled"
        ts = item.get("create_time") or item.get("update_time") or time.time()
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
            if root:
                part = root.get("message", {}).get("content", {}).get("parts", [])
                if part:
                    messages.append(("user", part[0], ts))
            for key, val in mapping.items():
                if key == "client-created-root":
                    continue
                part = val.get("message", {}).get("content", {}).get("parts", [])
                if part:
                    messages.append(("assistant", part[0], ts))
                    break
        else:
            messages.append(("user", title, ts))
        result.append({"title": title, "timestamp": ts, "messages": messages})
    return result


def parse_claude(data: Any) -> List[dict]:
    convs = data.get("conversations") if isinstance(data, dict) else data
    if not isinstance(convs, list):
        convs = [data]
    result = []
    for item in convs:
        conv = item.get("conversation", {}) if isinstance(item, dict) else {}
        title = conv.get("title") or item.get("name") or "Untitled"
        ts = conv.get("created_at") or conv.get("updated_at") or time.time()
        resp = ""
        if isinstance(item.get("responses"), list) and item["responses"]:
            resp = item["responses"][0].get("response", {}).get("text", "")
        messages = [("user", title, ts)]
        if resp:
            messages.append(("assistant", resp, ts))
        result.append({"title": title, "timestamp": ts, "messages": messages})
    return result


def parse_grok(data: Any) -> List[dict]:
    convs = data.get("conversations") if isinstance(data, dict) and "conversations" in data else [data]
    result = []
    for item in convs:
        obj = item.get("conversation", item)
        title = obj.get("title") or "Untitled"
        ts = obj.get("create_time") or obj.get("modify_time") or time.time()
        mapping = item.get("mapping") or obj.get("mapping") or data.get("mapping")
        messages: List[Tuple[str, str, float]] = []
        if isinstance(mapping, dict):
            part = mapping.get("client-created-root", {}).get("message", {}).get("content", {}).get("parts", [])
            if part:
                messages.append(("user", part[0], ts))
            for key, val in mapping.items():
                if key == "client-created-root":
                    continue
                part = val.get("message", {}).get("content", {}).get("parts", [])
                if part:
                    messages.append(("assistant", part[0], ts))
                    break
        result.append({"title": title, "timestamp": ts, "messages": messages})
    return result


def build_webui(conversation: dict, fmt: str, user_id: str) -> Tuple[Dict[str, Any], str]:
    conv_uuid = str(uuid.uuid4())
    model = MODEL_MAP[fmt]
    model_name = MODEL_NAME_MAP[fmt]
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
            msg["models"] = [model]
        else:
            msg.update({
                "model": model,
                "modelName": model_name,
                "modelIdx": 0,
                "userContext": None,
                "lastSentence": extract_last_sentence(content),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "done": True,
            })
        if prev_id:
            messages_map[prev_id]["childrenIds"].append(msg_id)
        messages_map[msg_id] = msg
        messages_list.append(msg)
        prev_id = msg_id
    webui = {
        "id": "",
        "title": conversation["title"],
        "models": [model],
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
    fmt = detect_format(data)
    if fmt == "ChatGPT":
        conversations = parse_chatgpt(data)
    elif fmt == "Claude":
        conversations = parse_claude(data)
    elif fmt == "Grok":
        conversations = parse_grok(data)
    else:
        raise ValueError("Unsupported format")
    os.makedirs(outdir, exist_ok=True)
    for conv in conversations:
        out, conv_uuid = build_webui(conv, fmt, user_id)
        fname = f"{slugify(conv['title'])}_{conv_uuid}.json"
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert chat exports to open-webui JSON")
    parser.add_argument("files", nargs="+", help="Chat export JSON files")
    parser.add_argument("--userid", required=True, help="User ID for output files")
    parser.add_argument("--output-dir", default="output", help="Directory for output JSON files")
    args = parser.parse_args()
    for path in args.files:
        try:
            convert_file(path, args.userid, args.output_dir)
        except Exception as e:
            print(f"Failed to convert {path}: {e}")


if __name__ == "__main__":
    main()
