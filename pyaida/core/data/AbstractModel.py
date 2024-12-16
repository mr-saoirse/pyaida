"""contains the core abstract model and some derived and supporting types"""

from pydantic import BaseModel, create_model, Field
import typing
import docstring_parser
import inspect
from pydantic._internal._model_construction import ModelMetaclass
from pyaida.core.utils import inspection
import uuid
from pyaida.core.utils import sha_hash, logger, inspection
import json
from pydantic.fields import FieldInfo
from pyaida.core.utils.schema import get_pydantic_model_fields_from_json_schema

DEFAULT_NAMESPACE = 'public'

class EmbeddingField(BaseModel):
    column_name: str
    embedding_provider: str
    
class DataColumn(BaseModel):
    index: typing.List[uuid.UUID | str]
    column_name: str
    embedding_provider: typing.Optional[str] = None
    values: typing.Any
    chunk_ranks: typing.Optional[typing.List[int]] = Field([], description="If chunking we need to qualify")
    
    def __len__(self):
        return len(self.values)  # Length of the underlying data


    def expand_text_chunks(self, chunk_size_chars:int=5000, **kwargs):
        """
        convenience to expand records that are too large for chunk size
        """
        
        from pyaida.core.utils import batch_collection
        new_ids = []
        new_values = []
        chunk_ranks = []
        for i, v in enumerate(self.values):
            idx = self.index[i]
            rank = 0
            for batch in batch_collection(v, chunk_size_chars):
                new_ids.append(idx)
                new_values.append(batch)
                """a unique id for each chunk"""
                chunk_ranks.append(rank)
                rank+=1
                
        
        return DataColumn(index=new_ids, 
                          values=new_values, 
                          column_name=self.column_name, 
                          chunk_ranks=chunk_ranks,
                          embedding_provider=self.embedding_provider)
    
    def __iter__(self, *args, **kwargs):
        for i,d in enumerate(self.values):
            yield self.index[i],d

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
    def model_parse(cls,values:dict) -> "AbstractModel":
        """try to parse even when the dict objects are dumped json"""
        for k, v in MetaModel.model_fields.items():
            t = inspection.get_innermost_args(v.annotation)
            if t == dict or inspection.match_type(t, AbstractModel):
                try:
                    if isinstance(values[k],str):
                        values[k] = json.loads(values[k])
                except Exception as ex:
                    pass
        return cls(**values)
                
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
    def create_from_meta_model(cls, meta_model: "MetaModel"):
        """given a metamodel which is a declarative description of a model, create a model.
        This is used in cases where we save/or define a model in a declarative way and we can recover the pydantic object.
        """
        fields = get_pydantic_model_fields_from_json_schema(meta_model.model_schema)
        return cls.create_model(name=meta_model.name.replace(' ', '_'), 
                                namespace=meta_model.namespace, 
                                functions=meta_model.functions, 
                                description=meta_model.description,
                                fields=fields)
        
        
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
        return cls._try_config_attr('name', default=name).replace(' ','_')
    
    @classmethod
    def _get_external_functions(cls) -> dict:
        return cls._try_config_attr('functions', default={})

    @classmethod
    def to_meta_model(cls) -> "MetaModel":
        """create the meta model for reading and writing to the database
           An abstract model can be recovered from the meta model
        """
        return MetaModel(id=cls.__get_object_id__(),
                         name=cls._get_name(), 
                         namespace=cls._get_namespace(),
                         description=cls._get_description(),
                         functions=cls._try_config_attr('functions'),
                         model_schema=cls.model_json_schema(),
                         key_field=cls._try_config_attr('key'))
 
    @classmethod
    def _get_system_prompt_markdown(cls, 
                                   include_external_functions:bool=True, 
                                   include_fields: bool = True, 
                                   include_date:bool=True) -> str:
        """
        Return the system prompt and ass an optional references to external functions and structured fields if asked
        """
        
        prompt = f"""
# Model details
name: {cls._get_name()}

## System prompt
{cls._get_description()}
    """
    
        if include_fields:
            prompt += f"""
## Structured Response Objects (if required)
{cls._get_model_fields_to_markdown()}"""

        if include_external_functions and cls._get_external_functions():
            prompt+= """
## External functions on request
"""
            prompt += '\n'.join(f" - {k}:{v}" for k,v in cls._get_external_functions().items())

        return prompt
        
    @classmethod
    def _get_model_fields_to_markdown(cls):
        """inject a description of the fields into the system prompt"""
        
        from pyaida.core.utils.inspection import get_innermost_args, get_ref_types
        
        def _get_object_fields_markdown(cls_inner, index=1):
            """core logic to generate types so we can parse the tree and add fields for all abstract models"""
            required_fields = """
#### Required fields"""
            optional_fields = """
#### Optional fields"""
            has_optional = False
    
            """get all nested types"""
            
            for k,v in cls_inner.model_fields.items():
                #if match_type(v, AbstractModel):
                    
                type = get_innermost_args(v.annotation)
                s = f" - {k} ({type.__name__}): {v.description if v.description else ''} \n"
                if v.is_required:
                    required_fields += s
                else:
                    has_optional = True
                    optional_fields += s
            return f"""### {index+1}. {cls_inner.__name__}
{required_fields}
{optional_fields if has_optional else ''}
            """
        
        """revers for deepest in the tree, describe all abstract models used"""
        return "\n".join([_get_object_fields_markdown(t,i) for i,t in enumerate(get_ref_types(cls)[::-1])])
        
    @classmethod
    def get_public_class_and_instance_methods(cls: "AbstractModel"):
        """returns the class and instances methods that are not private"""

        if not isinstance(cls, ModelMetaclass):
            cls = cls.__class__
            
        """any methods that are not on the abstract model are fair game"""
        methods = inspection.get_class_and_instance_methods(cls, inheriting_from=AbstractModel)

        """return everything but hide privates
        add on base methods that are functional to agents such as save
        """
        methods = [m for m in methods if not m.__name__[:1] == "_"] 
        for method in ['save']:
            if hasattr(cls, method):
                methods.append(getattr(cls, method))
        return methods
    
    @classmethod
    def _get_embedding_fields(cls) -> typing.List[EmbeddingField]:
        """returns the fields that have embeddings based on the attribute - uses our convention"""
        needs_embeddings = []
        for k, v in cls.model_fields.items():
            extras = getattr(v, "json_schema_extra", {}) or {}
            if extras.get("embedding_provider"):
                needs_embeddings.append(EmbeddingField(column_name=k, embedding_provider=extras['embedding_provider']))
        return needs_embeddings
    
    @classmethod
    def get_column(cls, values: typing.List[typing.Union[dict,"AbstractModel"]],column_name: str) -> DataColumn:
        """get the collection with metadata - handles dict or model
        TODO: convert to polars 
        """
        if not isinstance(values, list) and values:
            values = [values]
        data = [d[column_name] if isinstance(d, dict) else getattr(d, column_name) for d in values]
        key_field = "id" #TODO: does this generalize
        ids = [d[key_field] if isinstance(d, dict) else getattr(d, key_field) for d in values]
        embedding_metadata = [c for c in cls._get_embedding_fields() if c.column_name == column_name]
        embedding_provider = None if not embedding_metadata else embedding_metadata[0].embedding_provider
        return DataColumn(index=ids, column_name=column_name, values=data, embedding_provider=embedding_provider)

class AbstractEntityModel(AbstractModel):
    id:  uuid.UUID  
    description: str = Field(description="The summary or abstract of the resource", embedding_provider="openai.text-embedding-ada-002")
    
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
 
    """if you need to override defaults on your model do it on the validator or override save 
    e.g. in case agent passes null values for required fields"""
    @classmethod
    def save(cls, data: "AbstractEntityModel"):
        """save the entity by supplying all the fields described in the system prompt:
        Be sure to pass the object as-is given by the schema. Do not add extra scaffolding on the parameter.
        Args:
            data: a dictionary of values respecting the supplied data model. the data parameter should have the fields using the response model schema at top level
        """
        
        if isinstance(data,dict):
            """validator"""
            try:
                data = cls(**data)
            except:
                logger.warning(f"Failed to parse {data} into model {cls.__get_object_id__()}")
        
        from pyaida import pg
        try:
            result = pg.repository(cls).update_records(data)
        except Exception as ex:
            import traceback
            logger.warning(f"Failing to save the entity")
            logger.warning(traceback.format_exc())
            return {
                'status': 'Failed to save',
                "error": repr(ex)
            }
        return {
            'status': 'success - entity saved'
            #if useful return the context
        }
        
        
# class _MetaField(AbstractModel):
#     name: str
#     #TODO: for testing we can maybe be lax on typing for agentic systems
#     type: typing.Optional[str] = "str"
#     description: typing.Optional[str] = None
#     embedding_provider: typing.Optional[str] = None
#     default: typing.Optional[str] = None
    
#     @classmethod
#     def fields_from_schema(cls, model:AbstractModel)->typing.List["_MetaField"]:
#         """given the model json schema/ fields from the thing, generate the field objects for saving"""
#         pass
    
#     def as_field_info(self):
#         """get the field info obj"""
#         annotation = str #TODO resolve the type in some sort of smart way
#         embedding_provider = None if self.embedding_provider in ('', 'default') else self.embedding_provider
#         field =  Field (self.default, description=self.description) if not embedding_provider else Field (self.default, description=self.description, embedding_provider=self.embedding_provider)
#         return (annotation,field)
    
class MetaModel(AbstractEntityModel):
    """
    the meta model is a persisted version of a concrete model
    this can be saved and reloaded from the database and is used for agents
    """
    
    class Config:
        namespace:str = "public"
        description: str = "The Meta Model is the abstract representation of models or agents as can be saved or shared declaratively"
    
    id: str
    name: str
    namespace: str = Field('public', description="An optional namespace")
    description: str = Field('', description="System prompt or other overview description")
    functions: typing.Optional[dict]  = Field({}, description="A mapping of functions to use. simply map the function id to a description in a flat dict")
    key_field: typing.Optional[str] = Field('id', description="The primary key field - convention is to simply use id")
    model_schema: dict = Field(description="The fields and their properties")
 
    
class AssociatedEmbeddingModel(AbstractModel):
    """A table that is associated with the primary table to provide embeddings"""
    
    class Config:
        namespace:str = 'public'
        
    id: typing.Optional[str] = Field(description="The id should be generated as a hash of the fk and column name but also the embedding to allow for multiple embeddings per column")
    source_table_id: uuid.UUID|str 
    column_name: str = Field(description="The embedded content column - tables can have 0 or more linked embeddings")
    embedding_vector: typing.Optional[typing.List[float]] = Field(description="The embedding vector often computed in the data tier")
    embedding_id: typing.Optional[uuid.UUID|str] = Field("The embedding provider id into the embeddings loop - default to cheapest open api model")
    
    @classmethod
    def id_for_table(cls, table_name:str, foreign_key:str, values:dict, rank:int=0):
        """
        Generate a conventional id for the embedding. For example, consider a table public.MyTable.
        We create embeddings in embeddings.public_MyTable and add a link.
        A record in the embeddings table has an upsertable id that uniquely defines an embedding type for a field.
        For chunking we also add a rank
        """
        from pyaida.core.utils import sha_hash
        d = dict({k:v for k,v in values.items() if k != 'embedding_vector'})
        d['foreign_key'] = foreign_key
        d['rank'] = rank
        id = sha_hash(d)
        return id
        
    @classmethod
    def from_data_and_embeddings(cls, data_column: DataColumn, embeddings, model:AbstractModel):
        """speed up with polars later - given a data column which is expected to be a small batch,
        merge the embeddings and column metadata to create a record that we can save as a foreign table for linked embeddings.
        although we want to speed up, actually this is just for testing since we expect to push down the embeddings into postgres
        """
        
        batch = []
        for i, tup in enumerate(data_column): 
            fid, _ = tup
            rank = data_column.chunk_ranks[i] if data_column.chunk_ranks else 0
            values = {
                'embedding_vector' : embeddings[i],
                'source_table_id':fid,
                'column_name': data_column.column_name,
                'embedding_id':  sha_hash(data_column.embedding_provider) 
            }
            id = cls.id_for_table(table_name=model.__get_object_id__(), 
                                  foreign_key=fid,
                                  rank=rank,
                                  values=values)
            
            """create a concrete AssociatedEmbeddingModel that is saved to the right place"""
            concrete_model = AssociatedEmbeddingModel.create_model(name=model.__get_object_id__().replace('.','_'), 
                                                                   namespace='embeddings')

            """added to the batch"""
            batch.append(concrete_model(id=id, **values))
            
        """now we have a batch of embeddings that can be saved"""
        return batch
        
        
    @classmethod
    def generate_embeddings(cls, 
                          records: typing.List[dict|AbstractEntityModel], 
                          model: AbstractModel=None,
                          batch_size:int=50):
        """
        given some source table with embedding metadata, for each column with embeddings, generate the embeddings records
                
        """
        from pyaida.core.utils import batch_collection,logger
        from pyaida.core.lang import generate_embeddings
        
        if model is None:
            assert isinstance(records[0],AbstractModel), "The model was not supplied to generate embeddings and the records are not abstract model. The model type cannot be inferred"
            model = type(records[0])
            
        for batch in batch_collection(records, batch_size):
            for embedding_column in model._get_embedding_fields():
                """get column will get the data as dicts"""
                data :DataColumn = model.get_column(batch, embedding_column.column_name)
                item_count = len(data)
                """to allow chunking - we map one to many embedding chunks"""
                data = data.expand_text_chunks()
                logger.debug(f"Chunked {item_count} into {len(data)} chunks")
                """note that we split our qualified convention to get the last term, the model"""
                embeddings = generate_embeddings(data.values, model=embedding_column.embedding_provider.split('.')[-1])    
                record_batch = AssociatedEmbeddingModel.from_data_and_embeddings(data, embeddings, model)
                yield record_batch
                
                