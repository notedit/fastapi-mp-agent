"""Main aiohttp application module."""
import asyncio
import logging
import os
import sys
from typing import Dict
from aiohttp import web
from app.routes import (
    task_manager,
    setup_routes
)


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
    """启动应用时开始定期任务和任务监控器"""
    # 启动任务状态打印器
    app['task_printer'] = asyncio.create_task(print_tasks_status())

    # 启动任务管理器的状态监控器
    app['task_monitor'] = await task_manager.start_monitor()
    logger.info("Task monitor started successfully")


async def cleanup_background_tasks(app):
    """关闭应用时清理定期任务和关闭任务管理器"""
    # 取消任务打印
    app['task_printer'].cancel()
    try:
        await app['task_printer']
    except asyncio.CancelledError:
        pass

    # 关闭任务管理器
    logger.info("Shutting down task manager...")
    await task_manager.shutdown()
    logger.info("Task manager shut down successfully")


def init_app():
    """初始化aiohttp应用"""
    logger.info("Initializing application...")
    app = web.Application()

    # 使用路由模块的setup_routes函数设置路由
    setup_routes(app)
    logger.info("Routes configured successfully")

    # 设置启动和关闭回调
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    logger.info("Application lifecycle hooks registered")

    return app


def run_app():
    """运行aiohttp应用"""
    # 打印系统信息
    logger.info("=" * 50)
    logger.info("Starting aiohttp Async Multi-Process Task Service")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Running on: {os.name} platform")
    logger.info(f"Process ID: {os.getpid()}")
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info("=" * 50)

    # 初始化应用
    logger.info("Building application...")
    app = init_app()

    # 运行应用
    logger.info("Starting web server on http://0.0.0.0:8000")
    web.run_app(app, host='0.0.0.0', port=8000,
                access_log_format='%a "%r" %s %b "%{Referer}i" "%{User-Agent}i" %Tfs')

    logger.info("Server shutdown complete")


if __name__ == "__main__":
    run_app()
