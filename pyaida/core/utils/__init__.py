"""some convenience methods that we can break out later"""

from loguru import logger
import datetime
from datetime import timezone
import hashlib
import uuid
import json

def batch_collection(collection, batch_size):
    """Yield successive batches of size batch_size from collection. can also be used to chunk string of chars"""
    for i in range(0, len(collection), batch_size):
        yield collection[i:i + batch_size]
        
def short_md5_hash(input_string: str, length: int = 8) -> str:
    """
    Generate a short hash of a string using MD5 and truncate to the specified length.

    Args:
        input_string (str): The input string to hash.
        length (int): The desired length of the hash (default is 8).

    Returns:
        str: A short MD5 hash of the input string with the specified length.
    """
    if length < 1 or length > 32:
        raise ValueError("Length must be between 1 and 32 characters.")
    
    return hashlib.md5(input_string.encode()).hexdigest()[:length]

def sha_hash(input_str: str | dict):
    """"""
    
    if isinstance(input_str,dict):
        input_str = json.dumps(input_str)
        
    namespace = uuid.NAMESPACE_DNS  # Predefined namespace for domain names
    return str(uuid.uuid5(namespace, input_str))

    

def now():
    return datetime.datetime.now(tz=None)


def utc_now():
    return datetime.datetime.now(tz=timezone.utc)
