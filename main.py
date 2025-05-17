# _*_ coding: utf-8 _*_
# @Time : 2024/09/23 11:27
# @Author : Tech_T
# @python: 3.10.14

import uvicorn
from fastapi import FastAPI, Request
from wxmsg import WxMsg, MessageDB
from config.log import LogConfig

app = FastAPI()
log = LogConfig().get_logger()


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
