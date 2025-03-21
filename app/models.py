"""Data models for API requests and responses."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """Task creation request model."""
    task_type: str = Field(..., description="Type of task to run")
    task_data: Dict[str, Any] = Field(
        default_factory=dict, description="Data for the task")


class TaskResponse(BaseModel):
    """Task response model."""
    task_id: str = Field(..., description="Unique ID of the task")
    task_type: str = Field(..., description="Type of task")
    status: str = Field(..., description="Current status of the task")
    result: Optional[Any] = Field(
        None, description="Result of task execution if available")


class TaskList(BaseModel):
    """List of tasks response model."""
    tasks: Dict[str, TaskResponse] = Field(
        ..., description="Dictionary of task IDs to task details")
