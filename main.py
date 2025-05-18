# _*_ coding: utf-8 _*_
# @Time : 2024/09/23 11:27
# @Author : Tech_T
# @python: 3.10.14

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from wxmsg import WxMsg, MessageDB
from config.log import LogConfig
from config.config import Config
import asyncio
from contextlib import asynccontextmanager
import random
from sendqueue import QueueDB

log = LogConfig().get_logger()
config = Config()
timer_random = config.get_config("queue_timer_random")


async def consume_queue():
    while True:
        with QueueDB() as q:
            q.__consume__()
        await asyncio.sleep(
            random.randint(*timer_random)
        )  # 修改这里：使用timer_random而不是time_random


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时启动队列消费任务
    tasks = [
        asyncio.create_task(consume_queue()),
    ]

    try:
        yield
    finally:
        # 关闭时取消所有任务
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(lifespan=lifespan)

# 配置静态文件目录
# 确保static目录存在
static_dir = config.get_config("lesson_dir")
print(static_dir)
# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.post("/")
async def root(request: Request):
    body = await request.json()
    msg = WxMsg(body)
    with MessageDB() as db:
        db.insert(msg.__to_dict__())
    log.info(msg)


def trigger():
    # TODO: 触发事件 注意 对特定标签的 member 进行AI_content 生成
    pass


if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=14600, reload=True)  # dev
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
