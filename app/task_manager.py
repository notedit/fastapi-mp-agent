"""Task manager for coordinating worker processes."""
import uuid
import time
import asyncio
import logging
import aiohttp
from typing import Dict, Optional, Any
from multiprocessing import Queue, Process
from app.workers.process_worker import ProcessWorker

# 获取logger
logger = logging.getLogger(__name__)


class TaskManager:
    """Manages task worker processes."""

    def __init__(self):
        """Initialize the task manager."""
        self.tasks: Dict[str, dict] = {}
        self.status_queue = Queue()
        self.stop_event = asyncio.Event()
        self.monitor_task = None
        self.client_session = None  # aiohttp客户端会话，用于与工作进程通信
        logger.info("Task manager initialized")

    async def start_monitor(self):
        """启动异步监控任务，处理从队列接收的任务状态更新"""
        logger.info("Starting task status monitor...")
        # 创建aiohttp客户端会话
        self.client_session = aiohttp.ClientSession()
        self.monitor_task = asyncio.create_task(self._monitor_status_updates())
        logger.info("Task status monitor started")
        return self.monitor_task

    async def _monitor_status_updates(self):
        """监控状态更新的异步任务"""
        logger.info("Monitor task is running")
        while not self.stop_event.is_set():
            try:
                # 使用一个线程池执行器来处理阻塞的Queue操作
                if not self.status_queue.empty():
                    # 使用run_in_executor将阻塞调用包装到线程中
                    loop = asyncio.get_running_loop()
                    status_update = await loop.run_in_executor(
                        None, lambda: self.status_queue.get(timeout=1)
                    )

                    task_id = status_update.get('task_id')
                    if task_id in self.tasks:
                        old_status = self.tasks[task_id].get('status')
                        new_status = status_update.get('status')

                        # 更新任务状态
                        self.tasks[task_id].update({
                            'status': new_status,
                            'result': status_update.get('result')
                        })

                        # 如果状态更新包含worker_server信息，保存它
                        if status_update.get('result') and 'server_url' in status_update.get('result', {}):
                            self.tasks[task_id]['worker_server'] = status_update['result']['server_url']
                            logger.info(
                                f"Worker server for task {task_id} registered at: {self.tasks[task_id]['worker_server']}")

                        # 记录状态变化
                        if old_status != new_status:
                            logger.info(
                                f"Task {task_id} status changed: {old_status} -> {new_status}")
                else:
                    # 短暂等待
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in status monitor: {e}", exc_info=True)
                await asyncio.sleep(0.5)  # 出错后短暂暂停

        logger.info("Monitor task is shutting down")

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
        logger.info(f"Creating new task {task_id} of type '{task_type}'")

        # 创建新的ProcessWorker
        worker = ProcessWorker(
            uuid.UUID(task_id),
            task_type,
            task_data,
            self.status_queue
        )

        # 存储任务初始信息
        self.tasks[task_id] = {
            'task_id': task_id,
            'task_type': task_type,
            'status': 'initialized',
            'result': None,
            'worker': worker,
            'worker_server': None,  # 工作进程的HTTP服务器URL
            'created_at': time.time()
        }

        # 启动工作进程
        worker.start()
        logger.info(
            f"Worker process for task {task_id} started with PID: {worker.pid}")

        return task_id

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """
        Get the status of a task.

        Args:
            task_id: UUID of the task

        Returns:
            Status dictionary or None if task not found
        """
        task = self.tasks.get(task_id)
        if task:
            # 返回状态副本，不包含进程对象
            return {
                'task_id': task['task_id'],
                'task_type': task['task_type'],
                'status': task['status'],
                'result': task['result'],
                'worker_server': task.get('worker_server')
            }
        logger.warning(f"Requested status for non-existent task: {task_id}")
        return None

    async def get_worker_status(self, task_id: str) -> Optional[dict]:
        """
        通过HTTP从工作进程获取详细状态

        Args:
            task_id: 任务ID

        Returns:
            从工作进程获取的详细状态，如果无法获取则返回None
        """
        task = self.tasks.get(task_id)
        if not task or not task.get('worker_server'):
            logger.warning(
                f"Cannot get worker status: task {task_id} not found or worker server not ready")
            return None

        try:
            worker_url = f"{task['worker_server']}/status"
            logger.debug(f"Requesting status from worker at {worker_url}")

            if not self.client_session:
                self.client_session = aiohttp.ClientSession()

            async with self.client_session.get(worker_url, timeout=2) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received worker status for task {task_id}")
                    return data
                else:
                    logger.warning(
                        f"Failed to get worker status: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(
                f"Error getting worker status for task {task_id}: {e}", exc_info=True)
            return None

    async def control_worker(self, task_id: str, action: str) -> bool:
        """
        发送控制命令到工作进程

        Args:
            task_id: 任务ID
            action: 控制动作 (pause, resume, etc)

        Returns:
            操作是否成功
        """
        task = self.tasks.get(task_id)
        if not task or not task.get('worker_server'):
            logger.warning(
                f"Cannot control worker: task {task_id} not found or worker server not ready")
            return False

        try:
            worker_url = f"{task['worker_server']}/control"
            logger.info(
                f"Sending control action '{action}' to worker at {worker_url}")

            if not self.client_session:
                self.client_session = aiohttp.ClientSession()

            async with self.client_session.post(
                worker_url,
                json={"action": action},
                timeout=2
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(
                        f"Control action '{action}' for task {task_id} succeeded: {data}")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(
                        f"Control action '{action}' failed: HTTP {response.status}, {error_text}")
                    return False
        except Exception as e:
            logger.error(
                f"Error sending control action to worker for task {task_id}: {e}", exc_info=True)
            return False

    def list_tasks(self) -> Dict[str, dict]:
        """
        List all tasks and their statuses.

        Returns:
            Dictionary of task IDs to task statuses
        """
        # 返回所有任务状态的副本，不包含进程对象
        return {
            task_id: {
                'task_id': task_info['task_id'],
                'task_type': task_info['task_type'],
                'status': task_info['status'],
                'result': task_info['result'],
                'worker_server': task_info.get('worker_server')
            }
            for task_id, task_info in self.tasks.items()
        }

    async def terminate_worker_via_http(self, task_id: str) -> bool:
        """
        通过HTTP接口终止工作进程

        Args:
            task_id: 任务ID

        Returns:
            是否成功发送终止请求
        """
        task = self.tasks.get(task_id)
        if not task or not task.get('worker_server'):
            logger.warning(
                f"Cannot terminate via HTTP: task {task_id} not found or worker server not ready")
            return False

        try:
            worker_url = f"{task['worker_server']}/terminate"
            logger.info(f"Sending terminate request to worker at {worker_url}")

            if not self.client_session:
                self.client_session = aiohttp.ClientSession()

            async with self.client_session.post(worker_url, timeout=2) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(
                        f"Terminate request for task {task_id} succeeded: {data}")
                    # 更新任务状态
                    self.tasks[task_id]['status'] = 'terminating'
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(
                        f"Terminate request failed: HTTP {response.status}, {error_text}")
                    return False
        except Exception as e:
            logger.error(
                f"Error sending terminate request to worker for task {task_id}: {e}", exc_info=True)
            return False

    def terminate_task(self, task_id: str) -> bool:
        """
        Terminate a running task.

        Args:
            task_id: UUID of the task

        Returns:
            True if task was terminated, False otherwise
        """
        task = self.tasks.get(task_id)
        if task and 'worker' in task:
            worker = task['worker']
            try:
                # 检查进程是否仍在运行
                worker_pid = worker.pid
                if worker.is_alive():
                    logger.info(
                        f"Terminating worker process for task {task_id} (PID: {worker_pid})")
                    worker.terminate()  # 强制终止进程

                # 更新任务状态
                self.tasks[task_id]['status'] = 'terminated'
                logger.info(f"Task {task_id} terminated successfully")
                return True
            except Exception as e:
                logger.error(
                    f"Error terminating task {task_id}: {e}", exc_info=True)
                return False

        logger.warning(f"Attempt to terminate non-existent task: {task_id}")
        return False

    async def shutdown(self):
        """关闭任务管理器，终止所有任务"""
        logger.info("Initiating task manager shutdown...")

        # 设置停止事件，通知监控任务退出
        self.stop_event.set()
        logger.info("Stop event set for monitor task")

        # 如果监控任务存在，等待它结束
        if self.monitor_task:
            try:
                logger.info("Waiting for monitor task to complete...")
                await asyncio.wait_for(self.monitor_task, timeout=2.0)
                logger.info("Monitor task completed cleanly")
            except asyncio.TimeoutError:
                logger.warning(
                    "Monitor task took too long to shutdown, forcing cancel")
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    logger.info("Monitor task cancelled")

        # 尝试通过HTTP优雅地终止工作进程
        for task_id, task_info in list(self.tasks.items()):
            if task_info.get('status') in ['initialized', 'running'] and task_info.get('worker_server'):
                logger.info(
                    f"Attempting graceful shutdown of task {task_id} via HTTP")
                try:
                    success = await self.terminate_worker_via_http(task_id)
                    if success:
                        # 给工作进程一点时间来处理终止请求
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(
                        f"Error during graceful shutdown of task {task_id}: {e}")

        # 然后强制终止所有仍在运行的任务
        active_tasks = [
            task_id for task_id, task_info in self.tasks.items()
            if task_info.get('status') in ['initialized', 'running', 'terminating']
        ]

        if active_tasks:
            logger.info(
                f"Forcefully terminating {len(active_tasks)} active tasks")
            for task_id in active_tasks:
                self.terminate_task(task_id)
        else:
            logger.info("No active tasks to terminate")

        # 关闭aiohttp客户端会话
        if self.client_session:
            await self.client_session.close()
            logger.info("HTTP client session closed")

        # 清理队列
        try:
            # macOS不支持multiprocessing.Queue.qsize()，因此使用try/except处理
            queue_size = "unknown"
            try:
                if hasattr(self.status_queue, 'qsize'):
                    queue_size = self.status_queue.qsize()
            except NotImplementedError:
                # macOS上qsize()不可用
                pass

            logger.info(f"Clearing status queue (approx. size: {queue_size})")
            # 尝试清空队列，但不必太努力
            try:
                while not self.status_queue.empty():
                    self.status_queue.get_nowait()
            except Exception as e:
                logger.warning(f"Could not completely clear queue: {e}")
        except Exception as e:
            logger.error(f"Error during queue cleanup: {e}")

        logger.info("Task manager shutdown complete")
