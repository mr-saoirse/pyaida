from pydantic import BaseModel, create_model, Field
from typing import Any, Dict, Type, Union
from pyaida.core.data import AbstractModel

def resolve_ref(schema: Dict[str, Any], ref: str) -> Dict[str, Any]:
    """Resolve $ref to its definition in the schema."""
    ref_path = ref.lstrip("#/").split("/")
    resolved = schema
    for part in ref_path:
        resolved = resolved.get(part, {})
    return resolved

def get_pydantic_model_fields_from_json_schema(schema: Dict[str, Any], 
                         definitions: Dict[str, Any] = None) -> Type[BaseModel]:
    """
    Recursively generate Pydantic models from a JSON Schema.
    the model schema also contains the model name and description would we could use but we tender to save that elsewhere for search
    Also it east to pull out of the schema
    """
    if definitions is None:
        definitions = schema.get("definitions", {})

    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    model_fields = {}
    for field_name, field_info in properties.items():
        if "$ref" in field_info:
            ref_schema = resolve_ref({"definitions": definitions}, field_info["$ref"])
            sub_model = get_pydantic_model_fields_from_json_schema(ref_schema, definitions, name=field_name.capitalize())
            field_type = sub_model
        elif field_info.get("type") == "object":
            # Handle nested object
            field_type = get_pydantic_model_fields_from_json_schema(field_info, definitions, name=field_name.capitalize())
        elif field_info.get("type") == "array":
            # Handle arrays (assumes single-type arrays)
            items = field_info.get("items", {})
            if "$ref" in items:
                ref_schema = resolve_ref({"definitions": definitions}, items["$ref"])
                field_type = list[get_pydantic_model_fields_from_json_schema(ref_schema, definitions, name=field_name.capitalize())]
            else:
                field_type = list
        else:
            # Map simple types - TODO extend cases
            field_type = {
                "string": str,
                "integer": int,
                "boolean": bool,
                "number": float,
                "array": list,
                "object": dict,
            }.get(field_info.get("type"), Any)

        description = field_info.get("description", None)
        extras = {}
        
        """could do this for all pyaida extras"""
        if field_info.get('embedding_provider'):
            extras = {'embedding_provider':field_info.get('embedding_provider')}

        model_fields[field_name] = (field_type, Field(... if field_name in required_fields else None, description=description, **extras))
        

    return model_fields