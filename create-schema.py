#!/usr/bin/env python3
"""
JSON Schema Generator

This script reads a JSON file and generates a corresponding JSON Schema.
It analyzes the structure and data types to create a comprehensive schema.
"""

import json
import sys
from typing import Any, Dict, List, Union
from collections import defaultdict


def infer_type(value: Any) -> str:
    """Infer the JSON Schema type from a Python value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return "string"  # fallback


def analyze_array(arr: List[Any]) -> Dict[str, Any]:
    """Analyze an array to determine item types and constraints."""
    if not arr:
        return {"type": "array", "items": {}}
    
    # Collect all types found in the array
    item_types = set()
    item_schemas = []
    
    for item in arr:
        item_type = infer_type(item)
        item_types.add(item_type)
        
        if item_type == "object":
            item_schemas.append(generate_schema_from_value(item))
        elif item_type == "array":
            item_schemas.append(analyze_array(item))
        else:
            item_schemas.append({"type": item_type})
    
    # If all items have the same type, use that type
    if len(item_types) == 1:
        item_type = list(item_types)[0]
        if item_type == "object" and item_schemas:
            # Merge object schemas
            merged_schema = merge_object_schemas(item_schemas)
            return {
                "type": "array",
                "items": merged_schema,
                "minItems": 0
            }
        elif item_type == "array" and item_schemas:
            # Use the first array schema as template
            return {
                "type": "array",
                "items": item_schemas[0],
                "minItems": 0
            }
        else:
            return {
                "type": "array",
                "items": {"type": item_type},
                "minItems": 0
            }
    else:
        # Mixed types - use anyOf
        unique_schemas = []
        seen_schemas = set()
        for schema in item_schemas:
            schema_str = json.dumps(schema, sort_keys=True)
            if schema_str not in seen_schemas:
                seen_schemas.add(schema_str)
                unique_schemas.append(schema)
        
        return {
            "type": "array",
            "items": {"anyOf": unique_schemas} if len(unique_schemas) > 1 else unique_schemas[0],
            "minItems": 0
        }


def merge_object_schemas(schemas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple object schemas into one, combining properties."""
    if not schemas:
        return {"type": "object"}
    
    if len(schemas) == 1:
        return schemas[0]
    
    merged_properties = {}
    all_required = set()
    
    # Collect all properties and their schemas
    property_schemas = defaultdict(list)
    
    for schema in schemas:
        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                property_schemas[prop_name].append(prop_schema)
        
        if "required" in schema:
            all_required.update(schema["required"])
    
    # Merge properties
    for prop_name, prop_schema_list in property_schemas.items():
        if len(prop_schema_list) == 1:
            merged_properties[prop_name] = prop_schema_list[0]
        else:
            # Check if all schemas are the same
            if all(json.dumps(s, sort_keys=True) == json.dumps(prop_schema_list[0], sort_keys=True) 
                   for s in prop_schema_list):
                merged_properties[prop_name] = prop_schema_list[0]
            else:
                # Different schemas - use anyOf
                merged_properties[prop_name] = {"anyOf": prop_schema_list}
    
    # Only mark as required if property appears in ALL schemas
    required_props = []
    for prop_name in merged_properties:
        if all(prop_name in schema.get("properties", {}) for schema in schemas):
            # Check if it's required in all schemas that have it
            required_in_all = all(
                prop_name in schema.get("required", []) 
                for schema in schemas 
                if prop_name in schema.get("properties", {})
            )
            if required_in_all:
                required_props.append(prop_name)
    
    result = {
        "type": "object",
        "properties": merged_properties
    }
    
    if required_props:
        result["required"] = sorted(required_props)
    
    return result


def generate_schema_from_value(data: Any) -> Dict[str, Any]:
    """Generate a JSON schema from a Python value."""
    data_type = infer_type(data)
    
    if data_type == "null":
        return {"type": "null"}
    
    elif data_type in ["boolean", "integer", "number", "string"]:
        schema = {"type": data_type}
        
        # Add constraints for strings
        if data_type == "string" and data:
            schema["minLength"] = 1
        
        return schema
    
    elif data_type == "array":
        return analyze_array(data)
    
    elif data_type == "object":
        properties = {}
        required = []
        
        for key, value in data.items():
            properties[key] = generate_schema_from_value(value)
            # Consider non-null values as required
            if value is not None:
                required.append(key)
        
        schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = sorted(required)
        
        return schema
    
    return {"type": "string"}  # fallback


def generate_json_schema(json_data: Any, title: str = "Generated Schema") -> Dict[str, Any]:
    """Generate a complete JSON Schema from JSON data."""
    schema = generate_schema_from_value(json_data)
    
    # Add schema metadata
    complete_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.com/schema.json",
        "title": title,
        "description": f"Schema generated from JSON data",
        **schema
    }
    
    return complete_schema


def main():
    """Main function to handle command line arguments and file processing."""
    if len(sys.argv) != 2:
        print("Usage: python json_schema_generator.py <input_json_file>")
        print("Output will be saved as <input_file>_schema.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    try:
        # Read the input JSON file
        with open(input_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Generate the schema
        schema = generate_json_schema(json_data, title=f"Schema for {input_file}")
        
        # Create output filename
        if input_file.endswith('.json'):
            output_file = input_file[:-5] + '_schema.json'
        else:
            output_file = input_file + '_schema.json'
        
        # Write the schema to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        
        print(f"✅ JSON Schema generated successfully!")
        print(f"📝 Input file: {input_file}")
        print(f"📄 Output file: {output_file}")
        
        # Also print the schema to stdout for quick viewing
        print("\n" + "="*50)
        print("Generated Schema:")
        print("="*50)
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        
    except FileNotFoundError:
        print(f"❌ Error: File '{input_file}' not found.")
        sys.exit(1)
    
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{input_file}': {e}")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()