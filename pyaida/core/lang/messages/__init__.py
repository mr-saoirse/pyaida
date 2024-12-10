
"""message stack
- system prompt markdown table
    - model prompt with possible structure + optionally list external functions otherwise on demand
    - date
    - functions that you have listed as a message - model + other
- question


- format -> system, question | [data|data]

- think about the exact shape of data that comes back and what context we have and what maybe be redundant

"""

from .MessageStack import MessageStack