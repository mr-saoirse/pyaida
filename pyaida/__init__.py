from pyaida.core.data.AbstractModel import AbstractModel, AbstractEntityModel
from pyaida.core.lang import Runner

def get_bg():
    from pyaida.core.data.pg.PostgresService import PostgresService
    return PostgresService()


pg = get_bg()