#!/usr/bin/env python3
"""Convert OpenRouter Playground (orpg) chat exports to open-webui JSON."""

import argparse
import json
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

INVALID_RE = re.compile(r"[\ue000-\uf8ff]")


def sanitize_text(text: Any) -> str:
    """Return ``text`` without private-use Unicode characters."""
    if not isinstance(text, str):
        return ""
    return INVALID_RE.sub("", text)


SUBDIR = "openrouter"


def extract_last_sentence(text: str) -> str:
    """Extract the last sentence from text for summary purposes."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    matches = re.findall(r"[^.!?]*[.!?]", cleaned, flags=re.DOTALL)
    if matches:
        return matches[-1].strip()
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return lines[-1] if lines else cleaned


def parse_timestamp(value: Any, default: float) -> float:
    """Parse various timestamp formats to Unix timestamp."""
    if isinstance(value, (int, float)):
        if value > 4102444800:
            return float(value) / 1000
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return default


def _extract_text_from_item(item_data: dict) -> str:
    """Extract text content from an item's data field."""
    if not isinstance(item_data, dict):
        return ""
    
    data = item_data.get("data", {})
    if not isinstance(data, dict):
        return ""
    
    content = data.get("content")
    
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type", "")
                if part_type in ("input_text", "output_text", "text"):
                    text = sanitize_text(part.get("text", ""))
                    if text:
                        text_parts.append(text)
                elif part_type == "thinking":
                    thinking = sanitize_text(part.get("thinking", ""))
                    if thinking:
                        text_parts.append(f"<details>\n<summary>Thinking</summary>\n\n{thinking}\n</details>")
            elif isinstance(part, str):
                text_parts.append(sanitize_text(part))
        return "\n\n".join(filter(None, text_parts))
    
    if isinstance(content, str):
        return sanitize_text(content)
    
    return ""


def parse_openrouter_playground(data: dict) -> List[dict]:
    """Parse OpenRouter Playground (orpg.3.0) export format."""
    version = data.get("version", "")
    if not version.startswith("orpg"):
        print(f"⚠️  Warning: Unknown format version: {version}")
    
    title = data.get("title", "OpenRouter Chat")
    characters = data.get("characters", {})
    messages_dict = data.get("messages", {})
    items_dict = data.get("items", {})
    
    if not messages_dict:
        print("❌ No messages found in the file")
        return []
    
    messages_list = []
    for msg_id, msg in messages_dict.items():
        if not isinstance(msg, dict):
            continue
        created_at = msg.get("createdAt") or msg.get("created_at")
        ts = parse_timestamp(created_at, time.time())
        messages_list.append({"id": msg_id, "msg": msg, "timestamp": ts})
    
    messages_list.sort(key=lambda x: x["timestamp"])
    
    parsed_messages: List[Tuple[str, str, float, str]] = []
    
    for entry in messages_list:
        msg = entry["msg"]
        ts = entry["timestamp"]
        
        msg_type = msg.get("type", "")
        character_id = msg.get("characterId", "")
        
        if msg_type == "user" or character_id == "USER":
            role = "user"
        elif msg_type == "assistant":
            role = "assistant"
        else:
            continue
        
        model = "openrouter"
        if character_id and character_id != "USER" and character_id in characters:
            char = characters[character_id]
            model = char.get("model", "openrouter")
        
        msg_items = msg.get("items", [])
        text_parts = []
        
        for item_ref in msg_items:
            if not isinstance(item_ref, dict):
                continue
            item_id = item_ref.get("id")
            item_type = item_ref.get("type", "")
            if item_type != "message":
                continue
            if item_id and item_id in items_dict:
                item_data = items_dict[item_id]
                text = _extract_text_from_item(item_data)
                if text:
                    text_parts.append(text)
        
        content = "\n\n".join(text_parts)
        
        if content:
            parsed_messages.append((role, content, ts, model))
    
    if not parsed_messages:
        print("❌ No valid messages with content found")
        return []
    
    conv_ts = parsed_messages[0][2] if parsed_messages else time.time()
    
    return [{
        "title": title,
        "timestamp": conv_ts,
        "messages": parsed_messages,
        "conversation_id": None,
        "model": parsed_messages[0][3] if parsed_messages else "openrouter",
    }]


def parse_openrouter(data: Any) -> List[dict]:
    """Parse OpenRouter export data into a list of conversations."""
    if not isinstance(data, dict):
        print(f"❌ Expected dict, got {type(data)}")
        return []
    
    version = data.get("version", "")
    if version.startswith("orpg") or "characters" in data:
        return parse_openrouter_playground(data)
    
    # Fallback for other formats...
    print(f"❌ Unknown format. Keys: {list(data.keys())}")
    return []


def build_webui(conversation: dict, user_id: str) -> Dict[str, Any]:
    """Build open-webui format JSON from parsed conversation."""
    conv_uuid = str(uuid.uuid4())
    model = conversation.get("model", "openrouter")
    now_ts = int(time.time())
    
    messages_map: Dict[str, Any] = {}
    messages_list: List[Dict[str, Any]] = []
    prev_id: Optional[str] = None
    
    for role, content, ts, msg_model in conversation["messages"]:
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
            msg["models"] = [msg_model or model]
        else:
            msg.update({
                "model": msg_model or model,
                "modelName": msg_model or model,
                "modelIdx": 0,
                "userContext": None,
                "lastSentence": extract_last_sentence(clean),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "done": True,
            })
        
        if prev_id:
            messages_map[prev_id]["childrenIds"].append(msg_id)
        
        messages_map[msg_id] = msg
        messages_list.append(msg)
        prev_id = msg_id
    
    # Build the inner chat object
    chat_obj = {
        "id": conv_uuid,
        "title": conversation["title"],
        "models": [model],
        "params": {},
        "history": {"messages": messages_map, "currentId": prev_id},
        "messages": [{"role": messages_list[0]["role"], "content": messages_list[0]["content"]}] if messages_list else [],
        "files": [],
        "tags": [],
        "timestamp": int(conversation["timestamp"] * 1000),
    }
    
    # 构建完整的外层对象（符合 Open-WebUI 导入格式）
    webui_obj = {
        "id": conv_uuid,
        "user_id": user_id,
        "title": conversation["title"],
        "chat": chat_obj,
        "updated_at": now_ts,
        "created_at": int(conversation["timestamp"]),
        "share_id": None,
        "archived": False,
        "pinned": False,
        "meta": {"tags": []},
        "folder_id": None,
    }
    
    return webui_obj


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^a-zA-Z0-9_\-]", "", text)
    return text[:50] or "chat"


def convert_file(path: str, user_id: str, outdir: str) -> None:
    """Convert a single OpenRouter export file."""
    print(f"📂 Reading file: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"📊 Data type: {type(data)}")
    if isinstance(data, dict):
        print(f"🔑 Top-level keys: {list(data.keys())}")
        if "version" in data:
            print(f"📌 Version: {data['version']}")
    
    conversations = parse_openrouter(data)
    print(f"💬 Found {len(conversations)} conversation(s)")
    
    if not conversations:
        print("❌ No conversations to convert")
        return
    
    os.makedirs(outdir, exist_ok=True)
    
    # 收集所有对话到一个数组里（Open-WebUI 导入需要数组格式）
    all_chats = []
    
    for conv in conversations:
        webui_obj = build_webui(conv, user_id)
        all_chats.append(webui_obj)
        msg_count = len(conv["messages"])
        print(f"✅ Processed: {conv['title']} ({msg_count} messages)")
    
    # 输出为单个文件（数组格式）
    output_path = os.path.join(outdir, "openrouter_import.json")
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(all_chats, fh, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 Done! Output file: {output_path}")
    print(f"📝 Total {len(all_chats)} conversation(s) ready to import")


def run_cli() -> None:
    """Run the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Convert OpenRouter chat exports to open-webui JSON"
    )
    parser.add_argument("files", nargs="+", help="OpenRouter export JSON files")
    parser.add_argument("--userid", required=True, help="User ID for output files")
    parser.add_argument(
        "--output-dir", default="output", help="Directory for output JSON files"
    )
    args = parser.parse_args()
    
    outdir = os.path.join(args.output_dir, SUBDIR)
    
    for path in args.files:
        try:
            convert_file(path, args.userid, outdir)
        except Exception as exc:
            print(f"❌ Failed to convert {path}: {exc}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    run_cli()