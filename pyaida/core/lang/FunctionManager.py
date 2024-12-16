import typing
import os
import json
from pyaida.core.data import AbstractModel
from pyaida.core.lang.functions.Function import Function
from pyaida.core.lang.messages import MessageStack
from pyaida.core.lang.models import CallingContext, language_model_client_from_context, LanguageModel
from functools import partial
from pyaida.core.lang.PlanModel import Plan
from pyaida.core.utils import logger
 
class FunctionLoadException(Exception):
    pass
class ApiProxy:
    def __init__(self, uri:str=None, token_key:str=None, spec_file : str= "openapi.json"):
        """
        the uri is the unique url for the endpoint and the token key is an env var that loads any token for this endpoint
        this should be cached because we load the metadata each time its constructed.
        for example the function manager could load proxies the first time it sees them
        """
        from pyaida.core.parsing.openapi import OpenApiSpec
        self.uri = uri
        self.token_key = token_key
        self.endpoints = None
        if not self.uri:
            self.uri = os.environ.get('PYAIDA_API_URI', 'http://127.0.0.1:8002')
        try:
            self.openapi = OpenApiSpec(f"{self.uri}/{spec_file}")
            self.endpoints = self.openapi._endpoint_methods
        except Exception as ex:
            logger.warning(f"Failed to load the default API proxy json - may have trouble calling some default endpoint")
        
    def invoke_function(self, spec_or_id:str|dict, data=None,  **kwargs):
        """
        supply a spec or operation id for a function for example a get endpoint
        """
        if isinstance(spec_or_id,dict):
            """conventionally the name op id the unqualified name"""
            spec_or_id = spec_or_id.get('name').split('.')[-1]
            
        return self._invoke(op_id=spec_or_id, data=data, **kwargs)
            
    def __getattr__(self, name):
        
        """Custom attribute access logic."""
     
        try:
            return super().__getattribute__(name)
        except AttributeError:
            if name in self.endpoints:
                spec = self.openapi.get_operation_spec(name)
                return Function(spec=spec, fn=partial(self._invoke, op_id=name))
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        
    def _invoke(self, *args, op_id:str|dict, data=None, return_raw_response:bool=False, full_detail_on_error: bool = False, **kwargs):
        """call the endpoint assuming json output for now"""
        
        """the response does not have to be json - just for testing"""
        
        import requests
        
        headers = { } #"Content-type": "application/json"
        if self.token_key:
            headers["Authorization"] =  f"Bearer {os.environ.get(self.token_key)}"
        
        """decompose"""
        endpoint, verb = self.openapi.get_endpoint_method(op_id)
        f = getattr(requests, verb)
        """rewrite the url with the kwargs"""
        endpoint = endpoint.format_map(kwargs)
        endpoint = f"{self.uri.rstrip('/')}/{endpoint.lstrip('/')}"

        if data is None: #callers dont necessarily know about data and may pass kwargs
            data = kwargs
        if data and not isinstance(data,str):
            """support for passing pydantic models"""
            if hasattr(data, 'model_dump'):
                data = data.model_dump()
            data = json.dumps(data)

        """f is verified - we just need the endpoint. data is optional, kwargs are used properly"""
        response = f(
            endpoint,
            headers=headers,
            params=kwargs,
            data=data,
        )

        try:
            response.raise_for_status()

            if return_raw_response:
                return response
        
            """otherwise we try to be clever"""
            t = response.headers.get('Content-Type') or "text" #text assumed
            if 'json' in t:
                return  response.json()
            if t[:5] == 'image':
                from PIL import Image
                from io import BytesIO
                return Image.open(BytesIO(response.content))
            content = response.content
            return content.decode() if isinstance(content,bytes) else content
                        
            
        except Exception as ex:
        
 
            if not full_detail_on_error:
                """raise so runner can do its thing"""
                raise Exception(json.dumps(response.json())) 
            return {
                "data": response.json(),
                "type": response.headers.get("Content-Type"),
                "status": response.status_code,
                "requested_endpoint": endpoint,
                "info": self.model_dump(),
                "exception" : repr(ex)
            }

class FunctionManager:
    """Function manager for searching and proxying function calls
    """

    def __init__(self):
        """some options such as models or data stores to use for function loading"""
        self._functions: typing.Dict[str, Function] = {}
        
        """setup the default proxy object for apis that are not qualified"""
        self.proxy = ApiProxy()
        
    def __getitem__(self, key):
        return self._functions.get(key)

    def __setitem__(self, key, value):
        self._functions[key] = value

    def _get_proxy_by_id(self, id:str):
        """get the proxy by id
        - if the id is http:// then its assumed an API url
        - otherwise its assumed an object in the codebase
        
        Args:
            id: uri - unique object ref - a http:// api root or an object id using the object model syntax namespace.Name
        """
        
        if id[:4] == 'http':
            raise NotImplementedError('Todo create a singleton to register third party apis')
        from pyaida.core.utils.inspection import load_model
        return load_model(id)

    def register(self, model: AbstractModel)->typing.List[Function]:
        """Register model functions

        Args:
            model (AbstractModel): a model that describes the resources and objectives of an agent
        """
        if not model:
            return
        added_functions = []
        for f in model.get_public_class_and_instance_methods():
            added_functions.append(self.add_function(f))
        return added_functions

    def add_function(self, f: typing.Callable | "Function"):
        """Add a callable function to the runtime

        Args:
            f (typing.Callable|Function): the callable function or function descriptor to add to available functions
        """

        if not isinstance(f, Function) and callable(f):
            f = Function.from_function(f)

        self[f.hashed_qualified_name] = f

        return f


    def add_functions_by_key(self, function_keys: str | typing.List[str]):
        """functions are loaded by their unique key from some proxy
           - the format for the key is object_id.function_name
           - the object_id can take the form namespace.name and refer to an entity name or an api proxy
           - if the function key is not qualified we will use the default API proxy
        """
        
        if function_keys is None:
            raise ValueError("You must pass one or more function keys of the form object_id.function_name to the function_keys parameter")
        if isinstance(function_keys,str):
            function_keys = [function_keys]
            
        def _add_function(k):
            if k in self._functions:
                return self._functions[k]
            proxy_id = None
            function_name = k
            if "." in k:
                proxy_id, delim, function_name = k.rpartition(".")
    
            """proxies provide special functions e.g calling api endpoints but also providing the metadata
               a proxy can also be a runtime loaded object - runtime objects provide annotated functions that can also be turned into Function objects
               Function objects are simply metadata and callables
            """
            proxy = self._get_proxy_by_id(proxy_id) if proxy_id else self.proxy
            
            if not proxy:
                raise FunctionLoadException(f"There is no proxy to load the function `{k}` using proxy {proxy}({proxy_id})")
            fn = getattr(proxy,function_name,None)
            if fn is None:
                raise FunctionLoadException(f"Proxy cannot load function `{k}` - using proxy {proxy}({proxy_id}) - check the function name exists on the object or that operation id exists on the API")
            if not isinstance(fn, Function) and callable(fn):
                """we can load a function that is reference on some proxy object"""
                fn = Function.from_function(fn)
            self._functions[k] =  fn
            return fn
            
        return [_add_function(k) for k in function_keys]
        

    def reset_functions(self):
        """hard reset on what we know about"""
        self.functions = {}

    def search(self, question: str, limit: int = None, context: CallingContext = None):
        """search a deep function registry (API). The plan could be used to hold many functions in an in-memory/in-context registry.
        This as cost implications as the model must keep all functions in the context.
        On the other hand, a vector search can load functions that might be interesting but it may not be accurate or optimal

        Args:
            question (str): a query/prompt to search functions (using a vector search over function embeddings)
            limit: (int): a limit of functions returned for consideration
            context (CallingContext, optional): context may provide options
        """

        return pg.repository(Plan).ask(question)

        # may add tenacity retries for formatting
    def plan(self, question: str, context: CallingContext = None, strict: bool = False):
        """Given a question, use the known functions to construct a function calling plan (DAG)

        Args:
            question (str): any prompt/question
            context (CallingContext, optional): calling context may be used e.g. to choose the underlying model
        """

        """determine the model from context or default"""
 
        lm_client: LanguageModel = language_model_client_from_context(context)

        """there are no functions in this context as we want a direct response from context"""
        functions = None

        # example not just of response model but add functions/prompts with the model
        """we can structure the messages from the question and typed model"""
        messages = MessageStack(
            question=question, model=Plan, language_model_provider=context.model if context else None
        )
        
        if not context:
            context = CallingContext(prefer_json=True)
    
        response = lm_client(messages=messages, functions=functions, context=context)
        if strict:
            response: Plan = Plan.model_validate_json(response)
        return response


    @property
    def functions(self) -> typing.Dict[str, Function]:
        """provides a map of functions"""
        return self._functions

""""""