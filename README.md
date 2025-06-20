# openwebui-importer
Import Grok, Claude, ChatGPT chats into open-webui.

## Listing Chat Titles

Use `list_titles.py` to detect the format of a chat export and print
all conversation titles:

```bash
python list_titles.py <export.json> [more.json ...]
```

The script supports Grok, Claude, and ChatGPT exports and will report
the detected format for each file before listing its titles.
