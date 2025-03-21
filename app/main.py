"""Main FastAPI application module."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from app.models import TaskRequest, TaskResponse, TaskList
from app.task_manager import TaskManager
import asyncio
import logging
from typing import Dict

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FastAPI Multi-Process Agent",
    description="A service using FastAPI as HTTP server and uActor for long-running tasks",
    version="0.1.0",
)

# Create task manager
task_manager = TaskManager()

# 定期任务，每10秒打印所有任务状态


async def print_tasks_status():
    """定期打印所有任务状态的后台任务"""
    while True:
        tasks = task_manager.list_tasks()
        if tasks:
            logger.info(f"Current tasks ({len(tasks)}):")
            for task_id, task_info in tasks.items():
                logger.info(
                    f"Task ID: {task_id}, Type: {task_info['task_type']}, Status: {task_info['status']}")
        else:
            logger.info("No active tasks")

        # 等待10秒
        await asyncio.sleep(10)


@app.on_event("startup")
async def start_scheduler():
    """启动应用时开始定期任务"""
    asyncio.create_task(print_tasks_status())


@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(task_request: TaskRequest):
    """
    Create a new task that will run in a separate process.

    The task will be executed in a background process using uActor.
    """
    task_id = task_manager.create_task(
        task_request.task_type,
        task_request.task_data
    )

    # Return the initial status
    status = task_manager.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=500, detail="Failed to create task")

    return status


@app.get("/tasks", response_model=TaskList)
async def list_tasks():
    """
    List all tasks and their current statuses.
    """
    tasks = task_manager.list_tasks()
    return {"tasks": tasks}


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """
    Get the status of a specific task.
    """
    status = task_manager.get_task_status(task_id)
    if not status:
        raise HTTPException(
            status_code=404, detail=f"Task {task_id} not found")

    return status


@app.delete("/tasks/{task_id}", response_model=dict)
async def terminate_task(task_id: str):
    """
    Terminate a running task.
    """
    success = task_manager.terminate_task(task_id)
    if not success:
        raise HTTPException(
            status_code=404, detail=f"Task {task_id} not found or could not be terminated")

    return {"status": "success", "message": f"Task {task_id} terminated"}
