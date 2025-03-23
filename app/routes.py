"""API routes for the aiohttp application."""
import json
import logging
from aiohttp import web
from uuid import UUID
from typing import Dict, Any, List, Optional
from typing import Dict, Any
from app.task_manager import TaskManager

# 获取logger
logger = logging.getLogger(__name__)

# 创建任务管理器实例
task_manager = TaskManager()


async def create_task(request: web.Request) -> web.Response:
    """
    创建新任务并在独立进程中运行
    """
    client_ip = request.remote
    logger.info(f"Received task creation request from {client_ip}")

    try:
        data = await request.json()
        task_type = data.get('task_type')
        task_data = data.get('task_data', {})

        logger.debug(f"Task creation parameters - type: {task_type}")

        if not task_type:
            logger.warning("Task creation failed: missing task_type")
            return web.json_response(
                {"error": "task_type is required"},
                status=400
            )

        # 创建新任务
        task_id = task_manager.create_task(task_type, task_data)
        logger.info(f"Task created successfully with ID: {task_id}")

        # 获取任务初始状态
        status = task_manager.get_task_status(task_id)
        if not status:
            logger.error(f"Failed to get initial status for task {task_id}")
            return web.json_response(
                {"error": "Failed to create task"},
                status=500
            )

        return web.json_response(status, status=201)

    except json.JSONDecodeError:
        logger.warning(
            f"Invalid JSON in task creation request from {client_ip}")
        return web.json_response(
            {"error": "Invalid JSON"},
            status=400
        )
    except Exception as e:
        logger.error(f"Task creation error: {str(e)}", exc_info=True)
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def list_tasks(request: web.Request) -> web.Response:
    """
    列出所有任务及其状态
    """
    client_ip = request.remote
    logger.info(f"Received list tasks request from {client_ip}")

    tasks = task_manager.list_tasks()
    task_count = len(tasks) if tasks else 0
    logger.info(f"Returning list of {task_count} tasks")

    return web.json_response({"tasks": tasks})


async def get_task(request: web.Request) -> web.Response:
    """
    获取特定任务的状态
    """
    client_ip = request.remote
    task_id = request.match_info.get('task_id')
    logger.info(
        f"Received request from {client_ip} for task status: {task_id}")

    # 检查是否请求详细状态
    detail = request.query.get('detail', '').lower() == 'true'

    if detail:
        # 通过HTTP从工作进程获取详细状态
        status = await task_manager.get_worker_status(task_id)
        if status:
            logger.info(f"Returning detailed worker status for task {task_id}")
            return web.json_response(status)

    # 获取基本状态
    status = task_manager.get_task_status(task_id)
    if not status:
        logger.warning(f"Task {task_id} not found")
        return web.json_response(
            {"error": f"Task {task_id} not found"},
            status=404
        )

    logger.debug(
        f"Returning status for task {task_id}: {status.get('status')}")
    return web.json_response(status)


async def control_task(request: web.Request) -> web.Response:
    """
    控制任务执行（暂停/恢复等）
    """
    client_ip = request.remote
    task_id = request.match_info.get('task_id')

    try:
        data = await request.json()
        action = data.get('action')

        if not action:
            return web.json_response(
                {"error": "action parameter is required"},
                status=400
            )

        logger.info(
            f"Received control request from {client_ip} for task {task_id}: {action}")

        # 发送控制命令到工作进程
        success = await task_manager.control_worker(task_id, action)

        if success:
            return web.json_response({
                "success": True,
                "task_id": task_id,
                "action": action
            })
        else:
            return web.json_response(
                {"error": f"Failed to control task {task_id}"},
                status=404
            )

    except json.JSONDecodeError:
        return web.json_response(
            {"error": "Invalid JSON"},
            status=400
        )
    except Exception as e:
        logger.error(f"Error in control_task: {e}", exc_info=True)
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def terminate_task(request: web.Request) -> web.Response:
    """
    终止运行中的任务
    """
    client_ip = request.remote
    task_id = request.match_info.get('task_id')
    logger.info(
        f"Received request from {client_ip} to terminate task: {task_id}")

    # 检查是否优先使用HTTP终止
    use_http = request.query.get('use_http', '').lower() == 'true'

    if use_http:
        # 尝试通过HTTP终止
        success = await task_manager.terminate_worker_via_http(task_id)
        if success:
            logger.info(f"Task {task_id} termination initiated via HTTP")
            return web.json_response({
                "status": "terminating",
                "message": f"Task {task_id} termination initiated"
            })

    # 如果HTTP终止未启用或失败，尝试直接终止进程
    success = task_manager.terminate_task(task_id)
    if not success:
        logger.warning(
            f"Failed to terminate task {task_id}: not found or already terminated")
        return web.json_response(
            {"error": f"Task {task_id} not found or could not be terminated"},
            status=404
        )

    logger.info(f"Task {task_id} terminated successfully")
    return web.json_response({
        "status": "success",
        "message": f"Task {task_id} terminated"
    })


# 为应用创建路由表
def setup_routes(app: web.Application):
    """设置应用的路由"""
    app.router.add_post('/tasks', create_task)
    app.router.add_get('/tasks', list_tasks)
    app.router.add_get('/tasks/{task_id}', get_task)
    app.router.add_post('/tasks/{task_id}/control', control_task)
    app.router.add_delete('/tasks/{task_id}', terminate_task)

    logger.info("Routes configured")
    return app
