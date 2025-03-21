"""API routes for the aiohttp application."""
import json
from aiohttp import web
from uuid import UUID
from typing import Dict, Any
from app.task_manager import TaskManager

# 创建任务管理器实例
task_manager = TaskManager()


async def create_task(request: web.Request) -> web.Response:
    """
    创建新任务并在独立进程中运行
    """
    try:
        data = await request.json()
        task_type = data.get('task_type')
        task_data = data.get('task_data', {})

        if not task_type:
            return web.json_response(
                {"error": "task_type is required"},
                status=400
            )

        # 创建新任务
        task_id = task_manager.create_task(task_type, task_data)

        # 获取任务初始状态
        status = task_manager.get_task_status(task_id)
        if not status:
            return web.json_response(
                {"error": "Failed to create task"},
                status=500
            )

        return web.json_response(status, status=201)

    except json.JSONDecodeError:
        return web.json_response(
            {"error": "Invalid JSON"},
            status=400
        )
    except Exception as e:
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def list_tasks(request: web.Request) -> web.Response:
    """
    列出所有任务及其状态
    """
    tasks = task_manager.list_tasks()
    return web.json_response({"tasks": tasks})


async def get_task(request: web.Request) -> web.Response:
    """
    获取特定任务的状态
    """
    task_id = request.match_info.get('task_id')

    status = task_manager.get_task_status(task_id)
    if not status:
        return web.json_response(
            {"error": f"Task {task_id} not found"},
            status=404
        )

    return web.json_response(status)


async def terminate_task(request: web.Request) -> web.Response:
    """
    终止运行中的任务
    """
    task_id = request.match_info.get('task_id')

    success = task_manager.terminate_task(task_id)
    if not success:
        return web.json_response(
            {"error": f"Task {task_id} not found or could not be terminated"},
            status=404
        )

    return web.json_response({
        "status": "success",
        "message": f"Task {task_id} terminated"
    })
