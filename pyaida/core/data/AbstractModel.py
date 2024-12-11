from pydantic import BaseModel, create_model, Field
import typing
import docstring_parser
import inspect
from pydantic._internal._model_construction import ModelMetaclass
from pyaida.core.utils import inspection
import uuid

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


class AbstractModel(BaseModel):
    """sys prompt"""
    
    """optional config - especially for run times"""
    def ensure_model_not_instance(cls_or_instance: typing.Any):
        if not isinstance(cls_or_instance, ModelMetaclass) and isinstance(cls_or_instance,AbstractModel):
            """because of its its convenient to use an instance to construct stores and we help the user"""
            return cls_or_instance.__class__
        return cls_or_instance
            
            
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
        return default
        
    @classmethod
    def __get_object_id__(cls):
        """fully qualified name"""
        return f"{cls._get_namespace()}.{cls._get_name()}"
    
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
    def _get_name(cls):
        s = cls.model_json_schema(by_alias=False)
        name = s.get("title") or cls.__name__
        return cls._try_config_attr('name', default=name)
    
    @classmethod
    def _get_external_functions(cls):
        return cls._try_config_attr('functions', default={})

    @classmethod
    def to_meta_model(cls) -> "MetaModel":
        """create the meta model for reading and writing to the database
           An abstract model can be recovered from the meta model
        """
        return MetaModel(name=cls._get_name(), 
                         namespace=cls._get_namespace(),
                         description=cls._get_system_prompt_markdown(),
                         functions=cls._try_config_attr('functions'),
                         key_field=cls._try_config_attr('key'))
 
    @classmethod
    def _get_system_prompt_markdown(cls, 
                                   include_external_functions:bool=True, 
                                   include_fields: bool = True, 
                                   include_date:bool=True) -> str:
        """
        
        """
        
        return f"""
## Model details
name: {cls._get_name()}

## System prompt
{cls._get_description()}
    """
    
    @classmethod
    def get_public_class_and_instance_methods(cls):
        """returns the class and instances methods that are not private"""

        if not isinstance(cls, ModelMetaclass):
            cls = cls.__class__
            
        """any methods that are not on the abstract model are fair game"""
        methods = inspection.get_class_and_instance_methods(cls, inheriting_from=AbstractModel)

        """return everything but hide privates"""
        return [m for m in methods if not m.__name__[:1] == "_"]
    
    @classmethod
    def _get_embedding_fields(cls) -> typing.Dict[str, str]:
        """returns the fields that have embeddings based on the attribute - uses our convention"""
        needs_embeddings = {}
        for k, v in cls.model_fields.items():
            extras = getattr(v, "json_schema_extra", {}) or {}
            if extras.get("embedding_provider"):
                needs_embeddings[k] = f"{k}_embedding"
        return needs_embeddings
    
    
class AbstractEntityModel(AbstractModel):
    id:  uuid.UUID  
    description: str = Field(description="The summary or abstract of the resource", embedding_model="openai.text-embedding-ada-002")
    
    @classmethod
    def _update_records(cls, records: typing.List["AbstractEntityModel"]):
        """"""
        from pyaida import pg
        return pg.repository(cls).update_records(records)
        
    @classmethod
    def _select(cls, fields: typing.Optional[typing.List] = None):
        """"""
        from pyaida import pg
        return pg.repository(cls).select(fields=fields)
        
        
class _MetaField(AbstractModel):
    name: str
    description: typing.Optional[str] = None
    embedding_provider: typing.Optional[str] = None
    default: typing.Optional[str] = None
    
class MetaModel(AbstractModel):
    """
    the meta model is a persisted version of a concrete model
    this can be saved and reloaded from the database and is used for agents
    """
    name: str
    namespace: str = Field('public', description="An optional namespace")
    description: str = Field('', description="System prompt or other overview description")
    functions: dict  = Field({}, description="A mapping of functions to use")
    key_field: typing.Optional[str] = Field('id', description="The primary key field - convention is to simply use id")
    fields: typing.Optional[_MetaField] = Field(description="The fields and their properties")