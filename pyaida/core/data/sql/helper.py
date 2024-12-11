from pyaida import AbstractEntityModel
from uuid import UUID
import typing
from typing import get_type_hints
from enum import Enum
"""a map to json schema types for serialization"""
import uuid
import types
import json

EMBEDDING_LENGTH_OPEN_AI = 1536

PYTHON_TO_JSON_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def match_type(f, t):
    """a general way to see if we would match this type allowing for optionality and unions"""
    if f is t:
        return True
    args = getattr(f, "__args__", {}) or ()
    return t in args


def some_default_for_type(f):
    """it may be convenient to create a dummy value for a type
    this is somewhat subjective so we are experimenting with this over time
    this is used for DB use cases primarily so things will be serialized in such a way
    """
    is_nullable = types.NoneType in typing.get_args(f)
    if match_type(f, uuid.UUID):
        return str(uuid.uuid4())
    if match_type(f, str):
        return "" if not is_nullable else None
    if match_type(f, typing.List):
        return [] if not is_nullable else None
    if match_type(f, dict):
        return "{}" if not is_nullable else None
    if match_type(f, int):
        return 0 if not is_nullable else None
    if match_type(f, float):
        return 0.0 if not is_nullable else None
    if match_type(f, bool):
        return False if not is_nullable else None

    return "" if not is_nullable else None


class VectorSearchOperator(Enum):
    """
    If vectors are normalized to length 1 (like OpenAI embeddings), use inner product for best performance.
    see also ops
    <~> 	Hamming distance
    <%> 	Jaccard distance

    """

    L1 = " <+>"  # taxicab
    L2 = "<->"  # euclidean
    INNER_PRODUCT = "<#>"  # Neg inner product
    COSINE = "<=>"


class SqlHelper:

    def __init__(cls, model:AbstractEntityModel):
        cls.model = model
        cls.table_name = cls.model.__get_object_id__() 
        cls.field_names = SqlHelper.select_fields(model)
        cls.id_field = cls.model._try_config_attr('key', default='id')
        cls.embedding_fields = list(cls.model._get_embedding_fields().values())
        cls.metadata = {}

    @classmethod
    def select_fields(cls, model):
        """select db relevant fields"""
        fields = []
        for k, v in model.model_fields.items():
            if v.exclude:
                continue
            attr = v.json_schema_extra or {}
            """we skip fields that are complex"""
            if attr.get("sql_child_relation"):
                continue
            fields.append(k)
        return fields
    
    def select_query(self, fields:typing.List[str]=None):
        """"""
        fields = fields or ",".join(self.field_names)
        return f"""SELECT { fields } FROM {self.table_name}"""
    
        

    def select_fields_with_dummies(cls):
        """selects the database fields but uses dummy values. this is to allow for some upsert modes (small hack/trick)"""

        fields = cls.select_fields(cls.model)
        model_fields = get_type_hints(cls.model)

        def dummy_value(field_name):
            ftype = model_fields[field_name] 

            return some_default_for_type(ftype)

        return {f: dummy_value(f) for f in fields}

    def partial_model_tuple(cls, data: dict) -> tuple:
        """
        simple wrapper that creates a placeholder tuple injecting in partial actual data
        this is paired with partial updates
        """
        d = cls.select_fields_with_dummies()
        d.update(data)
        return tuple(d.values())

    
    
    def _db_dump(self, model:AbstractEntityModel|dict):
        """serialize complex types as we need for DBs/Postgres
        - we do things like allow for config to turn fields off
        - we map complex types to json
        - embedding are added async on a new table in our model

        """
        data = vars(model) if not isinstance(model,dict) else model
        """control selectable fields by exclude or other attributes"""

        def check_complex(v):
            if isinstance(v, uuid.UUID):
                v = str(v)
            if isinstance(v, dict):# or isinstance(v, list):
                return json.dumps(v)
            return v

        data = {k: check_complex(v) for k, v in data.items() if k in self.field_names}

        return data
    
    def serialize_for_db(cls, model_instance:AbstractEntityModel|dict) -> dict:
        """this exists only to allow for generalized types
        abstract models can implement db_dump to have an alt serialization path
        """
        if isinstance(model_instance, dict):
            data = model_instance
        else:
            # this is the one we want to override sometimes
            data = cls._db_dump(model_instance)
           
 
        """if there is an embedding map we can add the embeddings here
            but its assumed that the database supports those embeddings by convention
        """
        
        """im not sure what i need to do this yet"""
        d = {}
        import json
        for k,v in data.items():
            if hasattr(v,'model_dump'):
              v = v.model_dump()
            if isinstance(v,list):
                v = [json.dumps( vi.model_dump() ) if hasattr(vi,'model_dump') else vi for vi in v  ]
            d[k] = v  

        return d

    @classmethod
    def pydantic_to_postgres_type(cls, t):
        """fill me in"""
        type_mapping = {
            str: "VARCHAR",
            int: "INTEGER",
            float: "FLOAT",
            bool: "BOOLEAN",
            dict: "JSON",
            UUID: "UUID",
            list: "ARRAY",
        }

        # TODO: need to test adding extras and other complex types like lists and json

        return type_mapping.get(t, "TEXT")

    @classmethod
    def _create_embedding_table_script(cls, entity_model, existing_columns=None):
        """for a separate embedding table
        if we have the connection we can check for a diff and create an alter statement, otherwise we must to the update
        we do not remove columns, but we can add
        """
        pass

    @classmethod
    def _create_view_script(cls, entity_model):
        """
        create or alter the view to select all columns from the join possibly with system columns
        """
        pass

    def create_script(cls, embeddings_inline: bool = False, connection=None, allow_create_schema:bool = False, if_exists: str = 'raise'):
        """

        (WIP) generate tables for entities -> short term we do a single table with now schema management
        then we will add basic migrations and split out the embeddings + add system fields
        we also need to add the other embedding types - if we do async process we need a metadata server
        we also assume the schema exists for now

        We will want to create embedding tables separately and add a view that joins them
        This creates a transaction of three scripts that we create for every entity
        We should add the created at and updated at system fields and maybe a deleted one

        - key register trigger -> upsert into type-name -> on-conflict do nothing

        - we can check existing columns and use an alter to add new ones if the table exists

        """
        entity_model = cls.model

        def is_optional(field):
            return typing.get_origin(field) is typing.Union and type(
                None
            ) in typing.get_args(field)

        table_name = cls.table_name
        fields = typing.get_type_hints(entity_model)
        field_descriptions = entity_model.model_fields
        id_field = cls.id_field

        """check exists and if so determine an alter..."""

        columns = []
        for field_name, field_type in fields.items():
            """handle uuid option"""
            if typing.get_origin(
                field_type
            ) is typing.Union and UUID in typing.get_args(field_type):
                postgres_type = "UUID"
            else:
                postgres_type = SqlHelper.pydantic_to_postgres_type(field_type)

            field_desc = field_descriptions[field_name]
            column_definition = f"{field_name} {postgres_type}"
            # we could have a default thing but hold
            # if field_desc.field_info.default is not None:
            #     column_definition += f" DEFAULT {json.dumps(field_desc.field_info.default)}"
            if field_name == id_field:
                column_definition += " PRIMARY KEY "
            elif not is_optional(field_type):
                column_definition += " NOT NULL"
            columns.append(column_definition)

            """check should add embedding vector for any columns"""
            metadata = field_descriptions.get(field_name)
            extras = getattr(metadata, "json_schema_extra", {}) or {}
            if extras.get("embedding_provider", "").replace("_", "") == "openai":
                pass #observe that we need to create the embedding column table or alter existing
                

            """add system fields - created at and updated at fields"""
            # TODO

        """add system fields"""
        columns.append("created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        columns.append("updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        columns.append("deleted_at TIMESTAMP")
        columns.append("userid UUID")

        columns_str = ",\n    ".join(columns)
        create_table_script = f"""
        CREATE TABLE {table_name} (
            {columns_str}
        );
        
        CREATE TRIGGER update_updated_at_trigger
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();

        """
        return create_table_script

    def upsert_query(
        cls,
        batch_size: int,
        returning="*",  # ID, * etc.
        restricted_update_fields: str = None,
        # records: typing.List[typing.Any],
        # TODO return * or just id for performance
    ):
        """upserts on the ID conflict

        if deleted at set generate another query to set deleted dates for records not in the id list

        This will return a batch statement for some placeholder size. You can then

        ```
        connector.run_update(upsert_sql(...), batch_data)

        ```

        where batch data is some collection of items

        ```
        batch_data = [
            {"id": 1, "name": "Sample1", "description": "A sample description 1", "value": 10.5},
            {"id": 2, "name": "Sample2", "description": "A sample description 2", "value": 20.5},
            {"id": 3, "name": "Sample3", "description": "A sample description 3", "value": 30.5},
        ]
        ```
        """
        
        if restricted_update_fields is not None and not len(restricted_update_fields):
            raise ValueError('You provided an empty list of restricted field')

        """TODO: the return can be efficient * for example pulls back embeddings which is almost never what you want"""
        field_list = cls.field_names
        """conventionally add in order anything that is added in upsert and missing"""
        for c in restricted_update_fields or []:
            if c not in field_list:
                field_list.append(c)

        non_id_fields = [f for f in field_list if f != cls.id_field]
        insert_columns = ", ".join(field_list)
        insert_values = ", ".join([f"%({field})s" for field in field_list])

        """restricted updated fields are powerful for updates 
           we can ignore the other columns in the inserts and added place holder values in the update
        """
        update_set = ", ".join(
            [
                f"{field} = EXCLUDED.{field}"
                for field in restricted_update_fields or non_id_fields
            ]
        )

        value_placeholders = ", ".join(
            [f"({insert_values})" for _ in range(batch_size)]
        )

        # ^old school way but for psycopg2.extras.execute_values below is good
        value_placeholders = "%s"

        """batch insert with conflict - prefix with a delete statement that sets items to deleted"""
        upsert_statement = f"""
        -- now insert
        INSERT INTO {cls.table_name} ({insert_columns})
        VALUES {value_placeholders}
        ON CONFLICT ({cls.id_field}) DO UPDATE
        SET {update_set}
        RETURNING {returning};
        """

        return upsert_statement.strip()

    def partial_update_query(cls, field_names, batch_size: int, returning: str = "*"):
        """
        this is just a slight mod on the other one - we could refactor to just have a field restriction
        """

        return cls.upsert_query(
            batch_size=batch_size,
            returning=returning,
            restricted_update_fields=field_names,
        )

    def query_from_natural_language(
        self,
        question: str,
    ):
        """"""
        pass
