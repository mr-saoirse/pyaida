from pyaida import AbstractEntityModel
import psycopg2
from pyaida.core.utils.env import POSTGRES_CONNECTION_STRING
from pyaida.core.data.sql import SqlHelper, VectorSearchOperator
import typing
from pyaida.core.utils import logger, batch_collection
import psycopg2.extras
from psycopg2 import sql
from psycopg2.errors import DuplicateTable  
from pyaida.core.data.AbstractModel import MetaModel
from pyaida.core.lang import generate_embeddings

class PostgresService:
    """the postgres service wrapper for sinking and querying entities/models"""

    def __init__(self, model: AbstractEntityModel=None, conn = None):
        try:
            self.conn = None
            self.conn = conn or psycopg2.connect(POSTGRES_CONNECTION_STRING)
            """we do this because its easy for user to assume the instance is what we want instead of the type"""
            model = AbstractEntityModel.ensure_model_not_instance(model)
            self.model = model      
            self.helper = SqlHelper(model) if model else SqlHelper 
        except:
            import traceback
            logger.warning(traceback.format_exc())
            logger.warning("Could not connect - you will need to check your env and call pg._connect again")
        
    def _connect(self):
        self.conn = psycopg2.connect(POSTGRES_CONNECTION_STRING)
        return  self.conn

    def repository(self, model:AbstractEntityModel):
        """a connection in the context of the abstract model for crud support"""
        return PostgresService(model=model, conn=self.conn)

    def register(self, plan:bool=False, allow_create_schema:bool = False, add_embedding_table: bool=True):
        """"""    
        assert self.model is not None, "You need to specify a model in the constructor or via a repository to register models"
        script = self.helper.create_script(allow_create_schema=allow_create_schema)
        logger.debug(script)
        if plan:
            return
        
        try:
            self.execute(script)
        except DuplicateTable:
            logger.warning(f"The table already exists - ignoring")
        
        """added the embedding but check if there are certainly embedding columns"""
        if add_embedding_table and len(self.helper.model._get_embedding_fields()):
            try:
                self.execute(self.helper.embedding_table_creation_script())
                logger.warning(f"Created embedding table")
            except DuplicateTable:
                logger.warning(f"The embedding-associated table already exists")
            
    def ask(self, question:str):
        """
        natural language to sql using the model
        """
        query = self.helper.query_from_natural_language(question=question)
        return self.execute(query)
     
    def execute(
        cls,
        query: str,
        data: tuple = None,
        as_upsert: bool = False,
        page_size: int = 100,
    ):
        """run any sql query
        this works only for selects and transactional updates without selects
        """
        
        # lets not do this for a moment
        # if not isinstance(data, tuple):
        #     data = (data,)
        
        if cls.conn is None:
            logger.warning("Connect not initialized - returning nothing. Check your env and re-connect the service")
            return
        if not query:
            return
        try:
            c = cls.conn.cursor()
            if as_upsert:
                psycopg2.extras.execute_values(
                    c, query, data, template=None, page_size=page_size
                )
            else:
                c.execute(query, data)

            if c.description:
                result = c.fetchall()
                """if we have and updated and read we can commit and send,
                otherwise we commit outside this block"""
                cls.conn.commit()
                column_names = [desc[0] for desc in c.description or []]
                result = [dict(zip(column_names, r)) for r in result]
                return result
            """case of upsert no-query transactions"""
            cls.conn.commit()
        except Exception as pex:
            logger.warning(f"Failing to execute query {query} for model {cls.model} - Postgres error: {pex}, {data}")
            cls.conn.rollback()
            raise
        finally:
            cls.conn.close
    
    def select(self, fields: typing.List[str] = None):
        """
        select based on the model
        """
        assert self.model is not None, "You need to specify a model in the constructor or via a repository to select models"
        return self.execute(self.helper.select_query(fields))
    
    def select_to_model(self, fields: typing.List[str] = None):
         """
         like select except we construct the model objects
         """
         data = self.select(fields) 
         return [self.model.model_parse(d) for d in data]

    def run_procedure(self, name, **kwargs):
        """"""
        pass
    
    def load_model_from_key(self, key: str):
        """
        load the model from the database. If the model is not registered you can create an anonymous one.
        The reason you might do this is just to have the postgres binding metadata i.e. the table name for CRUD.
        But you really want to have the fields and associated functions defined
        """
        #data = self.run_procedure("get_entity", key=key)
        
        Q = """
        
        """
        
        if data:
            data = data[0]
            return AbstractEntityModel.create_model(
                **data
            )
        
    @staticmethod
    def save_meta_model(model: MetaModel):
        """save the meta model to the database - its saved over three tabes"""
        
        pass
            
    def execute_upsert(cls, query: str, data: tuple = None, page_size: int = 100):
        """run an upsert sql query"""
        return cls.execute(query, data=data, page_size=page_size, as_upsert=True)
            
    def update_records(self, records: typing.List[AbstractEntityModel], batch_size:int=50):
        """records are updated using typed object relational mapping."""

        if records and not isinstance(records, list):
            records = [records]
        """
        something i am trying to understand is model for sub classed models e.g. missing content but
        """
        
        if len(records) > batch_size:
            logger.info(f"Saving  {len(records)} records in batches of {batch_size}")
            for batch in batch_collection(records, batch_size=batch_size):
                sample = self.update_records(batch, batch_size=batch_size)
            return sample
                
 
        data = [
            tuple(self.helper.serialize_for_db(r).values()) for i, r in enumerate(records)
        ]
 
        if records:
            query = self.helper.upsert_query(batch_size=len(records))
            try:
                result = self.execute_upsert(query=query, data=data)
            except:
                logger.info(f"Failing to run {query}")
                raise

            return result
        else:
            logger.warning(f"Nothing to do - records is empty {records}")
            
    def run_search(self, questions: str, **kwargs):
        """run an intelligence search on the entity"""
        
        assert self.model, "You must specify a model to run the search"
        
        """just for testing but we should generate a query that joins sql query and vector and graph in some sort of smart way"""
        
        return self.vector_search(questions)    
    
    def vector_search(
        self,
        question: str,
        search_operator: VectorSearchOperator = VectorSearchOperator.INNER_PRODUCT,
        limit: int = 7,
    ):
        """
        search the model' embedding content
        in generally we can query multiple embeddings per table but for now testing with just one

        Args:
            question: a natural language question
            search_operator: the pg_vector operator type as an enum - uses the default inner product because we use the open ai embeddings by default
            limit: limit results to return
        """
        print(question)
                
        if not self.helper.embedding_fields:
            raise Exception(
                "this type does not support vector search as there are no embedding columns"
            )
            
        if isinstance(question,list):
            """todo async - """
            logger.debug("Splitting question into three parts and reducing limit")
            lists = [self.vector_search(q, limit=min(3,limit//len(question))) for q in question]
            return   [item for sublist in lists for item in sublist]

        vec = generate_embeddings(question)[0]    
        """alias with the one from below - for vector search only return the embedding content"""
        select_fields = ",".join([f"a.{a}" for a in self.helper.embedding_fields])
         ##TODO: this only makes sense for the neg inner product
        distance_max: float = -0.79
        part_predicates = (
            f"embedding_vector {search_operator.value} '{vec}' < {distance_max}"
        )

        """distances are determined in different ways, that includes what 'large' is"""
        distances = f"embedding_vector {search_operator.value} '{vec}' "

        """generate the query for now for only one embedding col"""
        query = f"""SELECT
            {select_fields},
            ({distances}) as distances
            from {self.helper.table_name} a 
              join {self.helper.embedding_table_name} b on a.id = b.source_table_id
              WHERE b.{part_predicates}
                order by {distances} ASC LIMIT {limit}
             """

        return self.execute(query)