# openwebui-importer

Import Grok, Claude and ChatGPT chats into [open-webui](https://github.com/open-webui/open-webui).

Install the required Python dependencies first:

```bash
pip install -r requirements.txt
```

## Scripts


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

### create_sql.py

```
usage: create_sql.py [-h] [--tags TAGS] [--output OUTPUT] files [files ...]

Create SQL inserts for open-webui chats

positional arguments:
  files            Chat JSON files or directories

options:
  -h, --help       show this help message and exit
  --tags TAGS      Comma-separated tags for the meta field
  --output OUTPUT  Write SQL statements to this file
```

### create-schema.py

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
4. Generate SQL statements from the converted JSON files:
   ```bash
   python ./create_sql.py ./output --tags="imported, grok" --output=grok.sql
   ```
5. Make a copy of your `webui.db` database.
6. Execute the generated SQL using a tool such as [DB Browser for SQLite](https://sqlitebrowser.org/dl/).
