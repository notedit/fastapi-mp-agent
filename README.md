# aiohttp异步多进程任务处理服务

一个使用aiohttp作为HTTP服务器、asyncio处理异步任务监控、multiprocessing.Process处理CPU密集型工作的多进程服务。每个工作进程启动自己的HTTP服务器，用于接收主进程的控制请求。

## 功能

- 接收HTTP请求并启动长时间运行的任务
- 每个任务在单独的进程中运行
- 每个工作进程启动自己的HTTP服务器，用于接收控制命令
- 使用asyncio处理主服务器的异步逻辑
- 使用Python multiprocessing进行进程间通信
- 支持查询任务状态、列出所有任务和终止任务
- 支持暂停和恢复任务执行
- 定期（每10秒）在日志中打印所有任务及其状态
- 支持多种任务类型，包括CPU密集型任务

## 技术特点

- 使用aiohttp作为异步Web服务器
- 每个工作进程有自己的aiohttp服务器实例，在随机可用端口上运行
- 通过HTTP接口实现进程间通信，提供更丰富的交互功能
- 使用asyncio处理主服务器的事件循环和异步任务
- 使用multiprocessing.Process创建独立工作进程执行CPU密集型任务
- 通过multiprocessing.Queue进行基本进程间通信
- 异步任务状态监控实时更新任务状态
- 支持通过HTTP接口优雅地终止任务
- 优雅的应用关闭，确保所有资源被正确释放

## 设计思路

该应用结合了asyncio和multiprocessing的优势：

1. **主服务进程（aiohttp）**：使用asyncio处理所有HTTP请求和内部事件循环
2. **异步监控**：使用asyncio协程监控所有工作进程的状态
3. **工作进程（multiprocessing）**：使用multiprocessing.Process在独立进程中执行CPU密集型任务
4. **工作进程HTTP服务器**：每个工作进程启动自己的aiohttp服务器，用于接收控制命令
5. **双重进程间通信**：
   - 通过multiprocessing.Queue进行快速状态更新
   - 通过HTTP接口进行丰富的交互控制

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
- `GET /tasks/{task_id}?detail=true` - 获取任务的详细状态（从工作进程HTTP服务器获取）
- `POST /tasks/{task_id}/control` - 控制任务（暂停/恢复等）
- `DELETE /tasks/{task_id}` - 立即终止任务（强制）
- `DELETE /tasks/{task_id}?use_http=true` - 优雅地终止任务（通过HTTP请求）

## 支持的任务类型

1. `process_data` - 数据处理任务（IO密集型）
2. `generate_report` - 报告生成任务（IO密集型）
3. `cpu_intensive` - CPU密集型计算任务

## 工作进程HTTP端点

每个工作进程启动的HTTP服务器提供以下端点：

- `GET /status` - 获取工作进程的详细状态
- `POST /control` - 接收控制命令（如暂停/恢复）
- `POST /terminate` - 接收终止请求

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
  -d '{"task_type": "cpu_intensive", "task_data": {"complexity": 2000000, "batches": 5}}'
```

暂停一个正在运行的任务:

```bash
curl -X POST http://localhost:8000/tasks/{task_id}/control \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'
```

恢复一个已暂停的任务:

```bash
curl -X POST http://localhost:8000/tasks/{task_id}/control \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'
```

优雅地终止任务:

```bash
curl -X DELETE "http://localhost:8000/tasks/{task_id}?use_http=true"
```
