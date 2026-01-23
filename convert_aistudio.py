#!/usr/bin/env python3
"""Convert AI Studio exports to open-webui JSON."""

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


MODEL = "google/gemini"
MODEL_NAME = "Gemini"
SUBDIR = "gemini"


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


def parse_gemini(data: Any, default_title: str = "Untitled") -> List[dict]:
    # Handle list of conversations if applicable (though example was a single dict)
    if isinstance(data, list):
        return [c for item in data for c in parse_gemini(item, default_title)]
        
    if not isinstance(data, dict):
        return []
    
    conversations = []
    
    # Check for the expected structure
    chunks = data.get("chunkedPrompt", {}).get("chunks", [])
    if not chunks and "conversations" in data:
         # Fallback if it's a different format wrapper
         return parse_gemini(data["conversations"], default_title)

    messages = []
    ts = time.time()  # Default timestamp as none are provided in the schema
    thought_buffer = ""
    
    for chunk in chunks:
        role = chunk.get("role")
        text = chunk.get("text", "")
        is_thought = chunk.get("isThought", False)
        
        # Handle attachments if present
        if "driveImage" in chunk:
             image_id = chunk["driveImage"].get("id", "unknown")
             if text:
                 text = f"[Image Attachment: {image_id}]\n\n{text}"
             else:
                 text = f"[Image Attachment: {image_id}]"

        if is_thought:
            thought_buffer += text + "\n\n"
            continue

        # Map roles
        if role == "model":
            role = "assistant"
        elif role != "user":
            # Fallback for unknown roles (e.g. system?)
            role = "system" if role == "system" else role
            
        clean_text = sanitize_text(text)
        if thought_buffer:
            # Wrap thinking in Open WebUI details tag
            reasoning = sanitize_text(thought_buffer).strip()
            clean_text = f'<details type="reasoning" done="true" duration="0">\n<summary>Thought</summary>\n{reasoning}\n</details>\n' + clean_text
            thought_buffer = ""
            
        if not clean_text:
            continue
            
        messages.append((role, clean_text, ts))

    # If there's a thought buffer left at the end (no following message)
    if thought_buffer:
        reasoning = sanitize_text(thought_buffer).strip()
        final_thought = f'<details type="reasoning" done="true" duration="0">\n<summary>Thought</summary>\n{reasoning}\n</details>\n'
        messages.append(("assistant", final_thought, ts))

    if messages:
        conversations.append({
            "title": default_title,
            "timestamp": ts,
            "messages": messages,
            "conversation_id": str(uuid.uuid4()),
        })
        
    return conversations


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
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return

    # Use filename as default title
    filename_title = os.path.splitext(os.path.basename(path))[0]
    conversations = parse_gemini(data, default_title=filename_title)
    
    os.makedirs(outdir, exist_ok=True)
    for conv in conversations:
        out, conv_uuid = build_webui(conv, user_id)
        conv_id = conv.get("conversation_id")
        unique = conv_id if conv_id else conv_uuid
        fname = f"{slugify(conv['title'])}_{unique}.json"
        
        output_path = os.path.join(outdir, fname)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"Converted: {path} -> {output_path}")


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Convert Gemini exports to open-webui JSON")
    parser.add_argument("files", nargs="+", help="Gemini export JSON files")
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
