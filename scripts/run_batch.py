#!/usr/bin/env python3
"""Batch process chat exports and generate SQL."""

import argparse
import os
import subprocess
import sys

def run_command(command, description):
    print(f"--- {description} ---")
    print(f"Running: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error during {description}:", file=sys.stderr)
        print(e.stdout)
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Batch process chat exports and generate SQL for Open WebUI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python scripts/run_batch.py --input-dir ./chats/gpt --type chatgpt --user-id "my-user-id"
  python scripts/run_batch.py --input-dir ./chats/gemini --type aistudio --user-id "uuid-123" --sql-output gemini_chats.sql
        """
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing the source chat files")
    parser.add_argument("--type", required=True, choices=["aistudio", "chatgpt", "claude", "grok"], help="Source chat format")
    parser.add_argument("--user-id", required=True, help="Open WebUI User ID to assign to these chats")
    parser.add_argument("--output-dir", default="output", help="Directory for intermediate JSON files (default: output)")
    parser.add_argument("--sql-output", help="Path to the final SQL file. If not specified, SQL generation is skipped.")
    
    args = parser.parse_args()
    
    # Resolve absolute paths
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    
    # 1. Determine the converter script
    converter = f"convert_{args.type}.py"
    converter_path = os.path.join(root_dir, converter)
    
    if not os.path.exists(converter_path):
        print(f"Error: Converter script {converter} not found in {root_dir}.", file=sys.stderr)
        sys.exit(1)
        
    # 2. Collect files to convert
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory {input_dir} does not exist.", file=sys.stderr)
        sys.exit(1)
        
    files = []
    for f in os.listdir(input_dir):
        path = os.path.join(input_dir, f)
        if not os.path.isfile(path):
            continue
            
        _, ext = os.path.splitext(f)
        if ext.lower() == '.json':
            files.append(path)
        elif args.type == 'aistudio' and ext == '':
            files.append(path)

    if not files:
        msg = "No .json files found"
        if args.type == 'aistudio':
            msg = "No .json or extensionless files found"
        print(f"{msg} in {input_dir}")
        sys.exit(0)
        
    # 3. Run conversion
    conv_cmd = [sys.executable, converter_path, "--userid", args.user_id, "--output-dir", output_dir] + files
    run_command(conv_cmd, f"Converting {args.type} chats")
    
    # 4. Generate SQL (optional)
    if args.sql_output:
        # The converters put files in output/<type>/
        json_dir = os.path.join(output_dir, args.type)
        if not os.path.exists(json_dir):
            # Fallback to output dir if type-specific subdir wasn't created
            json_dir = output_dir

        sql_script = os.path.join(root_dir, "create_sql.py")
        sql_file_path = os.path.abspath(args.sql_output)
        
        sql_cmd = [sys.executable, sql_script, json_dir, "--output", sql_file_path, "--tags", f"imported-{args.type}"]
        run_command(sql_cmd, "Generating SQL statements")
        
        print(f"\n✨ Success! Generated SQL: {sql_file_path}")
    else:
        print("\nSkipping SQL generation (no --sql-output provided).")

if __name__ == "__main__":
    main()
