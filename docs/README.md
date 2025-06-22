# openwebui-importer

**Import Grok, Claude and ChatGPT chats into [open-webui](https://github.com/open-webui/open-webui).**

This importer tool has two Python scripts: one for converting the model JSON files to openweb-ui format JSON, the second for 
creating a SQL script to import the JSON into the openweb-ui SQLite database.  

The imported chats are given the tags `imported-chatgpt`, `imported-claude` and `imported-grok`.

Any private-use Unicode characters occasionally found in model exports are stripped from the message text during conversion.

*There were problems exporting chats from Gemini, so it's not currently supported. DeepSeek and others could be added without much effort.*

## Quick start

```
python .\convert_chatgpt.py --userid="get-this-from-your-webui.db" .\chatgpt.json   
python .\create_sql.py ./output/chatgpt --tags="imported-chatgpt" --output=chatgpt.sql
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

### create-schema.py
JSON schemas were originally used with the Model's export JSON. This script and the schemas are kept for reference.

```
Usage: python json_schema_generator.py <input_json_file>
Output will be saved as <input_file>_schema.json
```

## Example workflow

1. Create an export from Claude, ChatGPT or Grok.
2. Unzip the archive and locate the JSON file (for Grok this is `prod-grok-backend.json`).
3. Convert the export to open-webui JSON using the appropriate script:
   ```bash
   python ./convert_grok.py --userid="d95194d2-9cef-4387-8ee4-b82eb2e1c637" ./grok.json
   ```
   The converter writes JSON files to a subdirectory such as `output/grok`.
4. Generate SQL statements from the converted JSON files:
   ```bash
   python ./create_sql.py ./output --tags="imported-grok" --output=grok.sql
   ```
   The resulting SQL removes any existing chats with the same IDs before
   inserting new ones, while tags are inserted using UPSERTs so they are
   updated if they already exist. Any tags passed with `--tags` are also created
   for each user.
5. Make a copy of your `webui.db` database.
6. Execute the generated SQL using a tool such as [DB Browser for SQLite](https://sqlitebrowser.org/dl/). Ensure you save the database.
