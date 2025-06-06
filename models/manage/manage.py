# _*_ coding: utf-8 _*_
# @Time: 2025/06/03 19:21
# @Author: Tech_T

from config.config import Config
from sendqueue import send_text, send_image
from models.manage.member import Member
from models.api import ju_pai
import json
import requests
from time import sleep
from client import Client


def forward_msg(msg):
    urls = Config().get_config("forward_url")
    if not urls or len(urls) == 0:
        return
    payload = json.dumps(msg)
    headers = {"User-Agent": "tech_t", "Content-Type": "application/json"}
    for url in urls:
        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            if response:
                return response
        except:
            pass
        sleep(1)


async def command_manul(record):
    """
    命令帮助
    :param record: 命令记录
    :return: 命令帮助
    """
    command_list = Config().get_config("command_manul")
    tips = "当前指令列表：\n"
    cnt = 1
    for key in command_list:
        tips += str(cnt) + ". " + key + "\n"
        cnt += 1
    send_text(tips, record.roomid)


async def welcome_msg(record):
    """
    欢迎消息
    """
    roomid = record.roomid
    msgs = Config().get_config("welcome_msg")
    try:
        msg = msgs[roomid]
        send_text(msg, roomid)
    except:
        pass


async def say_hi_qun(record: any):
    """
    新人入群欢迎，小黄人举牌
    """
    alias = ""
    member = record.ext["members"][0]
    with Member() as m:
        remarks = m.wxid_remark(member)
        if remarks:
            alias = remarks[1]
    if not alias:
        if "加入了群聊" in record.content:
            s_list = record.content.split('"')
            alias = s_list[-2]
        if "通过扫描" in record.content:
            s_list = record.content.split('"')
            alias = s_list[1]
    if alias:
        img = ju_pai(alias)
        if img:
            pic_path = img[len(Config().get_config("lesson_dir")) :].replace("\\", "/")
            send_image(pic_path, record.roomid, "manage")
            return True


async def invite_chatroom_member(record: any):
    """
    邀请入群
    """
    text = record.content.replace("#", "").replace(" ", "")
    invite_rooms = Config().get_config("invite_rooms")
    chatrooms = Config().get_config("qrcode_git")
    try:
        roomid = chatrooms[invite_rooms[text]]
        c = Client()
        c.group_manage(roomid, record.sender, 2)
        return True
    except:
        return False
