# AIDA

Tasks for aida
1. create all the tables and a stored procedure that is capable of building background embeddings
2. add the abstract models and the postgres client for CRUD
3. Implement the callable instance manager with OpenAPI spec
4. Test the planner on loading functions from database - all or by search - good use case to start thinking about query planner for context e.g. vector vs other
5. create the Message Builder
-----------
6. test with a simple runner - later add more lang clients
7. Try the meta agent for easily creating new entities
8. think about function relationships to aid planning
9. Build graph builder sproc
10. Test Graph queries

Parsing tasks
1. implement JSONSchema and Content meta tag extract as resources for a number of sites
2. add parsing extensions metadata to the database
------------------------


- AbstactModels 
- Runner
- CallableInstanceManager - manage API proxies and instances in code - fucnctions should have the spec, the instance, the id and the friendly name. id should be sanitized 
- MessageBuilder - should have a generic schema that maps to language clients
- Langauge Model Clients
- MetaAgent - for creating agents and objects
- PlannerAgent

DB - pyaida is just a client
- We store system objects and fields 
- We allow dynamic creation of new types / postgres tables
- We run an embedding service
- We run a graph index service
- Maybe provide a push-d    own query builder e.g. natural language to query result 



Data Model for functions
id (scope.namespace.name)
name
schema
category (mostly external but fine to store class instances - this is a scope)
instance_group_key e.g. API - could be cached function 


Data Model for objects
id
key 
name
namespace
system_prompt

Linked functions
id
object_id
function_id (fk)
function_alias
usage


Fields
id
name
description
embedding_type
object_id




## usage

PLAN: start with agents that work from the database by loading an abstract model - > constructor creates something with a Config
The config allows for name, namespace, system prompt, external functions
The structured fields as for responses and other things like crud
The abstract model should rehydrate or be extensible and work in similar ways


A class that loads (caches) from the database or is pydantic or markdown



Test basic flows for hopping.
Focus on Message Structure Understanding. Should be possible to debug from any stage in the hop.
In the text there is a message graph - context could be used somehow but forgetting would be a problem
Testing database of message sequences 

Logging performance of agents should be free - we should start ranking them


Markdown super prompt could have tabular vals
[System prompt]
Date
Avail functions
Objective
Response Structure

