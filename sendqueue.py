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
base_url = config.get_config('base_url')


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
        if hasattr(self, 'initialized'):
            return
        self.initialized = True
        self.expeired_minutes = 28
        self.expeired_time = None
        self.wxid = config.get_config('bot_wxid')
        self._local = threading.local()
        self.client = Client() # 初始化client对象, 用于获取token, TEST

    def __enter__(self, db='databases/queues.db'):
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(db)
            self._local.cursor = self._local.connection.cursor()
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        if hasattr(self._local, 'connection'):
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
        self._local.cursor.execute('''
            CREATE TABLE IF NOT EXISTS queues (
                id TEXT,
                is_consumed BOOLEAN DEFAULT 0,
                data TEXT,
                producer TEXT,
                p_time TEXT,
                consumer TEXT,
                c_time TEXT,
                timestamp INTEGER                          
                )''')
        self._local.connection.commit()

    def __produce__(self, m_id: str, data: dict, consumer: str, producer: str):
        """
        生产消息队列
        :param m_id: 消息id
        :param data: 消息内容
        :param producer: 消息生产者
        :param consumer: 消息消费者,api的完整地址 eg: http://127.0.0.1:9999/text
        :return:
        """
        data_string = json.dumps(data, ensure_ascii=False)

        record = {
            'id': m_id,
            'data': data_string,
            'producer': producer,
            'p_time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            'consumer': consumer,
            'c_time': '',
            'timestamp': time.time().__int__()
        }
        try:
            self._local.cursor.execute('''
            INSERT INTO queues (id, data, producer, p_time, consumer, c_time, timestamp) VALUES (:id, :data, :producer, :p_time, :consumer, :c_time, :timestamp)
            ''', record)
            self._local.connection.commit()
        except Exception as e:
            log.error(f'生产消息队列失败: {e}')

    def __consume__(self):
        """
        消费消息队列
        :return:
        """
        # 创建新的数据库连接
        with sqlite3.connect('databases/queues.db') as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                SELECT * FROM queues WHERE is_consumed = 0 ORDER BY timestamp ASC LIMIT 1
                ''')
                record = cursor.fetchone()
                if record:
                    token = self.client._check_token()
                    if not token:
                        log.error(f'获取token失败')
                        return None
                    headers = {
                        "content-type": "application/x-www-form-urlencoded; charset=utf-8",
                        'Authorization': f'Bearer {token}',
                    }
                    r = requests.post(
                        url=record[5],
                        data=json.loads(record[2]),
                        headers=headers,
                        timeout=30
                    )
                    response.raise_for_status()  # 如果响应状态码指示错误，将抛出HTTPError异常
                    if r.status_code != 200:
                        log.error(f"发送消息失败: {response.content.decode('utf-8')}")
                        return -1
                    # print(r.status_code, url)
                    c_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    cursor.execute('''
                    UPDATE queues SET is_consumed = 1, c_time = ? WHERE id = ?
                    ''', (c_time, record[0]))
                    conn.commit()
                    return response.content.decode('utf-8')
            except Exception as e:
                log.error(f'消费消息队列失败: {e}-{record[5] if record else ""}')
                return None

    def send_text(self, m_id: str, msg: str, receiver: str, aters: str = '', producer: str = 'main'):
        data = {
                "friend_id": receiver,
                "message": content,
                "remark": aters,
                "content_type": 1
        }
        self.__produce__(m_id, data, base_url + 'send_message_250514.html', producer)

    def send_image(self, m_id: str, img_path: str, receiver: str, producer: str = 'main'):
        try:
            data={
                "friend_id": receiver,
                "message": img_path,
                "content_type": 2
            }
            self.__produce__(m_id, data, base_url +'send_message_250514.html', producer)
        except Exception as e:
            self.send_text(m_id, f'{img_path}图片发送失败', receiver)

    def send_file(self, m_id: str, file_content: str, receiver: str, producer: str = 'main'):
        pass

    def send_rich_text(self, m_id: str, des: str, thumb: str, title: str, url: str, receiver: str, producer: str ='main'):
        data = {
                "friend_id": receiver,
                "message": json.dumps({
                    "des": des,
                    "thumb": thumb,
                    "title": title,
                    "url": url
                }),
                "content_type": 6,
            }
        self.__produce__(m_id, data, base_url +'send_message_250514.html', producer)
 


if __name__ == '__main__':
    db = QueueDB()
    db.__enter__()
    db.__create_table__()
    print('Done!')
