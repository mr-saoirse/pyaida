from pydantic import BaseModel
import typing
from pyaida.core.utils import inspection, short_md5_hash
from pyaida.core.data.AbstractModel import AbstractEntityModel
import uuid


class FunctionModel(AbstractEntityModel):
    class Config:
        namespace: str = "public"
        
    name: str
    key: str
    spec: dict
    group_id: typing.Optional[str] = None

    @classmethod
    def from_spec(cls, spec, group:str= None):
        """convenience to save from an in memory function"""
        key = spec['title'] if not group else f"{group}.{spec['title']}"
        id_md5_uuid =  uuid.uuid3(uuid.NAMESPACE_DNS, key)   
        return cls(id=id_md5_uuid, 
                   name=spec['title'], 
                   key= key,
                   group=group,
                   spec=spec, 
                   description=spec['description'] )
            
    @classmethod
    def from_function(cls, fn, group:str= None):
        """convenience to save from an in memory function"""
        _fn = Function.from_function(fn)
        spec = _fn.to_json_spec()
        key =  _fn.hashed_qualified_name if not group else f"{group}.{_fn.hashed_qualified_name}"
        id_md5_uuid =  uuid.uuid3(uuid.NAMESPACE_DNS, _fn.name)   
        return cls(id=id_md5_uuid, 
                   name = _fn.name, 
                   key  = key, 
                   group=group,
                   spec=spec, 
                   description=spec['description'] )

class _OpenAIFunctionParametersModel(BaseModel):
    properties: typing.Optional[dict] = {}
    type: typing.Optional[str] = 'object'
class _OpenAIFunctionModel(BaseModel):
    name: str
    description: str
    parameters: typing.Optional[_OpenAIFunctionParametersModel] = None

class FunctionCall(BaseModel):
    name: str
    arguments: str | dict

class Function:
    """for this to be useful it should wrap and convert the json string and also provide a calling proxy to invoke the function
       Agent instances and API proxies
       The function manager can manage them as a context and this can be a convenient shell to move things around in
    """
    
    def __init__(self, spec:dict, proxy:typing.Any =None, fn:typing.Callable = None, name_prefix:str = None):
        self.proxy = proxy
        self.spec = spec
        
        """todo - validate spec to some normed forma but provide specific dump later"""
        for k, v in {'summary':'description', 'operationId': 'title'}.items():
            if k in self.spec:
                self.spec[v] = self.spec.pop(k) 
            
        self.fn = fn
        self.name_prefix = name_prefix
    
    @property
    def name(self):
        return (self.spec or {}).get('title')
    
    @property
    def qualifier(self):
        """the qualifier makes functions globally unique"""
        if self.name_prefix:
            return self.name_prefix
        if self.proxy:
            return self.proxy.id
        if self.fn and hasattr(self.fn, '__self__'):
            return inspection.object_name(self.fn.__self__)
    
    @property
    def qualified_name(self):
        """get a globally unique name for the function"""
        return f"{self.qualifier}.{self.name}" if self.qualifier else self.name
    
    @property
    def hashed_qualified_name(self):
        """get a globally unique name for the function"""
        q = None
        if self.qualifier:
            """add friendly parent to the end of the hash"""
            q = self.qualifier.split('.')[-1].split('_')[-1]
            
        return f"{short_md5_hash(self.qualifier, 5)}_{q}_{self.name}" if q else self.name
    
    def to_json_spec(self, qualified:bool = True, provider:str=None, **kwargs):
        """
        returns the spec but can transform it in some ways
        - for open ai we take our function object and promote some of the properties to a top level
        
        OpenAI
        
        ```Example
           
            {
                "name": "get_delivery_date",
                "description": "Get the delivery date for a customer's order. Call this whenever you need to know the delivery date, for example when a customer asks 'Where is my package'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The customer's order ID."
                        }
                    },
                    "required": ["order_id"],
                    "additionalProperties": false
                }
            }
    
            
        ```
        """
        s = dict(self.spec)
        if qualified:
            """we want globally unique names that are also respecting constraints of name length"""
            s['title'] = self.hashed_qualified_name
        
        assert len(s['title']) < 64, f"The name {s['title']} is too long (>63)"
        
        """we take the function object spec and generate a function spec"""
        name = s.pop('title')
        description = s.pop('description')
        return _OpenAIFunctionModel(**{  'name': name, 'description' : description, 'parameters': s }).model_dump()
        
    
    def __call__(cls, **kwargs):
        """
        call the function with either a proxy or the function instance container (in that order of precedence)
        """  
        if cls.proxy:
            """the json schema title is the function name?"""
            fn = getattr(cls.proxy, cls.spec.get('title'),None)
            assert fn is not None, f"The function {cls.spec.get('title')} was not found on {cls.proxy=}"
            return fn(**kwargs)
        if cls.fn:
            return cls.fn(**kwargs)
        raise ValueError("You must provide either a callable function or a proxy to resolve the function from the spec")
    
    @classmethod
    def from_function(cls, fn: typing.Callable, proxy: typing.Any=None, name_prefix:str=None):
        """create a function from a callable function"""
        from pyaida.core.data import AbstractModel
        """this this works in all cases that i mean"""
 
        fn_model = AbstractModel.create_model_from_function(fn, name_prefix = name_prefix)
        
        """if you know the proxy you can use it but normally you would not - relay the name prefix in case it causes confusion"""
        return cls(fn_model.model_json_schema(), proxy, fn=fn, name_prefix=name_prefix)
    