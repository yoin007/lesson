# _*_ coding: utf-8 _*_
# @Time     : 2025/5/28 19:57
# @Author   : Tech_T

from openai import OpenAI
from config.config import Config
import datetime


class ZPAI:
    def __init__(self):
        self.api_key = Config().get_config("deepseek_key")
        self.base_url = "https://api.deepseek.com"

    def ai_remind_text(self, text):
        # 调用Z-PAI的API，实现提醒功能
        now = datetime.datetime.now().strftime("%H:%M:%S")
        today = datetime.datetime.now().strftime("%Y%m%d")
        week_day = int(datetime.datetime.now().weekday()) + 1
        propmt = f"{text}\n把上面这句话按照下面的指定格式的字符串返回给我，请只返回格式化的字符串，不要其他内容。\n指定格式:定时-提醒日期和时间-提醒内容\n提醒日期和时间的格式为:YYYYMMDD HH:MM:SS\n当前日期是{today},当前时间是{now}，本周的第{str(week_day)}天，请以当前日期和当前时间正确计算提醒日期和时间，尤其是关于星期(周几)的计算(每周从周1开始，一周7天)"

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": propmt},
            ],
            max_tokens=1024,
            temperature=0.7,
            stream=False,
        )

        text = str(response.choices[0].message.content)
        return text
