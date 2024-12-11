import os
from pathlib import Path
from importlib import import_module

"""local bia db for testing"""
POSTGRES_DB = "postgres"
POSTGRES_SERVER = "localhost"
POSTGRES_PORT = 5432
POSTGRES_PASSWORD =  "password"
POSTGRES_USER = "sirsh"
POSTGRES_CONNECTION_STRING = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

POSTGRES_DB = os.environ['DRAFTER_DB']
POSTGRES_SERVER = os.environ['DRAFTER_DB_HOST']
POSTGRES_PORT = os.environ['DRAFTER_DB_PORT']
POSTGRES_PASSWORD =  os.environ['DRAFTER_DB_PASSWORD']
POSTGRES_USER = os.environ['DRAFTER_DB_USER']
POSTGRES_CONNECTION_STRING = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}?sslmode=require"
   
   
AGE_GRAPH = "pyaida"
STORE_ROOT = os.environ.get('FUNKY_HOME',f"{Path.home()}/.pyaida")

def get_repo_root():
    """the root directory of the project"""
    path = os.environ.get("PYAIDA_REPO_HOME")
    if not path:
        one = import_module("pyaida")
        if one.__file__ is not None:
            path = Path(one.__file__).parent.parent
        else:
            path = Path(__file__).parent.parent.parent
    return Path(path)