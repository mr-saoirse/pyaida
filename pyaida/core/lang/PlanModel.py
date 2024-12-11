from pyaida.core.data import AbstractEntityModel


class Plan(AbstractEntityModel):
    """use this to build plans - you can search for other agents and run these agents and their functions"""
    
    class Config:
        namespace: str = 'system'
        
    @classmethod
    def test_plan(cls, context:str=None):
        """this is a test function to probe the agent

        Args:
            context (str, optional): pass in context and it will be returned. Defaults to None.
        """
        
        return context