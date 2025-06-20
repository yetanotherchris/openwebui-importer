# openwebui-importer
Import Grok, Claude, ChatGPT chats into open-webui.

## Listing Chat Titles

Use `list_titles.py` to detect the format of a chat export and print
all conversation titles. By default each title is prefixed with its
timestamp in a human readable form:

```bash
python list_titles.py <export.json> [more.json ...]
```

The script supports Grok, Claude, and ChatGPT exports and will report
the detected format for each file before listing its titles. Detection
normally relies on quick heuristics. Pass `--validate` to enforce JSON
schema validation which is slower. If you already know the export
format you can pass `--format Grok`, `--format ChatGPT`, or
`--format Claude` to skip detection. Titles are shown with their
timestamps unless you pass `--no-dates`.

The script depends on the `jsonschema` package. Install the required
dependencies with:

```bash
pip install -r requirements.txt
```
