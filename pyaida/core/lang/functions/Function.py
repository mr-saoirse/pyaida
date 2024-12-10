from pydantic import BaseModel
import typing
class FunctionCall(BaseModel):
    name: str
    arguments: str | dict

class Function:
    """for this to be useful it should wrap and convert the json string and also provide a calling proxy to invoke the function
       Agent instances and API proxies
       The function manager can manage them as a context and this can be a convenient shell to move things around in
    """
    
    def __init__(self, spec:dict, proxy:typing.Any, fn:typing.Callable = None, name_prefix:str = None):
        self.proxy = proxy
        self.spec = spec
        self.fn = fn
        self.name_prefix = name_prefix
    
    def to_json_spec(self):
        """"""
        pass
    
    def __call__(cls, **kwargs):
        """
        call the function with either a proxy or the function instance container (in that order of precedence)
        """  
        if cls.proxy:
            """the json schema title is the function name?"""
            fn = cls.proxy.getattr(cls.spec.get('title'))
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
    