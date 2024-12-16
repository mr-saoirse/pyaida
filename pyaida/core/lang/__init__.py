from .Runner import Runner
from .FunctionManager import FunctionManager
import openai
import typing
import numpy as np

DEFAULT_TEXT_EMBEDDING_MODEL = "text-embedding-ada-002"

def generate_embeddings(texts: typing.Union[typing.List[str], np.ndarray], model: str = DEFAULT_TEXT_EMBEDDING_MODEL
) -> typing.List[np.array]:
    
    if not texts or texts == '':
        raise ValueError("Empty value passed to generate embeddings")
    
    if not isinstance(texts, list):
        texts= [texts]
        
    rs = openai.embeddings.create(input=texts, model=model).data
    emb = [v.embedding for v in rs]
    return emb