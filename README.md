# aiohttp Multi-Process Agent

一个使用aiohttp作为HTTP服务器，uActor作为工作进程的多进程服务。

## 功能

- 接收HTTP请求并启动长时间运行的任务
- 每个任务在单独的进程中运行
- 使用uActor的Actor模型进行进程间通信
- 支持查询任务状态、列出所有任务和终止任务
- 定期（每10秒）在日志中打印所有任务及其状态
- 支持多种任务类型，包括CPU密集型任务

## 设置环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 运行应用

```bash
# 从虚拟环境中运行
python run.py
```

应用将在 http://localhost:8000 上启动。

## API端点

- `POST /tasks` - 创建新任务
- `GET /tasks` - 列出所有任务
- `GET /tasks/{task_id}` - 获取特定任务的状态
- `DELETE /tasks/{task_id}` - 终止任务

## 支持的任务类型

1. `process_data` - 数据处理任务（IO密集型）
2. `generate_report` - 报告生成任务（IO密集型）
3. `cpu_intensive` - CPU密集型计算任务

## 示例请求

创建数据处理任务:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "process_data", "task_data": {"items": [1, 2, 3, 4, 5]}}'
```

创建报告生成任务:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "generate_report", "task_data": {"report_type": "detailed"}}'
```

创建CPU密集型任务:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type": "cpu_intensive", "task_data": {"iterations": 2000000, "batches": 5}}'
```
