# _*_ coding: utf-8 _*_
# @Time : 2024/09/23 11:27
# @Author : Tech_T
# @python: 3.10.14

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import models
import re
import os
from wxmsg import WxMsg, MessageDB
from config.log import LogConfig
from config.config import Config
from models.manage.member import Member
import asyncio
from contextlib import asynccontextmanager
import random
from sendqueue import QueueDB, send_text
from models.task import task_start
from models.manage.manage import forward_msg

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
        asyncio.create_task(task_start()),  # 删除多余的逗号
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
# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.post("/")
async def root(request: Request):
    body = await request.json()
    print(body)
    msg = WxMsg(body)
    with MessageDB() as db:
        db.insert(msg.__to_dict__())
    log.info(msg.__str__())
    
    if not msg.is_self:
        forward_msg(msg.__to_dict__())
        reply, func, msg = trigger(msg)
        if reply:
            if len(msg.content)<50:
                aters = msg.sender if msg.is_group else ""
                send_text(reply, msg.roomid, aters)

        if func:
            trigger_func = getattr(models, func)
            if trigger_func:
                log.info(f"触发函数 {func}")
                asyncio.create_task(trigger_func(msg))
            else:
                log.warning(f"未找到函数 {func}, 请检查配置")


def trigger(msg):
    # TODO: 1. 触发事件 注意 对特定标签的 member 进行AI_content 生成
    # TODO: 2. 违禁词检测

    with Member() as m:
        rules = m.permission_info()
        if rules:
            for rule in rules:
                acitvate = rule[3]  # 是否禁用
                if acitvate == 0:
                    continue
                msg_type = rule[6] if rule[6] else "all"
                pattern = rule[7] if rule[7] else ""
                keywords = rule[8].split("/") if rule[8] else []
                reply = rule[11] if rule[11] else ""
                row = {
                    "func": rule[1] if rule[1] else "",
                    "blacklist": rule[4].split("/") if rule[4] else [],
                    "whitelist": rule[5].split("/") if rule[5] else [],
                    "type": msg_type,
                    "pattern": pattern,
                    "keywords": keywords,
                    "ai_flag": rule[9],
                    "need_at": rule[10] if rule[10] else 0,
                    "reply": reply,
                }
                if msg_type != "all" and str(msg_type) != str(msg.type):
                    continue
                if row["need_at"] and not msg.is_at:
                    continue
                if msg.roomid in row["blacklist"]:
                    continue
                if row["whitelist"] != ["all"] and msg.roomid not in row["whitelist"]:
                    continue
                if row["ai_flag"]:
                    msg.content = ai_content(msg.content, row["keywords"])
                if row['whitelist'] != ["all"] and msg.roomid in row["whitelist"]:
                    if not re.search(row["pattern"], msg.content, re.DOTALL):
                        continue
                    return row["reply"], row["func"], msg
                if row["whitelist"] == ["all"]:
                    if not re.search(row["pattern"], msg.content, re.DOTALL):
                        continue
                    return row["reply"], row["func"], msg
    return None, None, msg


def ai_content(content, keywords):
    # TODO: 1. 触发事件 注意 对特定标签的 member 进行AI_content 生成
    return content


if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=14600, reload=True)  # dev
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
