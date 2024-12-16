from pyaida.core.data.AbstractModel import AbstractModel, AbstractEntityModel
from pyaida.core.lang import Runner
from pyaida.core.lang.models import CallingContext
    
def get_bg():
    from pyaida.core.data.pg.PostgresService import PostgresService
    return PostgresService()


pg = get_bg()


def ask(question:str, model:AbstractModel | str =None, context:CallingContext=None, **kwargs):
    """ask a question of any model. For repo models in the codebase supply the type.
otherwise supply a key to load a declarative model from the database.
    """
    from pyaida.core.lang import Runner
    from pyaida import pg
    
    if not model:
        raise NotImplementedError("Have not added the default ask")
    
    if isinstance(model, str):
        model = pg.load_model_from_key(model)
    
    return Runner(model).run(question, context=context or CallingContext(), **kwargs)
    