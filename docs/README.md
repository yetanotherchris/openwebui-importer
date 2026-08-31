# openwebui-importer

**Import Grok, Claude, AI Studio (Gemini), ChatGPT and Openrouter chats into [open-webui](https://github.com/open-webui/open-webui).**

This importer tool has two Python scripts: one for converting the model JSON files to openweb-ui format JSON, the second for 
creating a SQL script to import the JSON into the openweb-ui SQLite database.  

The imported chats are given the tags `imported-aistudio`, `imported-chatgpt`, `imported-claude`, `imported-openrouter` and `imported-grok`.

Any private-use Unicode characters occasionally found in model exports are stripped from the message text during conversion.

OpenRouter Playground stores chat history in browser localStorage and exports in `orpg.3.0` format. This script handles that specific format and outputs a single JSON file ready for direct import via Open-WebUI's built-in import feature.

## Finding your Open WebUI user ID

Every converter needs `--userid`, and it has to be the exact UUID Open
WebUI already assigned your account, not your name or email. The
reliable way to get it is to query `webui.db` directly.

The database lives inside the `open-webui` container's data volume, at
`/app/backend/data/webui.db`. Reading it through a short-lived container
mounted against that same volume works regardless of platform — some
Docker setups (Docker Desktop's VM, OrbStack, a remote host) don't expose
named-volume paths to the host filesystem at all, or expose them through
a bridge that doesn't handle SQLite's file locking correctly, so this is
also the version worth reaching for even if you think you can browse the
volume directly:

```bash
docker run --rm -v open-webui:/data alpine sh -c \
  "apk add --no-cache sqlite >/dev/null && sqlite3 /data/webui.db 'select id, email, name from user;'"
```

Replace `open-webui` with your actual volume name if your deployment
names it differently — check with `docker volume ls`. The `id` column is
the value every `--userid` flag below wants.

This is a read-only query, so it's safe to run while Open WebUI is up.
The same is not true once you get to running the SQL `create_sql.py`
generates: stop the Open WebUI container first, and keep a copy of
`webui.db` from before you ran it. Writing to the database while the app
still has it open risks a corrupted WAL file, which costs a lot more time
than the import was meant to save.

## Quick start

```
python ./convert_chatgpt.py --userid="get-this-from-your-webui.db" ./chatgpt.json
python ./create_sql.py ./output/chatgpt --tags="imported-chatgpt" --output=chatgpt.sql
--
python ./convert_aistudio.py --userid="get-this-from-your-webui.db" ./aistudio_example.json
python ./create_sql.py ./output/aistudio --tags="imported-aistudio" --output=aistudio.sql
--
python ./convert_claude.py --userid="get-this-from-your-webui.db" ./claude_example.json
python ./create_sql.py ./output/claude --tags="imported-claude" --output=claude.sql
```

## Quickstart Docker

```bash
docker run --rm -v $(pwd)/data:/data \
  ghcr.io/yetanotherchris/openwebui-importer:latest \
  python convert_chatgpt.py --userid="your-user-id" --output-dir=/data/output /data/chatgpt.json

docker run --rm -v $(pwd)/data:/data \
  ghcr.io/yetanotherchris/openwebui-importer:latest \
  python create_sql.py /data/output/chatgpt --tags="imported-chatgpt" --output=/data/chatgpt.sql
```

```powershell
docker run --rm -v ${PWD}/data:/data `
  ghcr.io/yetanotherchris/openwebui-importer:latest `
  python convert_chatgpt.py --userid="your-user-id" --output-dir=/data/output /data/chatgpt.json

docker run --rm -v ${PWD}/data:/data `
  ghcr.io/yetanotherchris/openwebui-importer:latest `
  python create_sql.py /data/output/chatgpt --tags="imported-chatgpt" --output=/data/chatgpt.sql
```

Full example for GPT, AI Studio, Grok and Claude:

```
python ./convert_chatgpt.py --userid="example-9cef-4387-8ee4-b82eb2e1c637" ./chatgpt.json
python ./convert_aistudio.py --userid="example-9cef-4387-8ee4-b82eb2e1c637" ./aistudio_example.json
python ./convert_grok.py --userid="example-9cef-4387-8ee4-b82eb2e1c637" ./grok.json
python ./convert_claude.py --userid="example-9cef-4387-8ee4-b82eb2e1c637" ./claude_example.json
python ./create_sql.py ./output/chatgpt --tags="imported-chatgpt" --output=chatgpt.sql
python ./create_sql.py ./output/aistudio --tags="imported-aistudio" --output=aistudio.sql
python ./create_sql.py ./output/grok --tags="imported-grok" --output=grok.sql
python ./create_sql.py ./output/claude --tags="imported-claude" --output=claude.sql
# Now run the scripts inside DB Browser and hit save
```

Example for Openrouter:

```
python ./convert_openrouter.py --userid="get-this-from-your-webui.db" ./openrouter.json

# The output file output/openrouter/openrouter_import.json can be imported directly
# via Open-WebUI: Settings → Data → Import Chat History.
```

## Scripts

Install the required Python dependencies first:

```bash
pip install -r requirements.txt
```

### convert_chatgpt.py

```
usage: convert_chatgpt.py [-h] --userid USERID [--output-dir OUTPUT_DIR] files [files ...]

Convert ChatGPT exports to open-webui JSON
```

### convert_grok.py

```
usage: convert_grok.py [-h] --userid USERID [--output-dir OUTPUT_DIR] files [files ...]

Convert Grok exports to open-webui JSON
```

### convert_claude.py

```
usage: convert_claude.py [-h] --userid USERID [--output-dir OUTPUT_DIR] files [files ...]

Convert Claude exports to open-webui JSON
```

### convert_aistudio.py

```
usage: convert_aistudio.py [-h] --userid USERID [--output-dir OUTPUT_DIR] files [files ...]

Convert AI Studio exports to open-webui JSON
```

### convert_openrouter.py

```
usage: convert_openrouter.py [-h] --userid USERID [--output-dir OUTPUT_DIR] files [files ...]

Convert Openrouter exports to open-webui JSON
```

All converter scripts name the output files using the original conversation ID
so running them again will produce the same filename for the same conversation.
Converted files are saved in a subdirectory named after the model (for example
`output/grok` or `output/claude`).

### create_sql.py

```
usage: create_sql.py [-h] [--tags TAGS] [--output OUTPUT] files [files ...]

Create SQL inserts for open-webui chats. Existing chat records are deleted
before inserting so they are replaced if already present. Tags are inserted
with UPSERT statements, ensuring the default import tags (and any tags passed
via `--tags`) exist for each user.

positional arguments:
  files            Chat JSON files or directories

options:
  -h, --help       show this help message and exit
  --tags TAGS      Comma-separated tags for the meta field
  --output OUTPUT  Write SQL statements to this file
```

### run_batch.py (Helper Script)

```
usage: run_batch.py [-h] --input-dir INPUT_DIR --type {aistudio,chatgpt,claude,grok} --user-id USER_ID [--output-dir OUTPUT_DIR] [--sql-output SQL_OUTPUT]

Batch process chat exports and generate SQL for Open WebUI.

options:
  -h, --help            show this help message and exit
  --input-dir INPUT_DIR
                        Directory containing the source chat files
  --type {aistudio,chatgpt,claude,grok}
                        Source chat format
  --user-id USER_ID     Open WebUI User ID to assign to these chats
  --output-dir OUTPUT_DIR
                        Directory for intermediate JSON files (default: output)
  --sql-output SQL_OUTPUT
                        Path to the final SQL file. If not specified, SQL generation is skipped.
```

Example:
```bash
python scripts/run_batch.py --input-dir ./my_chats --type aistudio --user-id "your-user-id" --sql-output aistudio_import.sql
```
This will convert all `.json` (and extensionless files for AI Studio) in `./my_chats` and generate `aistudio_import.sql`.

## Example workflow

1. Create an export from AI Studio (Gemini), Claude, ChatGPT or Grok. For
   Claude: Settings → Account → Export data, from claude.ai — the export
   arrives by email as a zip containing `conversations.json`.
2. Unzip the archive and locate the JSON file (for Grok this is
   `prod-grok-backend.json`; for Claude, `conversations.json`).
3. Look up your Open WebUI user ID if you haven't already — see
   ["Finding your Open WebUI user ID"](#finding-your-open-webui-user-id)
   above.
4. Convert the export to open-webui JSON using the appropriate script.
   For Grok:
   ```bash
   python ./convert_grok.py --userid="d95194d2-9cef-4387-8ee4-b82eb2e1c637" ./grok.json
   ```
   For Claude:
   ```bash
   python ./convert_claude.py --userid="d95194d2-9cef-4387-8ee4-b82eb2e1c637" ./conversations.json
   ```
   The converter writes one JSON file per conversation to a subdirectory
   named after the source — `output/grok` or `output/claude`.
5. Generate SQL statements from the converted JSON files:
   ```bash
   python ./create_sql.py ./output/claude --tags="imported-claude" --output=claude.sql
   ```
   The resulting SQL removes any existing chats with the same IDs before
   inserting new ones, while tags are inserted using UPSERTs so they are
   updated if they already exist. Any tags passed with `--tags` are also created
   for each user.
6. Make a copy of your `webui.db` database, and stop the Open WebUI
   container before the next step — see the caution in ["Finding your
   Open WebUI user ID"](#finding-your-open-webui-user-id) above.
7. Execute the generated SQL using a tool such as [DB Browser for SQLite](https://sqlitebrowser.org/dl/). Ensure you save the database, then start Open WebUI back up.
