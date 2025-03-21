"""Task manager for coordinating worker processes."""
import uuid
from typing import Dict, Optional, Any
from app.workers.task_worker import TaskWorker


class TaskManager:
    """Manages task worker processes."""

    def __init__(self):
        """Initialize the task manager."""
        self.tasks: Dict[str, TaskWorker] = {}

    def create_task(self, task_type: str, task_data: dict) -> str:
        """
        Create a new task and start its worker process.

        Args:
            task_type: Type of task to run
            task_data: Data required for the task

        Returns:
            task_id: UUID of the created task
        """
        task_id = str(uuid.uuid4())

        # Create a new TaskWorker actor process
        worker = TaskWorker(uuid.UUID(task_id), task_type, task_data)

        # Store the worker proxy
        self.tasks[task_id] = worker

        # Start the task in the worker process
        worker.start_task()

        return task_id

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """
        Get the status of a task.

        Args:
            task_id: UUID of the task

        Returns:
            Status dictionary or None if task not found
        """
        worker = self.tasks.get(task_id)
        if worker:
            return worker.get_status()
        return None

    def list_tasks(self) -> Dict[str, dict]:
        """
        List all tasks and their statuses.

        Returns:
            Dictionary of task IDs to task statuses
        """
        return {task_id: worker.get_status() for task_id, worker in self.tasks.items()}

    def terminate_task(self, task_id: str) -> bool:
        """
        Terminate a running task.

        Args:
            task_id: UUID of the task

        Returns:
            True if task was terminated, False otherwise
        """
        worker = self.tasks.get(task_id)
        if worker:
            try:
                worker.shutdown()
                del self.tasks[task_id]
                return True
            except Exception:
                return False
        return False
