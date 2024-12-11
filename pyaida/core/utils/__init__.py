from loguru import logger
import datetime
from datetime import timezone
import hashlib

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
    

def now():
    return datetime.datetime.now(tz=None)


def utc_now():
    return datetime.datetime.now(tz=timezone.utc)
