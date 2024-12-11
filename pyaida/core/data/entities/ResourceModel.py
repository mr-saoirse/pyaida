from pyaida.core.data.AbstractModel import AbstractEntityModel, Field
import typing
from datetime import datetime

class ResourceModel(AbstractEntityModel):
    """The Resource Model is a general model for adding references to material such as books, websites etc. 
    It serves as a generic way to refer to things and follows a bib reference entity model.
    You can use external linked functions to resolve details from a uri
    """
    
    class Config:
        namespace: str = "public"
        functions: dict = {
            "pyaida.resources_parse_page_metadata": "Use this api function to parse attributes from the uri and return a fleshed out ResourceModel"
        }
    
    id: str = Field(description="The unique key normally a hash of a uri or similar")
    uri: str = Field(description="A required unique resource identifier such as a web url")
    title: str = Field(description="The title of the resources")
    authors: typing.Optional[typing.List[str]] = Field(default=None, description="One or more authors")
    """description is inherited"""
    resource_type: typing.Optional[str] = Field(default=None, description="The type of the resource e.g. web|book|article|etc.")
    reference_date: typing.Optional[datetime] = Field(default=None, description="Access or publication date")
    publisher: typing.Optional[str] = Field(default=None, description="The publisher if relevant")
    published_city: typing.Optional[str] = Field(default=None, description="The publisher city if relevant")
    metadata: typing.Optional[dict] = Field(default={}, description="Extra metadata")