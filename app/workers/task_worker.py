"""Task worker implementation using uActor."""

import time
import typing
from uuid import UUID
# 修改导入路径，使用项目根目录的uactor模块

from .uactor import Actor


class TaskResult:
    """Result of a task execution."""

    def __init__(self, task_id: UUID, status: str, result: typing.Any = None):
        self.task_id = task_id
        self.status = status
        self.result = result


class TaskWorker(Actor):
    """Actor that performs long-running tasks."""

    # 确保TaskWorker类公开所需的方法
    _exposed_ = ('start_task', 'get_status', 'shutdown')

    def __init__(self, task_id: UUID, task_type: str, task_data: dict):
        """Initialize task worker with task information."""
        super().__init__()
        self.task_id = task_id
        self.task_type = task_type
        self.task_data = task_data
        self.status = "initialized"
        self.result = None

    def start_task(self) -> TaskResult:
        """Start the long-running task."""
        self.status = "running"
        try:
            # Simulate long-running task
            if self.task_type == "process_data":
                self.process_data_task()
            elif self.task_type == "generate_report":
                self.generate_report_task()
            else:
                raise ValueError(f"Unknown task type: {self.task_type}")

            self.status = "completed"
            return TaskResult(self.task_id, self.status, self.result)
        except Exception as e:
            self.status = "failed"
            self.result = str(e)
            return TaskResult(self.task_id, self.status, self.result)

    def process_data_task(self):
        """Simulate a data processing task."""
        print(f"[Worker {self.task_id}] Processing data task started")
        # Simulate work with a sleep
        for i in range(1000):
            time.sleep(1)
            print(f"[Worker {self.task_id}] Processing progress: {(i+1)*10}%")

        self.result = {"processed_items": len(self.task_data.get("items", [])),
                       "success": True}
        print(f"[Worker {self.task_id}] Processing data task completed")

    def generate_report_task(self):
        """Simulate a report generation task."""
        print(f"[Worker {self.task_id}] Report generation task started")
        # Simulate work with a sleep
        time.sleep(5)

        report_type = self.task_data.get("report_type", "summary")
        self.result = {
            "report_type": report_type,
            "generated_at": time.time(),
            "report_data": f"This is a {report_type} report"
        }
        print(f"[Worker {self.task_id}] Report generation task completed")

    def get_status(self) -> dict:
        """Get the current status of the task."""
        return {
            "task_id": str(self.task_id),
            "task_type": self.task_type,
            "status": self.status,
            "result": self.result
        }

    def shutdown(self):
        """Clean up resources before actor process terminates."""
        print(f"[Worker {self.task_id}] Shutting down worker")
