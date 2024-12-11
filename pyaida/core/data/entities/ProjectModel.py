from pyaida.core.data.AbstractModel import AbstractEntityModel, Field
import typing
from datetime import datetime

class ProjectModel(AbstractEntityModel):
    """The Project Model is used to create projects to track goals
    """
    
    class Config:
        namespace: str = "public"
    
    id: str = Field(description="The unique key normally a hash of a uri or similar")
    title: str = Field(description="The title of the resources")
    metadata: typing.Optional[dict] = Field(default={}, description="Extra metadata")
    
    
class TaskModel(AbstractEntityModel):
    """The Task Model to add any todo or sub project tasks
    """
    
    class Config:
        namespace: str = "public"
    
    id: str = Field(description="The unique key normally a hash of a uri or similar")
    title: str = Field(description="The title of the resources")
    due_date: typing.Optional[datetime] = Field(default=None,description="An optional due date")
    project_id: typing.Optional[str] = Field(default=None, description="A project id if known")
    priority: typing.Optional[int] = Field(default=None,description="An optional priority rank e.g. 0 being the hightest")
    metadata: typing.Optional[dict] = Field(default={}, description="Extra metadata")