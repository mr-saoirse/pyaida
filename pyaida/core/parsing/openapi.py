import yaml
import json
import os
import requests

class OpenApiSpec:
    """
    The spec object parses endpoints into function descriptions
    """
    def __init__(self, uri_or_spec):
        """supply a spec object (dict) or a uri to one"""
        self._uri_str = ""
        if isinstance(uri_or_spec,str):
            self._uri_str = uri_or_spec
            if uri_or_spec[:4].lower() == 'http':
                uri_or_spec = requests.get(uri_or_spec)
                if uri_or_spec.status_code == 200:
                    uri_or_spec = uri_or_spec.json()
                else:
                    raise Exception(f"unable to fetch {uri_or_spec}")
            else:
                with open(uri_or_spec, "r") as file:
                    uri_or_spec = yaml.safe_load(file)
                    
        if not isinstance(uri_or_spec,dict):
            raise ValueError("Unable to map input to spec. Ensure spec is a spec object or a uri pointing to one")
        
        self.spec = uri_or_spec
        
        """lookup"""
        self._endpoint_methods = {op_id: (endpoint,method) for op_id, endpoint, method in self}

    def __repr__(self):
        """
        """
        return f"OpenApiSpec({self._uri_str})"
    
    def get_operation_spec(self, operation_id):
        """return the spec for this function given an endpoint operation id"""
        endpoint, verb = self._endpoint_methods[operation_id]
        return self.spec['paths'][endpoint][verb]
            
    def get_endpoint_method(self, op_id):
        return self._endpoint_methods.get(op_id)
    
    def resolve_ref(self, ref: str):
        """Resolve a $ref to its full JSON schema."""
        parts = ref.lstrip("#/").split("/")
        resolved = self.spec
        for part in parts:
            resolved = resolved[part]
        return resolved

    def __iter__(self):
        """iterate the endpoints with operation id, method, endpoint"""
        for endpoint, grp in self.spec['paths'].items():
            for method, s in grp.items():
                op_id = s.get('operationId')
                yield op_id, endpoint, method

    def get_expanded_schema(self):
        """expand the lot map to operation id"""
        return {operation_id: self.get_expanded_schema_for_endpoint(endpoint, method)   
                for operation_id, endpoint, method in self}
            
    def get_expanded_schema_for_endpoint(self, endpoint: str, method: str):
        """Retrieve the expanded JSON schema for a given endpoint and HTTP method."""
        parameters = []
        request_body = None
        spec = self.spec
        
        method_spec = spec["paths"].get(endpoint, {}).get(method, {})

        # Process query/path/header parameters
        for param in method_spec.get("parameters", []):
            param_schema = param.get("schema", {})
            if "$ref" in param_schema:
                param_schema = self.resolve_ref(param_schema["$ref"])
            parameters.append({
                "name": param["name"],
                "in": param["in"],
                "description": param.get("description", ""),
                "schema": param_schema
            })

        # Process requestBody (e.g., for POST requests)
        if "requestBody" in method_spec:
            content = method_spec["requestBody"].get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema", {})
                if "$ref" in schema:
                    schema = self.resolve_ref(schema["$ref"])
                request_body = schema

        return {"parameters": parameters, "request_body": request_body}
    
   