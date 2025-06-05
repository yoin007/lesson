# _*_ coding: utf-8 _*_
# @Time     : 2025/5/28 19:57
# @Author   : Tech_T

from openai import OpenAI
from config.config import Config
import datetime
import os
import time
import requests
from sendqueue import send_text


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


def one_day_English():
    # 原来是每日一句英语，但是api失效，更改为下面的每日一句
    url = "https://api.ahfi.cn/api/bsnts?type=text"
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.6045.160 Safari/537.36 "
    }
    # 发送GET请求
    response = requests.get(url, headers).text
    return response


def countdown_day(month, day):
    """
    日期倒计时函数
    :param target_date:
    :return:
    """
    # 获取当前日期
    today = datetime.datetime.now()

    # 设置高考日期为每年的6月7日
    college_entrance_exam_date = datetime.datetime(today.year, month, day)

    # 如果当前日期已经超过了今年的高考日期，则计算明年的高考日期
    if today > college_entrance_exam_date:
        college_entrance_exam_date = college_entrance_exam_date.replace(
            year=today.year + 1
        )

    # 计算倒计时天数
    delta = college_entrance_exam_date - today
    days_to_go = delta.days
    return days_to_go


def gk_countdown():
    """
    高考倒计时，每天一句英语
    :return:
    """
    year = datetime.datetime.now().year
    tips = one_day_English()

    gk_days = countdown_day(6, 7)
    zk_days = countdown_day(6, 13)
    if gk_days > 0:
        gk_tips = f"距离{str(year)}年高考还有{gk_days}天!"
    elif gk_days == 0:
        gk_tips = f"今日高考，祝考试顺利，金榜题名！"
    if zk_days > 0:
        zk_tips = f"距离{str(year)}年中考还有{zk_days}天!"
    elif zk_days == 0:
        zk_tips = f"今日中考，祝考试顺利，金榜题名！"

    msg = f"{tips}"
    msg = msg + "\n" + gk_tips + "\n" + zk_tips
    for r in Config().get_config("gk_remind"):
        send_text(msg, r)
        time.sleep(1)


def ju_pai(words):
    timestamp = int(time.time())
    static_dir = Config().get_config("lesson_dir")
    pic = os.path.join(static_dir, "temp", f"{timestamp}.png")
    headers = {
        "authority": "api.ahfi.cn",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.6045.160 Safari/537.36 ",
    }
    from urllib.parse import quote

    encoded_words = quote(f"欢迎{words}入群!")
    req = requests.get(
        f"https://api.ahfi.cn/api/xrjupai?msg={encoded_words}",
        headers=headers,
        verify=False,
    )
    with open(pic, "wb") as f:
        f.write(req.content)
    if req.status_code == 200:
        return pic
    else:
        """"""
