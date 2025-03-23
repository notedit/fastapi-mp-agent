"""Process worker implementation using multiprocessing.Process."""

import os
import time
import typing
import json
import asyncio
import socket
import multiprocessing
from multiprocessing import Process, Queue
from uuid import UUID, uuid4
import math
import random
import logging
import traceback
from aiohttp import web
import aiohttp
import contextlib

# 获取logger
logger = logging.getLogger(__name__)


class TaskResult:
    """Result of a task execution."""

    def __init__(self, task_id: UUID, status: str, result: typing.Any = None):
        self.task_id = task_id
        self.status = status
        self.result = result

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": str(self.task_id),
            "status": self.status,
            "result": self.result
        }


def find_free_port():
    """查找可用的端口号"""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class ProcessWorker(Process):
    """Multi-process worker that performs long-running tasks with its own aiohttp server."""

    def __init__(self, task_id: UUID, task_type: str, task_data: dict,
                 status_queue: Queue = None):
        """Initialize worker process with task information."""
        super().__init__()
        self.task_id = task_id
        self.task_type = task_type
        self.task_data = task_data
        self.status = "initialized"
        self.result = None
        self.status_queue = status_queue or multiprocessing.Queue()
        self.daemon = True  # 设置为守护进程，使主进程结束时，工作进程也会结束

        # 为工作进程选择一个空闲端口
        self.port = find_free_port()
        self.server_running = multiprocessing.Event()

        logger.debug(
            f"ProcessWorker initialized for task {task_id}, will use port {self.port}")

    def run(self):
        """
        Process entry point - runs when process.start() is called.

        Executes the task and communicates results via the status queue.
        """
        try:
            logger.info(
                f"Worker process started for task {self.task_id} (PID: {self.pid})")

            # 报告启动状态
            self._report_status("initializing", {
                "worker_pid": self.pid,
                "server_port": self.port
            })

            # 启动aiohttp服务器
            asyncio.run(self._run_server_and_task())

        except Exception as e:
            # 捕获并报告任何错误
            error_details = {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            logger.error(
                f"Error in worker process {self.task_id}: {e}", exc_info=True)
            self._report_status("error", error_details)

    async def _run_server_and_task(self):
        """启动aiohttp服务器并执行任务"""
        # 创建aiohttp应用
        app = web.Application()
        app.add_routes([
            web.get('/status', self._handle_status_request),
            web.post('/control', self._handle_control_request),
            web.post('/terminate', self._handle_terminate_request),
        ])

        # 启动server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', self.port)

        logger.info(
            f"Worker {self.task_id} starting HTTP server on port {self.port}")
        await site.start()

        # 设置服务器运行标志
        self.server_running.set()

        # 报告server已启动
        self._report_status("running", {
            "server_url": f"http://127.0.0.1:{self.port}",
            "pid": self.pid
        })
        logger.info(
            f"Worker {self.task_id} HTTP server is running on port {self.port}")

        # 根据任务类型开始执行任务
        task = None
        if self.task_type == "process_data":
            task = asyncio.create_task(self._process_data_task())
        elif self.task_type == "generate_report":
            task = asyncio.create_task(self._generate_report_task())
        elif self.task_type == "cpu_intensive":
            task = asyncio.create_task(self._cpu_intensive_task())
        else:
            logger.error(f"Unknown task type: {self.task_type}")
            self._report_status(
                "error", {"error": f"Unknown task type: {self.task_type}"})
            await runner.cleanup()
            return

        # 等待任务完成或接收到终止信号
        try:
            await task
            logger.info(f"Task {self.task_id} completed successfully")
            self._report_status("completed", self.result)
        except asyncio.CancelledError:
            logger.info(f"Task {self.task_id} was cancelled")
            self._report_status(
                "terminated", {"message": "Task was terminated by request"})
        except Exception as e:
            logger.error(f"Error in task execution: {e}", exc_info=True)
            self._report_status("error", {
                "error": str(e),
                "traceback": traceback.format_exc()
            })
        finally:
            # 关闭服务器
            logger.info(f"Shutting down HTTP server for worker {self.task_id}")
            await runner.cleanup()

    async def _handle_status_request(self, request):
        """处理状态请求"""
        logger.debug(f"Received status request for task {self.task_id}")
        return web.json_response({
            "task_id": str(self.task_id),
            "task_type": self.task_type,
            "status": self.status,
            "result": self.result,
            "pid": self.pid,
            "port": self.port
        })

    async def _handle_control_request(self, request):
        """处理控制请求"""
        try:
            data = await request.json()
            action = data.get('action')

            logger.info(
                f"Received control request: {action} for task {self.task_id}")

            if action == "pause":
                # 实现暂停功能
                self.status = "paused"
                self._report_status("paused")
                return web.json_response({"success": True, "status": "paused"})

            elif action == "resume":
                # 实现恢复功能
                self.status = "running"
                self._report_status("running")
                return web.json_response({"success": True, "status": "running"})

            else:
                return web.json_response(
                    {"error": f"Unknown action: {action}"},
                    status=400
                )

        except Exception as e:
            logger.error(f"Error handling control request: {e}", exc_info=True)
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def _handle_terminate_request(self, request):
        """处理终止请求"""
        logger.info(f"Received terminate request for task {self.task_id}")

        # 通知任务完成并退出服务器
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()

        return web.json_response({"success": True, "message": "Task termination initiated"})

    def _report_status(self, status: str, result: typing.Any = None):
        """
        Report task status to the status queue.

        Args:
            status: Current status of the task
            result: Any result data to include
        """
        self.status = status
        if result is not None:
            self.result = result

        update = {
            "task_id": str(self.task_id),
            "status": status,
            "result": self.result,
            "timestamp": time.time()
        }
        logger.debug(f"Reporting status for task {self.task_id}: {status}")
        self.status_queue.put(update)

    async def _process_data_task(self):
        """模拟数据处理任务 (异步版本)"""
        logger.info(f"[Worker {self.task_id}] Processing data task started")

        # 模拟处理进度
        for i in range(10):
            await asyncio.sleep(1)
            progress = (i+1) * 10
            logger.debug(
                f"[Worker {self.task_id}] Processing progress: {progress}%")

            # 每次进度更新时发送状态
            self._report_status("running", {
                "progress": progress,
                "processed_items": len(self.task_data.get("items", [])) * progress // 100,
                "total_items": len(self.task_data.get("items", []))
            })

        # 处理完成
        self.result = {
            "processed_items": len(self.task_data.get("items", [])),
            "success": True
        }
        logger.info(f"[Worker {self.task_id}] Processing data task completed")

    async def _generate_report_task(self):
        """模拟报告生成任务 (异步版本)"""
        logger.info(f"[Worker {self.task_id}] Report generation task started")

        # 模拟报告生成
        await asyncio.sleep(5)

        report_type = self.task_data.get("report_type", "summary")
        self.result = {
            "report_type": report_type,
            "generated_at": time.time(),
            "report_data": f"This is a {report_type} report"
        }
        logger.info(
            f"[Worker {self.task_id}] Report generation task completed")

    async def _cpu_intensive_task(self):
        """执行CPU密集型计算任务 (异步版本，但实际计算仍是阻塞的)"""
        logger.info(f"[Worker {self.task_id}] CPU intensive task started")

        # 获取计算的复杂度 (默认值：1000000)
        complexity = self.task_data.get("complexity", 1000000)
        batches = self.task_data.get("batches", 5)

        start_time = time.time()
        results = []

        for batch in range(batches):
            batch_start = time.time()
            logger.debug(
                f"[Worker {self.task_id}] Starting batch {batch+1}/{batches}")

            # 每个批次执行一组计算
            iterations = max(1000, complexity // 10)
            result = 0

            # 将批次分成多个更小的块，以便定期报告进度
            chunk_size = iterations // 10
            for i in range(0, iterations, chunk_size):
                # 使用一个执行器来运行CPU密集型任务，以便不阻塞事件循环
                def compute_chunk():
                    chunk_result = 0
                    end = min(i + chunk_size, iterations)
                    for j in range(i, end):
                        x = random.random() * 100
                        chunk_result += math.sqrt(x) * \
                            math.sin(x) / math.cos(x + 0.01)
                    return chunk_result

                # 在执行器中运行计算
                loop = asyncio.get_running_loop()
                chunk_result = await loop.run_in_executor(None, compute_chunk)
                result += chunk_result

                # 更新进度
                progress = min(100, (i + chunk_size) / iterations * 100)
                elapsed = time.time() - batch_start
                logger.debug(
                    f"[Worker {self.task_id}] Batch {batch+1} progress: {progress:.1f}% (elapsed: {elapsed:.2f}s)")

                # 报告进度
                self._report_status("running", {
                    "current_batch": batch + 1,
                    "total_batches": batches,
                    "batch_progress": progress,
                    "overall_progress": (batch * 100 + progress) / batches,
                    "elapsed_time": time.time() - start_time
                })

                # 允许其他任务有机会执行
                await asyncio.sleep(0.01)

            batch_time = time.time() - batch_start
            logger.debug(
                f"[Worker {self.task_id}] Batch {batch+1} completed in {batch_time:.2f}s with result: {result:.2f}")
            results.append(result)

            # 批次间短暂暂停
            await asyncio.sleep(0.5)

        total_time = time.time() - start_time
        self.result = {
            "batches": batches,
            "results": results,
            "average": sum(results) / len(results),
            "elapsed_time": total_time
        }

        logger.info(
            f"[Worker {self.task_id}] CPU intensive task completed in {total_time:.2f}s")
