# _*_ coding: utf-8 _*_
# @Time: 2024/09/23 18:27
# @Author: Tech_T


import json
import base64
import requests
import sqlite3
import time
from datetime import datetime, timedelta
import threading

from config.log import LogConfig
from config.config import Config
from client import Client

log = LogConfig().get_logger()
config = Config()
base_url = config.get_config("base_url")
static_url = config.get_config("static_url")


class QueueDB:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return
        self.initialized = True
        self.expeired_minutes = 28
        self.expeired_time = None
        self.wxid = config.get_config("bot_wxid")
        self._local = threading.local()
        self.client = Client()  # 初始化client对象, 用于获取token, TEST

    def __enter__(self, db="databases/queues.db"):
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(db)
            self._local.cursor = self._local.connection.cursor()
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection
            del self._local.cursor

    def __create_table__(self):
        """
        创建队列表
        producer: 消息生产者
        consumer: 消息消费者
        p_time: 消息生产时间
        c_time: 消息消费时间
        """
        self._local.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS queues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                is_consumed BOOLEAN DEFAULT 0,
                msg_id TEXT,
                data TEXT,
                producer TEXT,
                p_time TEXT,
                consumer TEXT,
                c_time TEXT,
                timestamp INTEGER        
                )"""
        )
        self._local.connection.commit()

    def __produce__(self, data: dict, consumer: str, producer: str, msg_id: str = ""):
        """
        生产消息队列
        :param msg_id: 对应微信消息的msg_id
        :param data: 消息内容
        :param producer: 消息生产者
        :param consumer: 消息消费者,api
        :return:
        """
        data_string = json.dumps(data, ensure_ascii=False)

        record = {
            "msg_id": msg_id,
            "data": data_string,
            "producer": producer,
            "p_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "consumer": consumer,
            "c_time": "",
            "timestamp": time.time().__int__(),
        }
        try:
            self._local.cursor.execute(
                """
            INSERT INTO queues (msg_id, data, producer, p_time, consumer, c_time, timestamp) VALUES (:msg_id, :data, :producer, :p_time, :consumer, :c_time, :timestamp)
            """,
                record,
            )
            self._local.connection.commit()
        except Exception as e:
            log.error(f"生产消息队列失败: {e}")

    def __consume__(self):
        """
        消费消息队列
        :return:
        """
        # 创建新的数据库连接
        with sqlite3.connect("databases/queues.db") as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                SELECT * FROM queues WHERE is_consumed = 0 ORDER BY timestamp ASC LIMIT 1
                """
                )
                record = cursor.fetchone()
                if record:
                    token = self.client._check_token()
                    if not token:
                        log.error(f"获取token失败")
                        return None
                    headers = {
                        "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                        "Authorization": f"Bearer {token}",
                    }
                    r = requests.post(
                        url=record[6],
                        data=json.loads(record[3]),
                        headers=headers,
                        timeout=30,
                    )
                    r.raise_for_status()  # 修改这里：使用r而不是response
                    if r.status_code != 200:
                        log.error(
                            f"发送消息失败: {r.content.decode('utf-8')}"
                        )  # 修改这里：使用r而不是response
                        return -1
                    # print(r.status_code, url)
                    c_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    cursor.execute(
                        """
                    UPDATE queues SET is_consumed = 1, c_time = ? WHERE id = ?
                    """,
                        (c_time, record[0]),
                    )
                    conn.commit()
                    return r.content.decode("utf-8")  # 修改这里：使用r而不是response
            except Exception as e:
                log.error(f'消费消息队列失败: {e}-{record[5] if record else ""}')
                return None

def send_text(content: str, receiver: str, aters: str="", producer: str = "main"):
    """发送文本消息"""
    data = {
        "friend_id": receiver,
        "message": content,
        "remark": aters,
        "content_type": 1,
    }
    with QueueDB() as queue:  # 使用上下文管理器
        queue.__produce__(data, base_url + "send_message_250514.html", producer)

def send_image(path: str = "", receiver: str = "", producer: str = "main"):
    """发送图片消息"""
    # 处理path
    if not (path.startswith("http://") or path.startswith("https://")):
        path = static_url + path
    data = {
        "friend_id": receiver,
        "message": path,
        "content_type": 2
    }
    with QueueDB() as queue:  # 使用上下文管理器
        queue.__produce__(data, base_url + "send_message_250514.html", producer)

def send_file(file_dict, receiver: str = "", producer: str = "main"):
    """发送文件消息"""
    # 处理字符串类型的参数
    if isinstance(file_dict, str):
        file_path = file_dict
        file_name = file_path.split('/')[-1]
        file_dict = {
            "name": file_name,
            "url": file_path
        }
    # 处理path
    if not (file_dict.get('url', '').startswith("http://") or file_dict.get('url', '').startswith("https://")):
        file_dict['url'] = static_url + file_dict.get('url')
    data = {
        "friend_id": receiver,
        "content_type": "8",
        "message": json.dumps(file_dict),
    }
    with QueueDB() as queue:  # 使用上下文管理器
        queue.__produce__(data, base_url + "send_message_250514.html", producer)

def send_app_msg(xml_dict: dict, receiver: str, type: int = 13, producer: str = "main"):
    """发送应用消息"""
    data = {
        "friend_id": receiver,
        "content_type": type,
        "message": json.dumps(xml_dict),
    }
    with QueueDB() as queue:  # 使用上下文管理器
        queue.__produce__(data, base_url + "send_message_250514.html", producer)


if __name__ == "__main__":
    db = QueueDB()
    db.__enter__()
    db.__create_table__()
    print("Done!")
