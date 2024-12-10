from pydantic import BaseModel, create_model, Field
import typing
import docstring_parser
import inspect
from pydantic._internal._model_construction import ModelMetaclass
from pyaida.core.utils import inspection

DEFAULT_NAMESPACE = 'public'

def create_config(name:str, namespace:str, description:str, functions: typing.Optional[typing.List[dict]]):
    """generate config classes on dynamic instances"""
    def _create_config(class_name, *property_names):
        class_dict = {}
        for prop in property_names:
            class_dict[prop] = property(
                fget=lambda self, prop=prop: getattr(self, f'_{prop}', None),
                fset=lambda self, value, prop=prop: setattr(self, f'_{prop}', value)
            )
        return type(class_name, (object,), class_dict)


    Config = _create_config('Config', 'name', 'namespace', 'description', 'functions', 'is_abstract')
    Config.name = name
    Config.namespace = namespace
    Config.description = description
    Config.functions = functions
    Config.is_abstract = True
    
    return Config


class AbstractModel:
    """sys prompt"""
    
    """optional config - especially for run times"""
    
    @classmethod
    def create_model_from_function(cls, fn: typing.Callable, name_prefix: str=None)->"AbstractModel":
        """
        returns a model from the function
        this is useful to generate function defs to send to language model from the model_json_schema
        docstring parser library is used to parse args and description from docstring
        name_prefix is a qualifier that we can add if needed
        """
        
        def s_combine(*l):
            return "\n".join(i for i in l if i)

        """parse the docstring"""
        p = docstring_parser.parse(fn.__doc__)
        description = s_combine(
            p.short_description, p.long_description
        )
        parameter_descriptions = {p.arg_name: p.description for p in p.params}

        """make fields from typing and docstring"""
        signature = inspect.signature(fn)
        type_hints = typing.get_type_hints(fn)
        fields = {}
        for name, param in signature.parameters.items():
            if name == "self": 
                continue
            annotation = type_hints.get(name, typing.Any)
            default = param.default if param.default is not inspect.Parameter.empty else ...
            """add the desc from the doc sting args when creating the field"""
            field = Field(default=default, description=parameter_descriptions.get(name))
            fields[name] = (annotation, field)
        
        """create the function model"""
        name = fn.__name__ if not name else f"{name_prefix}_{fn.__name__}"
        return create_model(fn.__name__, __doc__= description, **fields)
    
    @classmethod
    def get_function_descriptions(cls, name_prefix: str=None):
        """get all the json schema definitions for inline function"""
        return [cls.create_model_from_function(fn, prefix=name_prefix).model_json_schema() 
                for fn in cls.get_public_class_and_instance_methods()]
    
    @classmethod
    def create_model(cls, name: str, namespace: str = None, description:str = None, functions:dict = None, fields = None, **kwargs):
        """
        For dynamic creation of models for the type systems
        create something that inherits from the class and add any extra fields
        
        Args:
            name: name of the model (only required prop)
            namespace: namespace for the model - types take python models or we can use public as default
            description: a markdown description of the model e.g. system prompt 
            functions: a map of function ids and how they are to be used on context
        """
        if not fields:
            fields = {}
        namespace = namespace or cls._get_namespace()
        model =  create_model(name, **fields, __module__=namespace, __base__=cls)
        
        """add the config object which is used in interface"""
        model.Config = create_config(name=name, 
                                     namespace=namespace,
                                     description=description,
                                     functions=functions or [])
        return model
    
    
    @classmethod
    def _try_config_attr(cls, name, default=None):
        if hasattr(cls, 'Config'):
            return getattr(cls.Config, name, default)
        
    @classmethod
    def _get_description(cls):
        return  cls._try_config_attr('description',cls.__doc__)
    
    @classmethod
    def _get_namespace(cls):
        namespace = cls.__module__.split(".")[-1]
        namespace = (
            namespace
            if namespace not in ["model", "__main__"]
            else DEFAULT_NAMESPACE
        )
        return cls._try_config_attr('namespace', default=namespace)
    
    @classmethod
    def _get_names(cls):
        s = cls.model_json_schema(by_alias=False)
        name = s.get("title", cls.__name__)
        return cls._try_config_attr('name', default=name)
    
    @classmethod
    def _get_external_functions(cls):
        return cls._try_config_attr('functions', default={})

    
    
    @classmethod
    def _get_system_prompt_markdown(cls, 
                                   include_external_functions:bool=True, 
                                   include_fields: bool = True, 
                                   include_date:bool=True) -> str:
        """
        
        """
        
        return ""
    
    @classmethod
    def get_public_class_and_instance_methods(cls):
        """returns the class and instances methods that are not private"""

        if not isinstance(cls, ModelMetaclass):
            cls = cls.__class__
            
        """any methods that are not on the abstract model are fair game"""
        methods = inspection.get_class_and_instance_methods(cls, inheriting_from=AbstractModel)

        """return everything but hide privates"""
        return [m for m in methods if not m.__name__[:1] == "_"]
    
    
class AbstractEntityModel(AbstractModel):
    pass