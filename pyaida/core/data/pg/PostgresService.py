from pyaida import AbstractEntityModel
import psycopg2
from pyaida.core.utils.env import POSTGRES_CONNECTION_STRING
from pyaida.core.data.sql import SqlHelper
import typing
from pyaida.core.utils import logger
import psycopg2.extras

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

    def register(self, plan:bool=False, allow_create_schema:bool = False):
        """"""    
        assert self.model is not None, "You need to specify a model in the constructor or via a repository to register models"
        script = self.helper.create_script(allow_create_schema=allow_create_schema)
        logger.debug(script)
        if plan:
            return
        self.execute(script)
            
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
            

    def run_procedure(self, name, **kwargs):
        """"""
        pass
    
    def load_model_from_key(self, key: str):
        """
        load the model from the database
        """
        data = self.run_procedure("get_entity", key=key)
        if data:
            data = data[0]
            return AbstractEntityModel.create_model(
                **data
            )
            
    def execute_upsert(cls, query: str, data: tuple = None, page_size: int = 100):
        """run an upsert sql query"""
        return cls.execute(query, data=data, page_size=page_size, as_upsert=True)
            
    def update_records(self, records: typing.List[AbstractEntityModel]):
        """records are updated using typed object relational mapping."""

        if records and not isinstance(records, list):
            records = [records]
        """
        something i am trying to understand is model for sub classed models e.g. missing content but
        """
 
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