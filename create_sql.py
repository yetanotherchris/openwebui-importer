#!/usr/bin/env python3
"""Generate SQL insert statements from open-webui chat JSON files."""
import argparse
import json
import os
import uuid


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def escape_sql_string(value: str) -> str:
    return value.replace("'", "''")


def build_meta(tags: list[str]) -> str:
    meta = json.dumps({"tags": tags}, ensure_ascii=True)
    return escape_sql_string(meta)


def json_to_sql(path: str, tags: list[str]) -> str:
    data = load_json(path)
    chat_json = json.dumps(data, ensure_ascii=True)
    chat_json = escape_sql_string(chat_json)

    user_id = data.get("userId")
    if not user_id:
        raise ValueError(f"userId missing in {path}")
    title = escape_sql_string(data.get("title", ""))
    timestamp_ms = data.get("timestamp", 0)
    created_at = int(int(timestamp_ms) / 1000)
    record_id = str(uuid.uuid4())

    meta = build_meta(tags)

    sql = (
        'INSERT INTO "main"."chat" ("id","user_id","title","share_id","archived","created_at","updated_at","chat","pinned","meta","folder_id")\n'
        f"VALUES ('{record_id}','{user_id}','{title}',NULL,0,{created_at},{created_at},'{chat_json}',0,'{meta}',NULL);"
    )
    return sql


def gather_files(paths: list[str]) -> list[str]:
    result = []
    for p in paths:
        if os.path.isdir(p):
            for name in os.listdir(p):
                if name.endswith('.json'):
                    result.append(os.path.join(p, name))
        else:
            result.append(p)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create SQL inserts for open-webui chats")
    parser.add_argument("files", nargs="+", help="Chat JSON files or directories")
    parser.add_argument("--tags", default="imported", help="Comma-separated tags for the meta field")
    parser.add_argument("--output", help="Write SQL statements to this file")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(',') if t.strip()] or ["imported"]

    files = gather_files(args.files)
    inserts = []
    for fpath in files:
        try:
            inserts.append(json_to_sql(fpath, tags))
        except Exception as exc:
            raise SystemExit(f"Failed to process {fpath}: {exc}")

    output = "\n".join(inserts)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
