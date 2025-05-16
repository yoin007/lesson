# _*_ coding: utf-8 _*_
# @Time : 2024/09/23 11:27
# @Author : Tech_T
# @python: 3.10.14

import uvicorn
from fastapi import FastAPI, Request
from wxmsg import WxMsg

app = FastAPI()

@app.post('/')
async def root(request: Request):
    body = await request.json()
    print(body)  # test
    msg = WxMsg(body)
    print(msg)

if __name__ == "__main__":
    try:
        uvicorn.run('main:app', host='0.0.0.0', port=14600, reload=True)  # dev
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
