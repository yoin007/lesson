# _*_ coding: utf-8 _*_
# @Time: 2025/06/16 21:31
# @Author: Tech_T

import sqlite3
from datetime import datetime
from config.log import LogConfig
from sendqueue import send_text


class Application:
    def __init__(self):
        self.__conn__ = None
        self.__cursor__ = None
        self.year = datetime.now().year
        self.log = LogConfig().get_logger()

    def __enter__(self, db="databases/colleges.db"):
        self.__conn__ = sqlite3.connect(db)
        self.__cursor__ = self.__conn__.cursor()
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        if self.__conn__:
            self.__conn__.close()

    def query_zy(self, zymc="", zydm=0):
        """
        查询专业
        :param zy: 专业
        :return: 专业
        """
        if zymc == "" and zydm == 0:
            return "请输入专业名称或专业代码"
        if zymc:
            sql = f"select * from zyk where zymc='{zymc}'"
        else:
            sql = f"select * from zyk where zydm='{zydm}'"
        with self as app:
            self.__cursor__.execute(sql)
            results = self.__cursor__.fetchall()
        tips = ""
        if not results:
            tips = f"没有找到{zy}专业，请检查专业名称是否正确"
            return tips
        for result in results:
            tips += f"类别：{result[1]}\n"
            tips += f"门类：{result[2]}\n"
            tips += f"专业类：{result[3]}\n"
            tips += f"专业名称：{result[4]}\n"
            tips += f"专业代码：{result[5]}\n"
            tips += f"专业排名：{result[7]}\n" if result[7] else ""
            tips += f"男女比例：{result[8]}：{result[9]}\n" if result[8] else ""
            tips += f"授予学位：{result[10]}\n" if result[10] else ""
            tips += f"修业年限：{result[11]}\n" if result[11] else ""
            tips += f"专业介绍：{result[6]}" if result[6] else ""
        return tips

    def query_yx(self, yxmc):
        if yxmc == "":
            return "请输入院校名称"
        sql = f"select * from schools where school_name='{yxmc}'"
        with self as app:
            self.__cursor__.execute(sql)
            result = self.__cursor__.fetchone()
        if not result:
            return f"没有找到{yxmc}院校，请检查院校名称是否正确"
        tips = ""
        tips += f"院校名称：{result[0]}\n"
        tips += f"主管部位：{result[3]}\n"
        tips += f"院校性质：{result[4]}\n"
        tips += f"院校特色：{result[5]}\n" if result[5] else ""
        tips += f"院校层次：{result[6]}\n" if result[6] else ""
        tips += f"院校排名：{result[7]}\n" if result[7] else ""
        tips += f"院校省份：{result[8]}\n" if result[8] else ""
        tips += f"院校官网：{result[11]}\n" if result[11] else ""
        tips += f"招生网站：{result[12]}\n" if result[12] else ""
        tips += f"联系电话：{result[13]}\n" if result[13] else ""
        if result[1]:
            yggk = result[1].split("-")[-1].split(".")[0]
            tips += (
                f"院校介绍：\n\thttps://gaokao.chsi.com.cn/wap/sch/schinfomain/{yggk}"
            )
            tips += f"\n\t{result[2]}" if result[2] else ""
        return tips


async def zy_jieshao(record):
    zy = record.content.replace(" ", "").replace("专业介绍-", "")
    zydm = zy if zy[:-1].isdigit() else 0
    a = Application()
    if zydm:
        tips = a.query_zy(zydm=zy)
    else:
        tips = a.query_zy(zymc=zy)
    send_text(tips, record.roomid)


async def yx_jieshao(record):
    yx = record.content.replace(" ", "").replace("院校介绍-", "")
    a = Application()
    tips = a.query_yx(yx)
    send_text(tips, record.roomid)
