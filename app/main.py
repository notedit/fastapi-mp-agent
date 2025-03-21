"""Main aiohttp application module."""
import asyncio
import logging
from typing import Dict
from aiohttp import web
from app.routes import (
    create_task,
    list_tasks,
    get_task,
    terminate_task,
    task_manager
)

# 设置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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


async def start_background_tasks(app):
    """启动应用时开始定期任务"""
    app['task_printer'] = asyncio.create_task(print_tasks_status())


async def cleanup_background_tasks(app):
    """关闭应用时清理定期任务"""
    app['task_printer'].cancel()
    await app['task_printer']


def init_app():
    """初始化aiohttp应用"""
    app = web.Application()

    # 设置路由
    app.add_routes([
        web.post('/tasks', create_task),
        web.get('/tasks', list_tasks),
        web.get('/tasks/{task_id}', get_task),
        web.delete('/tasks/{task_id}', terminate_task),
    ])

    # 设置启动和关闭回调
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    return app


def run_app():
    """运行aiohttp应用"""
    app = init_app()
    web.run_app(app, host='0.0.0.0', port=8000)


if __name__ == "__main__":
    run_app()
