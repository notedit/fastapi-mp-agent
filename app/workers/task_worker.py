"""Task worker implementation using uActor."""

import time
import typing
from uuid import UUID
import math
import random
from app.workers.uactor import Actor


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
            elif self.task_type == "cpu_intensive":
                self.cpu_intensive_task()
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
        for i in range(10):
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

    def cpu_intensive_task(self):
        """执行CPU密集型计算任务."""
        print(f"[Worker {self.task_id}] CPU intensive task started")

        # 获取计算的复杂度 (默认值：1000000)
        iterations = self.task_data.get("iterations", 1000000)
        # 获取要计算的批次数 (默认值：10)
        batches = self.task_data.get("batches", 10)

        results = []
        start_time = time.time()

        for batch in range(batches):
            batch_start = time.time()
            print(
                f"[Worker {self.task_id}] Starting batch {batch+1}/{batches}")

            # 执行复杂数学计算
            result = 0
            for i in range(iterations):
                # 进行一些CPU密集型计算：计算素数、排序、矩阵计算等
                result += math.sin(math.sqrt(abs(math.cos(i * 0.001))
                                   * i)) * math.pi

                # 每处理一定数量的项目时打印进度
                if i % (iterations // 10) == 0 and i > 0:
                    progress = i / iterations * 100
                    elapsed = time.time() - batch_start
                    print(
                        f"[Worker {self.task_id}] Batch {batch+1} progress: {progress:.1f}% (elapsed: {elapsed:.2f}s)")

            batch_time = time.time() - batch_start
            print(
                f"[Worker {self.task_id}] Batch {batch+1} completed in {batch_time:.2f}s with result: {result:.2f}")
            results.append(
                {"batch": batch+1, "result": result, "time": batch_time})

            # 在批次之间随机暂停一小段时间，让CPU稍微休息一下
            if batch < batches - 1:
                pause = random.uniform(0.5, 2.0)
                time.sleep(pause)

        total_time = time.time() - start_time

        self.result = {
            "iterations_per_batch": iterations,
            "batches": batches,
            "total_time": total_time,
            "batch_results": results,
            "average_time_per_batch": total_time / batches
        }

        print(
            f"[Worker {self.task_id}] CPU intensive task completed in {total_time:.2f}s")

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
