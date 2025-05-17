#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from time import sleep
from typing import Optional

import requests
from config.config import Config

logging.basicConfig(
    level="DEBUG",
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class Client:
    def __init__(self) -> None:
        self.config = Config()
        self.base_url = self.config.get_config("base_url")
        self.wxid = self.config.get_config("bot_wxid")
        self.LOG = logging.getLogger("Bot")
        self._token = self.config.get_config("token")

    def _check_token(self):
        """检查token是否过期，过期则重新获取"""
        return self._token

    def send_text(self, content: str, receiver: str, aters: Optional[str] = ""):
        """发送消息"""
        token = self._check_token()
        if not token:
            self.LOG.error("获取token失败")
            return -1

        try:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                "Authorization": f"Bearer {token}",
            }
            data = {
                "friend_id": receiver,
                "message": content,
                "remark": aters,
                "content_type": 1,
            }
            response = requests.post(
                self.base_url + "send_message_250514.html",
                headers=headers,
                data=data,
                timeout=30,
            )
            response.raise_for_status()  # 如果响应状态码指示错误，将抛出HTTPError异常
            return response.content.decode("utf-8")  # 返回解码后的响应内容
        except requests.exceptions.RequestException as e:
            error_message = "HTTP Request failed: {}".format(e)
            print(error_message)
            return error_message  # 将错误信息赋值给变量并返回

    def send_image(self, path: str = "", receiver: str = ""):
        """发送图片"""
        token = self._check_token()
        if not token:
            self.LOG.error("获取token失败")
            return -1

        try:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                "Authorization": f"Bearer {token}",
            }
            data = {"friend_id": receiver, "message": path, "content_type": 2}
            response = requests.post(
                self.base_url + "send_message_250514.html",
                headers=headers,
                data=data,
                timeout=30,
            )
            response.raise_for_status()  # 如果响应状态码指示错误，将抛出HTTPError异常
            return response.content.decode("utf-8")  # 返回解码后的响应内容
        except requests.exceptions.RequestException as e:
            error_message = "HTTP Request failed: {}".format(e)
            print(error_message)
            return error_message  # 将错误信息赋值给变量并返回

    def send_rich_text(self, des: str, thumb: str, title: str, url: str, receiver: str):
        """发送富文本消息"""
        token = self._check_token()
        if not token:
            self.LOG.error("获取token失败")
            return -1

        try:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                "Authorization": f"Bearer {token}",
            }
            data = {
                "friend_id": receiver,
                "message": json.dumps(
                    {"des": des, "thumb": thumb, "title": title, "url": url}
                ),
                "content_type": 6,
            }
            response = requests.post(
                self.base_url + "send_message_250514.html",
                headers=headers,
                data=data,
                timeout=30,
            )
            response.raise_for_status()  # 如果响应状态码指示错误，将抛出HTTPError异常
            return response.content.decode("utf-8")  # 返回解码后的响应内容
        except requests.exceptions.RequestException as e:
            error_message = "HTTP Request failed: {}".format(e)
            print(error_message)
            return error_message  # 将错误信息赋值给变量并返回

    def send_app(self, xml: str, receiver: str, type: int = 49):
        """发送应用消息
        Args:
            xml (str): 应用消息的xml内容
            receiver (str): 接收者wxid
            type (int): 消息类型，默认为49
        Returns:
            int: 0表示成功，-1表示失败
        """
        token = self._check_token()
        if not token:
            self.LOG.error("获取token失败")
            return -1

        try:
            url = f"{self.base_api}/Msg/SendApp"
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                "Authorization": f"Bearer {token}",
            }
            data = {"ToWxid": receiver, "Type": type, "Wxid": self.wxid, "Xml": xml}

            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                data = response.json()
                if data.get("Success"):
                    # print(data)
                    return 0
                else:
                    self.LOG.error(f"发送应用消息失败: {data.get('Message')}")
                    return -1
            return -1
        except Exception as e:
            self.LOG.error(f"发送应用消息失败: {e}")
            return -1

    def send_file(self, content: str, receiver: str):
        """发送CDN文件
        Args:
            content (str): 收到文件消息xml
            receiver (str): 接收者wxid
        Returns:
            int: 0表示成功，-1表示失败
        """
        token = self._check_token()
        if not token:
            self.LOG.error("获取token失败")
            return -1
        # TODO: 实现发送CDN文件

    def down_file(self, msg_id) -> str:
        """下载文件"""
        token = self._check_token()
        if not token:
            self.LOG.error("获取token失败")
            return ""

        def trigger_download_file(msg_id):
            """触发下载文件"""
            try:
                headers = {
                    "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                    "Authorization": f"Bearer {token}",
                }
                data = {"msg_svr_id": msg_id}
                response = requests.post(
                    self.base_url + "trigger_download_file.html",
                    headers=headers,
                    data=data,
                    timeout=30,
                )
                response.raise_for_status()  # 如果响应状态码指示错误，将抛出HTTPError异常
                return response.content.decode("utf-8")  # 返回解码后的响应内容
            except requests.exceptions.RequestException as e:
                error_message = "HTTP Request failed: {}".format(e)
                print(error_message)
                return error_message  # 将错误信息赋值给变量并返回

        for _ in range(10):
            res = trigger_download_file(msg_id)
            res = json.loads(res)
            print(res)
            if res.get("success"):
                sleep(3)
            elif res.get("message") == "这条消息不是文件类型！":
                return ""
            elif res.get("message") == "文件已下载":
                return res.get("url")


if __name__ == "__main__":
    c = Client()
    # r = c.send_rich_text(des="❗戳我看看今天吃啥👉", thumb="http://b0.wcr222.top/2024/06/29/62b8d90380a449919e90d235d6109586.png", title="外卖红包天天领🧧", url="https://my-bucket-8ynxqsg-1305062151.cos-website.ap-guangzhou.myqcloud.com/uviewui/waimai668.html", receiver="yoin007")
    # r = c.down_file("9098001182538937472")
    r = c.send_image(
        "http://b1.wcr222.top/0e2c4df62a691f11/2025/05/14/41658fc8b63e4172a4f10be967244210.jpg",
        "yoin007",
    )
    print(r)
