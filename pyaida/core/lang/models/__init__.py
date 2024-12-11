"""add some language model abstractions"""


GPT_MINI = "gpt-4o-mini"
DEFAULT_MODEL =   "gpt-4o-2024-08-06"


import typing
from enum import Enum
from pyaida.core.lang.messages import MessageStack
from abc import ABC, abstractmethod
from .CallingContext import CallingContext
from pyaida.core.lang.functions import Function

class LanguageModelProvider(Enum):

    openai = "openai"
    anthropic = "anthropic"
    google = "google"
    meta = "meta"
    cerebras = "cerebras"
    

class LanguageModel(ABC):

    @classmethod
    def get_provider(cls) -> LanguageModelProvider:
        return 
    
    @abstractmethod
    def get_function_call_or_stream(
        self,
        response: typing.Any,
        callback: typing.Optional[typing.Callable] = None,
        response_buffer: typing.List[typing.Any] = None,
        token_callback_action: typing.Optional[typing.Callable] = None,
    ):
        pass

    @abstractmethod
    def run(
        cls,
        messages: MessageStack,
        context: CallingContext,
        functions: typing.Optional[typing.List[Function]] = None,
    ):
        pass

    def __call__(
        cls,
        messages: MessageStack,
        context: CallingContext,
        functions: typing.Optional[typing.List[Function]] = None,
    ):
        return cls.run(context=context, messages=messages, functions=functions)



class LanguageModelBase:

    @classmethod
    def get_provider():
        return None
    
    def __call__(
        self,
        messages: str | typing.List[dict] | MessageStack,
        context: CallingContext = None,
        functions: typing.Optional[dict] = None,
        **kwargs
    ):
        """the callable is a lightly more opinionated version of run for convenience
        but users of run should remain close to what the model needs
        """
 
        context = context or CallingContext()
        if isinstance(messages, str):
            """simple convenience cheat"""
            messages = MessageStack(model=None).add_question(messages)
 
        self._messages = messages
        self._functions = functions

        return self.run(messages=messages, context=context, functions=functions)




def language_model_client_from_context(
    context: CallingContext = None, with_retries: int = 0
):
    """The model is loaded from the context.
    Retries are used sparingly for some system contexts that require robustness
    e.g. in formatting issues for structured responses

    This context is passed on every invocation anyway so this narrows it down to an api provider or client
    - open ai
    - llama
    - gemini
    - claude

    Within each of these providers the context can choose a model size/version
    """
    context = context or CallingContext()

    if 'claude' in context.model:
        from .claude import ClaudeModel

        return ClaudeModel()
    
    from .gpt import GptModel
    
    """default"""
    return GptModel()
