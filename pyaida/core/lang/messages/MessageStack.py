from pyaida.core.data import AbstractModel
import typing
from pydantic import BaseModel, Field
from pyaida.core.lang.models import CallingContext
import json

class Message(BaseModel):
    role: str
    content: str | dict
    name: typing.Optional[str] = Field(
        description="for example function names", default=None
    )


class UserMessage(Message):
    role: str = "user"

class SystemMessage(Message):
    role: str = "system"

class AssistantMessage(Message):
    role: str = "assistant"

class MessageStack:
    def __init__(self, model: AbstractModel, 
                 function_names: typing.Optional[typing.List[str]] = None,
                 language_model_provider: str = None):
        """
        provide a model to construct a message stack from
        the function names are added as a pyaida hint - in future we may generalize this as a tabular context
        the language model is provided because there may be different formats per provider
        """
        self.model = model
        self.function_names = function_names
        self.language_model_provider = language_model_provider
        self._messages = [
            SystemMessage(content=model._get_system_prompt_markdown())
        ]
        if function_names:
            self._messages.append(
                SystemMessage(content=f"I can load functions by name or search if needed. I can use the following functions by default: {function_names}. I will read the function descriptions and parameter descriptions carefully")
            )
        
    def add_message(self, message: Message):
        """add a typed message e.g. system or user to the stack"""
        self._messages.append(message)
        return self
    
    def add(self, message: Message):
        """alias for add message"""
        return self.add_message(message)
     
    def add_question(self, question:str):
        """add a question to the stack"""
        return self.add_message(UserMessage(content=question))
    
    @classmethod
    def from_q_and_a(cls, question:str, data: typing.Any, observer_model:AbstractModel=AbstractModel):
        """
        often we will have a question that will trigger a search
        the search result can then be 'observed' by an observer model that responds to the user
        the result of this is typically to provide a formatted response to the user
        
        the data should be serializable to json
        
        """
        messages= [
            SystemMessage(content=f'The data below were retrieved from a resource and can be used to answer the users question\n````json{json.dumps(data,default=str)}``'),
            UserMessage(content=question)
        ]
        return MessageStack(question=question,messages=messages, model=observer_model)
    
    @classmethod
    def format_function_response_data(
        cls, name: str, data: typing.Any, context: CallingContext = None
    ) -> Message:
        """format the function response for the agent - essentially just a json dump

        Args:
            name (str): the name of the function
            data (typing.Any): the function response
            context (CallingContext, optional): context such as what model we are using to format the message with

        Returns: formatted messages for agent as a dict
        """
        
        """Pydantic things """
        if hasattr(data,'model_dump'):
            data = data.model_dump()

        return Message(
            role="function",
            name=f"{str(name)}",
            content=json.dumps(
                {
                    # do we need to be this paranoid most of the time?? this is a good label to point later stages to the results
                    "about-these-data": f"You called the tool or function `{name}` and here are some data that may or may not contain the answer to your question - please review it carefully",
                    "data": data,
                },
                default=str,
            ),
        )

    @classmethod
    def format_function_response_type_error(
        cls, name: str, ex: Exception, context: CallingContext = None
    ) -> Message:
        """type errors imply the function was incorrectly called and the agent should try again

        Args:
            name (str): the name of the function
            data (typing.Any): the function response
            context (CallingContext, optional): context such as what model we are using to format the message with

        Returns: formatted error messages for agent as a dict
        """
        return Message(
            role="function",
            name=f"{str(name.replace('.','_'))}",
            content=f"""You have called the function incorrectly - try again {ex}.
            If the user does not supply a parameter the function may supply a hint about default parameters.
            You can use the function description in your list of functions for hints if you do not know what parameters to pass!""",
        )

    def format_function_response_error(
        name: str, ex: Exception, context: CallingContext = None
    ) -> Message:
        """general errors imply something wrong with the function call

        Args:
            name (str): the name of the function
            data (typing.Any): the function response
            context (CallingContext, optional): context such as what model we are using to format the message with

        Returns: formatted error messages for agent as a dict
        """

        return Message(
            role="function",
            name=f"{str(name.replace('.','_'))}",
            content=f"""This function failed - you should try different arguments or a different function. - {ex}. 
If no data are found you must search for another function if you can to answer the users question. 
Otherwise check the error and consider your input parameters """,
        )
        
    def __iter__(self):
        for m in self._messages:
            yield m
            
    def model_dump(self):
        """dump the stack - may be provider specific """
        return [m.model_dump() for m in self]