#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from time import sleep
from typing import Optional, Dict, Any, Union

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
        self.static_url = self.config.get_config("static_url")

    def _check_token(self):
        """检查token是否过期，过期则重新获取"""
        return self._token

    def _make_request(self, endpoint: str, data: Dict[str, Any], params: Dict[str, Any] = None) -> Union[str, int]:
        """通用HTTP请求方法
        
        Args:
            endpoint: API端点
            data: 请求数据
            params: URL参数
            
        Returns:
            str: 成功时返回响应内容
            int: 失败时返回-1
        """
        token = self._check_token()
        if not token:
            self.LOG.error("获取token失败")
            return -1

        try:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                "Authorization": f"Bearer {token}",
            }
            
            response = requests.post(
                self.base_url + endpoint,
                headers=headers,
                data=data,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.content.decode("utf-8")
        except requests.exceptions.RequestException as e:
            error_message = f"HTTP Request failed: {e}"
            self.LOG.error(error_message)
            print(error_message)
            return error_message

    def send_text(self, content: str, receiver: str, aters: Optional[str] = ""):
        """发送文本消息"""
        data = {
            "friend_id": receiver,
            "message": content,
            "remark": aters,
            "content_type": 1,
        }
        return self._make_request("send_message_250514.html", data)

    def send_image(self, path: str = "", receiver: str = ""):
        """发送图片消息"""
        # 处理path
        if not (path.startswith("http://") or path.startswith("https://")):
            path = self.static_url + path

        data = {
            "friend_id": receiver,
            "message": path,
            "content_type": 2
        }
        return self._make_request("send_message_250514.html", data)

    def send_rich_text(self, card_dict: dict, receiver: str):
        """发送富文本消息"""
        data = {
            "friend_id": receiver,
            "message": json.dumps(card_dict),
            "content_type": 6,
        }
        return self._make_request("send_message_250514.html", data)

    def send_app(self, xml_dict: dict, receiver: str, type: int = 13):
        """发送应用消息
        Args:
            xml_dict (dict): xml
            receiver (str): 接收者wxid
            type (int): 消息类型，默认13为
        Returns:
            int: 0表示成功，-1表示失败
        """
        data = {
            "friend_id": receiver,
            "content_type": type,
            "message": json.dumps(xml_dict),
        }
        return self._make_request("send_message_250514.html", data)

    def send_file(self, file_dict, receiver: str):
        """发送文件
        Args:
            file_dict (dict or str): 文件信息字典或文件路径
            receiver (str): 接收者wxid
        Returns:
            int: 0表示成功，-1表示失败
        """
        # 处理字符串类型的参数
        if isinstance(file_dict, str):
            file_path = file_dict
            file_name = file_path.split('/')[-1]
            file_dict = {
                "name": file_name,
                "url": file_path
            }
            
        # 处理path
        if not (file_dict.get("url", "").startswith("http://") or file_dict.get("url", "").startswith("https://")):
            file_dict["url"] = self.static_url + file_dict.get("url")
        print(file_dict)
        data = {
            "friend_id": receiver,
            "content_type": "8",
            "message": json.dumps(file_dict),
        }
        return self._make_request("send_message_250514.html", data)

    def down_file(self, msg_id) -> str:
        """下载文件"""
        token = self._check_token()
        if not token:
            self.LOG.error("获取token失败")
            return ""

        def trigger_download_file(msg_id):
            """触发下载文件"""
            data = {"msg_svr_id": msg_id}
            return self._make_request("trigger_download_file.html", data)

        for _ in range(10):
            res = trigger_download_file(msg_id)
            try:
                res_json = json.loads(res)
                print(res_json)
                if res_json.get("success"):
                    sleep(3)
                elif res_json.get("message") == "这条消息不是文件类型！":
                    return ""
                elif res_json.get("message") == "文件已下载":
                    return res_json.get("url")
            except (json.JSONDecodeError, TypeError):
                self.LOG.error(f"解析响应失败: {res}")
                return ""
        return ""
    
    def contact_info(self, content_type=0):
        """获取联系人信息
        Args:
            content_type (int): 0通讯录 1群聊
        Returns:
            dict: 包含所有联系人信息的字典
        """
        all_contacts = []
        current_page = 1
        total_page = 1
        
        # 循环获取所有页面的联系人信息
        while current_page <= total_page:
            params = {
                "page": current_page,
                "type": content_type,
            }
            response = self._make_request("get_contact_info.html", {}, params)
            
            try:
                # 解析响应数据
                res_data = json.loads(response)
                if not res_data.get("success"):
                    self.LOG.error(f"获取联系人信息失败: {res_data.get('message')}")
                    break
                
                # 提取联系人列表并合并
                contacts_list = res_data.get("data", {}).get("list", [])
                all_contacts.extend(contacts_list)
                
                # 更新总页数和当前页码
                page_info = res_data.get("data", {}).get("page", {})
                total_page = page_info.get("total_page", 1)
                current_page += 1
                
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                self.LOG.error(f"解析联系人信息失败: {e}, 响应内容: {response}")
                break
        
        # 返回包含所有联系人的结果
        return all_contacts
        # return {
        #     "success": True,
        #     "message": "获取所有联系人信息成功",
        #     "data": {
        #         "list": all_contacts,
        #         "total": len(all_contacts)
        #     }
        # }


if __name__ == "__main__":
    # static_url = Config().get_config('static_url')
    c = Client()
    r = c.send_text('今天好热啊', "57477785315@chatroom", 'yoin007')

    print(r)
