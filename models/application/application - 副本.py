# _*_ coding: utf-8 _*_
# @Time: 2025/06/16 21:31
# @Author: Tech_T

import os
import sqlite3
import time
from datetime import datetime
import pandas as pd
from config.log import LogConfig
from config.config import Config
from sendqueue import send_text, send_image, send_file
from models.lesson.lesson import Lesson
from models.manage.member import check_permission
from functools import lru_cache

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib

# 设置 Matplotlib 的字体为支持中文的字体
matplotlib.rcParams["font.sans-serif"] = ["SimHei"]  # 指定默认字体为黑体
matplotlib.rcParams["axes.unicode_minus"] = False  # 用来正常显示负号
config = Config()
lesson_dir = config.get_config("lesson_dir")


class Application:
    def __init__(self, db_path="databases/colleges.db"):
        self.__conn__ = None
        self.__cursor__ = None
        self.year = datetime.now().year
        self.log = LogConfig().get_logger()
        self.db_path = db_path

    def __enter__(self):
        self.__conn__ = sqlite3.connect(self.db_path)
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
        
        sql = "select * from zyk where zymc=? or zydm=?"
        params = []
        if zymc:
            params = [zymc, 0]
        else:
            params = ["", zydm]
            
        with self as app:
            app.__cursor__.execute(sql, params)
            results = app.__cursor__.fetchall()
        tips = ""
        if not results:
            tips = f"没有找到{zymc}专业，请检查专业名称是否正确"
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
            tips += f"薪酬待遇：{result[13]}\n" if result[13] else ""
            tips += f"选课要求：{result[14]}\n" if result[14] else ""
            tips += f"考研方向：{result[15]}\n" if result[15] else ""
            tips += f"社会名人：{result[16]}\n" if result[16] else ""
            tips += f"专业介绍：{result[6]}\n" if result[6] else ""
            tips += "+" * 15 + "\n"
        return tips

    def query_yx(self, yxmc):
        if yxmc == "":
            return "请输入院校名称"
        sql = "select * from schools where school_name=?"
        with self as app:
            app.__cursor__.execute(sql, (yxmc,))
            result = app.__cursor__.fetchone()
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

    @lru_cache(maxsize=128)
    def rank_to_score(self, rank, category, year):
        """
        专业排名转分数 (带缓存)
        :param rank: 专业排名
        :param category: 专业类别
        :param year: 年份
        :return: 分数
        """
        # 类型检查和数据验证
        if not rank or not category or not year:
            return -1
        
        try:
            rank = int(rank)
            year = int(year)
        except (ValueError, TypeError):
            self.log.error(f"rank_to_score 参数类型错误: rank={rank}, year={year}")
            return -1
            
        valid_categories = ["普通类", "美术类", "音乐类", "体育类", "书法类"]
        if category not in valid_categories:
            self.log.error(f"rank_to_score 类别参数错误: category={category}")
            return -1
        
        # 使用字典映射表替代多个if-elif分支
        table_mapping = {
            "普通类": "putongfenshuduan",
            "美术类": "meishufenshuduan",
            "音乐类": "yinyuefenshuduan",
            "体育类": "tiyufenshuduan",
            "书法类": "shufafenshuduan"
        }
        
        table_name = table_mapping.get(category)
        
        # 构建查询语句
        query = f"SELECT 分数 FROM {table_name} WHERE 年份 = ? AND 累计人数 <= ?"
        
        # 对于艺术类专业，添加类型条件
        if category in ["美术类", "音乐类"]:
            query += " AND 类型 = '综合分'"
        
        query += " ORDER BY 累计人数 DESC LIMIT 1"
        
        with self as app:
            app.__cursor__.execute(query, (year, rank))
            result = app.__cursor__.fetchone()
        
        return result[0] if result else -1

    @lru_cache(maxsize=128)
    def score_to_rank(self, score, category, year):
        """
        专业分数转排名 (带缓存)
        :param score: 专业分数
        :param category: 专业类别
        :param year: 年份
        :return: 排名
        """
        # 类型检查和数据验证
        if not score or not category or not year:
            return -1
        
        try:
            score = float(score)
            year = int(year)
        except (ValueError, TypeError):
            self.log.error(f"score_to_rank 参数类型错误: score={score}, year={year}")
            return -1
                
        valid_categories = ["普通类", "美术类", "音乐类", "体育类", "书法类"]
        if category not in valid_categories:
            self.log.error(f"score_to_rank 类别参数错误: category={category}")
            return -1
        
        # 使用字典映射表替代多个if-elif分支
        table_mapping = {
            "普通类": "putongfenshuduan",
            "美术类": "meishufenshuduan",
            "音乐类": "yinyuefenshuduan",
            "体育类": "tiyufenshuduan",
            "书法类": "shufafenshuduan"
        }
        
        table_name = table_mapping.get(category)
        
        # 构建查询语句
        query = f"SELECT 累计人数 FROM {table_name} WHERE 年份 = ? AND 分数 <= ?"
        
        # 对于艺术类专业，添加类型条件
        if category in ["美术类", "音乐类"]:
            query += " AND 类型 = '综合分'"
        
        query += " ORDER BY 分数 DESC LIMIT 1"
        
        with self as app:
            app.__cursor__.execute(query, (year, score))
            result = app.__cursor__.fetchone()
        
        return result[0] if result else -1

    def toudang(self, category, zy, year="", yx="", rank=0, level="本科", counts=30):
        """
        查询投档情况
        
        Args:
            category: 类别，如"普通类"、"美术类"等
            zy: 专业名称
            year: 年份
            yx: 院校名称
            rank: 位次
            level: 层次，如"本科"、"专科"等
            counts: 返回结果数量，-1表示返回全部
            
        Returns:
            pandas.DataFrame: 投档结果数据框
        """
        # 参数验证
        if not category:
            self.log.error("toudang 缺少必要参数: category")
            return pd.DataFrame()
        
        # 使用字典映射表替代多个if-elif分支
        table_mapping = {
            "普通类": "putongtoudang",
            "美术类": "meishutoudang",
            "音乐类": "yinyuetoudang",
            "体育类": "tiyutoudang",
            "书法类": "shufatoudang"
        }
        
        table_name = table_mapping.get(category)
        if not table_name:
            self.log.error(f"toudang 类别参数错误: category={category}")
            return pd.DataFrame()
        
        # 构建查询条件
        conditions = []
        params = []
        
        # 添加各种查询条件
        if zy:
            conditions.append("专业 LIKE ?")
            params.append(f"%{zy}%")
        if yx:
            conditions.append("院校 LIKE ?")
            params.append(f"%{yx}%")
        if year:
            conditions.append("年份 = ?")
            params.append(year)
        
        conditions.append("类型 = ?")
        params.append(category)
        
        # 处理位次/分数条件
        if rank:
            if category == "普通类":
                conditions.append("最低位次 <= ?")
                params.append(rank)
            else:
                # 获取对应分数
                score_categories = ["美术类", "音乐类", "体育类", "书法类"]
                if category in score_categories:
                    score = self.rank_to_score(rank, category, year)
                    conditions.append("最低位次 >= ?")
                    params.append(score)
        
        # 构建SQL查询
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM {table_name} WHERE {where_clause}"
        
        # 执行查询
        with self as app:
            app.__cursor__.execute(sql, params)
            results = app.__cursor__.fetchall()
        
        if not results:
            return pd.DataFrame()
        
        # 处理查询结果
        columns = [
            "类型", "年份", "批次", "层次", "专业", "院校", "计划数", 
            "最低分数" if category != "普通类" else "最低位次", "院校代码"
        ]
        
        df = pd.DataFrame(results, columns=columns)
        
        # 根据类别处理数据
        if category != "普通类":
            # 非普通类处理
            df["最低分数"] = pd.to_numeric(df["最低分数"], errors="coerce").astype(float)
            df["位次"] = df.apply(
                lambda row: self.score_to_rank(row["最低分数"], row["类型"], row["年份"]),
                axis=1
            )
            df.sort_values(by=['年份', '位次'], ascending=False, inplace=True)
            
            # 设置列顺序
            new_order = [
                "类型", "年份", "批次", "院校代码", "院校", "专业", 
                "计划数", "最低分数", "位次", "层次"
            ]
            
            # 添加当年分数
            df[f"{self.year}分数(同位次)"] = df.apply(
                lambda row: self.rank_to_score(row["位次"], row["类型"], self.year),
                axis=1
            )
        else:
            # 普通类处理
            df["最低位次"] = pd.to_numeric(df["最低位次"], errors="coerce").astype(int)
            df["分数"] = df.apply(
                lambda row: self.rank_to_score(row["最低位次"], row["类型"], row["年份"]),
                axis=1
            )
            df.sort_values(by=['年份','分数'], ascending=False, inplace=True)
            # 设置列顺序
            new_order = [
                "类型", "年份", "批次", "院校代码", "院校", "专业", 
                "计划数", "最低位次", "分数", "层次", "选科要求", "学费", f"{self.year}计划数", f"{self.year}分数(同位次)"
            ]
            # 添加额外信息
            df["选科要求"] = df.apply(
                lambda row: self.get_xk(row["专业"][2:] if isinstance(row["专业"], str) else "", row["院校"]),
                axis=1
            )
            df[f"{self.year}计划数"] = df.apply(
                lambda row: self.get_jh(row["专业"][2:] if isinstance(row["专业"], str) else "", row["院校"]),
                axis=1
            )
            df["学费"] = df.apply(
                lambda row: self.get_xf(row["专业"][2:] if isinstance(row["专业"], str) else "", row["院校"]),
                axis=1
            )
            df[f"{self.year}分数(同位次)"] = df.apply(
                lambda row: self.rank_to_score(row["最低位次"], row["类型"], self.year),
                axis=1
            )
        
        # 处理结果数量限制
        if counts != -1:
            data = df[:counts].reset_index(drop=True)
        else:
            data = df.reset_index(drop=True)
        
        # 调整索引和列顺序
        data.index += 1
        data = data[new_order]
        data = data.drop(columns=["层次"])
        
        return data

    def _get_jihua_info(self, zy, yx, column, year=""):
        """获取计划信息的通用方法"""
        if not zy or not yx:
            return None
        if not year:
            year = self.year

        sql = f"SELECT {column} FROM jihua WHERE 院校名称=? AND 年份=? AND 专业名称 LIKE ?"
        params = (yx, year, f"{zy}%")

        try:
            with self as app:
                app.__cursor__.execute(sql, params)
                result = app.__cursor__.fetchone()
            return result[0] if result else None
        except Exception as e:
            self.log.error(f"获取{column}时出错: {e}")
            return None

    def get_jh(self, zy, yx, year=""):
        return self._get_jihua_info(zy, yx, "计划数", year)

    def get_xk(self, zy, yx, year=""):
        return self._get_jihua_info(zy, yx, "选科要求", year)

    def get_xf(self, zy, yx, year=""):
        return self._get_jihua_info(zy, yx, "学费", year)

    def toudang_range(self, category, year, min_rank, max_rank):
        """根据类别、年份和位次范围查询投档情况
        
        Args:
            category: 类别，如"普通类"、"美术类"等
            year: 年份
            min_rank: 最小位次
            max_rank: 最大位次
            
        Returns:
            pandas.DataFrame: 投档结果数据框
        """
        # 参数验证
        if not category:
            self.log.error("toudang_range 缺少必要参数: category")
            return pd.DataFrame()
            
        # 使用字典映射表替代多个if-elif分支
        table_mapping = {
            "普通类": "putongtoudang",
            "美术类": "meishutoudang",
            "音乐类": "yinyuetoudang",
            "体育类": "tiyutoudang",
            "书法类": "shufatoudang"
        }
        
        table_name = table_mapping.get(category)
        if not table_name:
            self.log.error(f"toudang_range 类别参数错误: category={category}")
            return pd.DataFrame()
        
        # 构建查询条件
        conditions = ["类型 =?"]
        params = [category]
        
        # 处理位次范围条件
        is_normal = category == "普通类"
        
        if min_rank:
            # 普通类和其他类别的条件不同
            if is_normal:
                conditions.append("最低位次 >=?")
                params.append(min_rank)
            else:
                # 对于艺术类，将位次转换为分数
                score = self.rank_to_score(min_rank, category, year)
                conditions.append("最低位次 <=?")
                params.append(score)
                
        if max_rank:
            # 普通类和其他类别的条件不同
            if is_normal:
                conditions.append("最低位次 <=?")
                params.append(max_rank)
            else:
                # 对于艺术类，将位次转换为分数
                score = self.rank_to_score(max_rank, category, year)
                conditions.append("最低位次 >=?")
                params.append(score)
                
        if year:
            conditions.append("年份 =?")
            params.append(year)
            
        # 构建SQL查询
        where_clause = " AND ".join(conditions)
        sql = f"SELECT * FROM {table_name} WHERE {where_clause}"
        
        # 执行查询
        with self as app:
            app.__cursor__.execute(sql, params)
            results = app.__cursor__.fetchall()
            
        if not results:
            return pd.DataFrame()
            
        # 根据类别处理数据
        if is_normal:
            # 普通类处理
            columns = [
                "类型", "年份", "批次", "层次", "专业", "院校", 
                "计划数", "最低位次", "院校代码"
            ]
            df = pd.DataFrame(results, columns=columns)
            df["最低位次"] = pd.to_numeric(df["最低位次"], errors="coerce").astype(int)
            df["分数"] = df.apply(
                lambda row: self.rank_to_score(row["最低位次"], row["类型"], row["年份"]),
                axis=1
            )
            df.sort_values(by=["年份", "最低位次"], ascending=[True, False], inplace=True)
            
            # 设置列顺序
            new_order = [
                "类型", "年份", "批次", "院校代码", "院校", "专业", 
                "计划数", "最低位次", "分数", "层次"
            ]
        else:
            # 非普通类处理
            columns = [
                "类型", "年份", "批次", "层次", "专业", "院校", 
                "计划数", "最低分数", "院校代码"
            ]
            df = pd.DataFrame(results, columns=columns)
            df["最低分数"] = pd.to_numeric(df["最低分数"], errors="coerce").astype(float)
            df["位次"] = df.apply(
                lambda row: self.score_to_rank(row["最低分数"], row["类型"], row["年份"]),
                axis=1
            )
            df.sort_values(by=["年份", "位次"], ascending=[True, True], inplace=True)
            
            # 设置列顺序
            new_order = [
                "类型", "年份", "批次", "院校代码", "院校", "专业", 
                "计划数", "最低分数", "位次", "层次"
            ]
        
        # 处理数据
        data = df.reset_index(drop=True)
        data.index += 1
        data = data[new_order]
        data = data.drop(columns=["层次"])
        
        # 添加额外信息
        if is_normal:
            # 添加普通类特有的额外信息
            data["选科要求"] = data.apply(
                lambda row: self.get_xk(
                    row.专业[2:] if isinstance(row.专业, str) else str(row.专业)[2:],
                    row.院校
                ),
                axis=1
            )
            data[f"{self.year}计划数"] = data.apply(
                lambda row: self.get_jh(
                    row.专业[2:] if isinstance(row.专业, str) else str(row.专业)[2:],
                    row.院校
                ),
                axis=1
            )
            data["学费"] = data.apply(
                lambda row: self.get_xf(
                    row.专业[2:] if isinstance(row.专业, str) else str(row.专业)[2:],
                    row.院校
                ),
                axis=1
            )
        
        # 添加所有类别都需要的当年分数信息
        score_column = "位次" if not is_normal else "最低位次"
        data[f"{self.year}分数(同位次)"] = data.apply(
            lambda row: self.rank_to_score(row[score_column], row["类型"], self.year),
            axis=1
        )
        
        return data


def df_to_png(df, png_name, title):
    """
    将DataFrame转换为PNG图片
    :param df: DataFrame
    :param png_name: 图片文件名
    :param title: 图片标题
    :return: PNG图片路径
    """
    if df.empty:
        return None
    l = Lesson()
    png = l.df_to_png(df, png_name, title, index_name="序号")
    # print(png)
    add_watermark(png[0], png[0], "公众号：技术田言", "simhei.ttf", 36, 0.8, 211)
    path = png[0][len(l.lesson_dir) :].replace("\\", "/")
    return path


async def zy_jieshao(record):
    zy = (
        record.content.replace(" ", "").replace("专业介绍-", "").replace("模版", "模板")
    )
    zydm = zy if zy[:-1].isdigit() else 0
    a = Application()
    if zydm:
        tips = a.query_zy(zydm=zy)
    else:
        tips = a.query_zy(zymc=zy)
    send_text(tips, record.roomid)


async def yx_jieshao(record):
    yx = (
        record.content.replace(" ", "").replace("院校介绍-", "").replace("模版", "模板")
    )
    a = Application()
    tips = a.query_yx(yx)
    send_text(tips, record.roomid)


async def zy_template(record):
    tips = "<专业投档>\n类别:美术类\n专业:不能为空\n年份:2024\n院校:可以为空\n位次:1000\n层次:本科"
    send_text(tips, record.roomid)


async def yx_template(record):
    tips = "<院校投档>\n类别:美术类\n专业:可以为空\n年份:2024\n院校:不能为空\n层次:本科"
    send_text(tips, record.roomid)


async def rank_template(record):
    tips = "<位次投档>\n类别:普通类\n年份:2024\n位次:1000"
    send_text(tips, record.roomid)


async def zy_toudang(record=None):
    try:
        app = Application()
        text = (
            record.content.replace(" ", "")
            .replace("：", ":")
            .replace("不能为空", "")
            .replace("可以为空", "")
            .split("\n")
        )
        # print(text)
        if len(text) != 7:
            send_text("查询参数有误，请参照下面的模板重新输入！", record.roomid)
            tips = "<专业投档>\n类别:美术类\n专业:不能为空\n年份:2024\n院校:可以为空\n位次:1000\n层次:本科"
            send_text(tips, record.roomid)
            send_text(
                "建议认真阅读《小助手志愿填报辅助功能使用说明！》\nhttps://mp.weixin.qq.com/s/O1BymUcRUh-0-tE5YsPXGA",
                record.roomid,
            )
            return None
        zy = text[2].split(":")[-1]
        if zy:
            tips = app.query_zy(zy)
            if len(tips.split("\n")) > 10:
                tip = tips.split("\n")[10]
                tip = f"{zy}\n{tip}"
                send_text(tip, record.roomid)
        df = app.toudang(
            text[1].split(":")[-1],
            text[2].split(":")[-1],
            text[3].split(":")[-1],
            text[4].split(":")[-1],
            text[5].split(":")[-1],
            text[6].split(":")[-1],
        )
        png_name = record.roomid + ".png"
        title = f"{text[3].split(':')[-1]} {text[4].split(':')[-1]}{text[1].split(':')[-1]}{text[2].split(':')[-1]}投档情况"
        png = df_to_png(df, png_name, title)
        if png:
            send_image(png, record.roomid)
            return 0
        else:
            send_text("查询结果为空，请重新输入！", record.roomid)
            return -1
    except Exception as e:
        log = LogConfig().get_logger()
        log.error(f"zy_toudang 执行出错: {e}")
        send_text("查询过程中出现错误，请稍后重试", record.roomid)
        return -1


async def yx_toudang(record=None):
    app = Application()
    text = (
        record.content.replace(" ", "")
        .replace("：", ":")
        .replace("不能为空", "")
        .replace("可以为空", "")
        .split("\n")
    )
    # text = ['', '美术类', '', '2024', '北京师范大学', '本科']
    if len(text) != 6:
        send_text("查询参数有误，请参照下面的模板重新输入！", record.roomid)
        tips = "<院校投档>\n类别:美术类\n专业:可以为空\n年份:2024\n院校:不能为空)\n层次:本科"
        send_text(tips, record.roomid)
        send_text(
            "建议认真阅读《小助手志愿填报辅助功能使用说明！》\nhttps://mp.weixin.qq.com/s/O1BymUcRUh-0-tE5YsPXGA",
            record.roomid,
        )
        return 0
    zy = text[2].split(":")[-1]
    if zy:
        tips = app.query_zy(zy)
        if len(tips.split("\n")) > 10:
            tip = tips.split("\n")[10]
            tip = f"{zy}\n{tip}"
            send_text(tip, record.roomid)
        else:
            send_text(tips, record.roomid)

    df = app.toudang(
        text[1].split(":")[-1],
        text[2].split(":")[-1],
        text[3].split(":")[-1],
        text[4].split(":")[-1],
        0,
        text[5].split(":")[-1],
        1000,
    )
    png_name = record.roomid + ".png"
    # png_name = 'yx.png'
    title = f"{text[3].split(':')[-1]} {text[4].split(':')[-1]}{text[1].split(':')[-1]}{text[2].split(':')[-1]}投档情况"
    png = df_to_png(df, png_name, title)
    if png:
        send_image(png, record.roomid)
    else:
        send_text("没有查到相关信息！", record.roomid)
    return -1


async def rank_toudang(record=None):
    app = Application()
    text = (
        record.content.replace(" ", "")
        .replace("：", ":")
        .replace("不能为空", "")
        .replace("可以为空", "")
        .split("\n")
    )
    if len(text) != 4:
        send_text("查询参数有误，请参照下面的模板重新输入！", record.roomid)
        tips = "<位次投档>\n类别:普通类\n年份:2024\n位次:1000"
        send_text(tips, record.roomid)
        send_text(
            "建议认真阅读《小助手志愿填报辅助功能使用说明！》\nhttps://mp.weixin.qq.com/s/O1BymUcRUh-0-tE5YsPXGA",
            record.roomid,
        )
        return 0
    df = app.toudang(
        text[1].split(":")[-1],
        "",
        text[2].split(":")[-1],
        "",
        text[3].split(":")[-1],
        "",
        50,
    )
    png_name = record.roomid + ".png"
    title = f"{text[2].split(':')[-1]} {text[1].split(':')[-1]}位次投档情况"
    png = df_to_png(df, png_name, title)
    if png:
        send_image(png, record.roomid)
    else:
        send_text("没有查到相关信息！", record.roomid)
    return -1


from PIL import Image, ImageDraw, ImageFont


def add_watermark(
    image_path, output_path, watermark_text, font_path, font_size, opacity, step
):
    """
    给图片添加水印
    
    Args:
        image_path: 原图片路径
        output_path: 输出图片路径
        watermark_text: 水印文字
        font_path: 字体路径
        font_size: 字体大小
        opacity: 透明度
        step: 水印间隔
    """
    # 打开图片
    image = Image.open(image_path).convert("RGBA")
    width, height = image.size
    # 创建一个与原图大小相同的透明图层用于绘制水印
    watermark_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark_layer)

    # 加载字体
    font = ImageFont.truetype(font_path, font_size)

    # 获取水印文字的大小
    left, top, right, bottom = font.getbbox(watermark_text)
    text_width = right - left
    text_height = bottom - top

    # 在图片上多处添加水印，根据图片尺寸自动计算位置，间隔约150像素
    x = 0
    while x < width:
        y = 0
        while y < height:
            # 计算水印位置
            position = (x, y)
            rotated_text = Image.new(
                "RGBA", (text_width, text_height), (255, 255, 255, 0)
            )
            text_draw = ImageDraw.Draw(rotated_text)
            # 指定水印颜色为绿色
            text_draw.text(
                (0, 0), watermark_text, font=font, fill=(0, 255, 0, int(255 * opacity))
            )
            rotated_text = rotated_text.rotate(30, expand=True)
            watermark_layer.paste(rotated_text, position, rotated_text)
            y += step
        x += text_width + step

    # 将水印图层与原图合并
    result = Image.alpha_composite(image, watermark_layer)
    # 保存添加水印后的图片
    result.save(output_path)


def calculate_gradient_intervals(
    rank,
    category="普通类",
    risk_preference="balanced",
    total_candidates=100000,
    verbose=False,
):
    """
    计算五级梯度位次区间，根据考生总数动态划分高中低分段

    参数:
    rank -- 考生位次(整数)
    total_candidates -- 考生总数(整数)
    category -- 考生类型: '普通类' 或 '艺术类'
    risk_preference -- 风险偏好: 'aggressive'(激进), 'balanced'(均衡), 'conservative'(保守)
    verbose -- 是否打印详细结果

    返回:
    包含五级梯度位次区间和志愿数量分配的字典
    """
    # 验证输入有效性
    if not isinstance(rank, int) or rank <= 0:
        raise ValueError("考生位次必须是正整数")
    if not isinstance(total_candidates, int) or total_candidates <= 0:
        raise ValueError("考生总数必须是正整数")

    # 根据考生类型设置总志愿数
    total_slots = 96 if category == "普通类" else 60
    if category == "普通类":
        total_candidates = 660000
    elif category == "美术类":
        total_candidates = 27500
    elif category == "音乐类":
        total_candidates = 6000
    elif category == "体育类":
        total_candidates = 16000
    elif category == "书法类类":
        total_candidates = 2500

    # 动态分段策略 - 基于考生总数
    # 高分段: 前4%
    # 中分段: 5%-30%
    # 低分段: 30%以后
    high_segment = int(total_candidates * 0.04)
    medium_segment = int(total_candidates * 0.20)

    # 根据分段策略确定考生类型
    if rank <= high_segment:
        segment_type = "高分"
        segment_desc = f"前{high_segment}名(前5%)"
    elif rank <= medium_segment:
        segment_type = "中分"
        segment_desc = f"{high_segment+1}-{medium_segment}名(5%-30%)"
    else:
        segment_type = "低分"
        segment_desc = f"{medium_segment+1}名以后(30%以后)"

    # 根据考生类型和分段确定策略系数
    if category == "普通类":
        if segment_type == "高分":  # 高分段考生
            coefficients = {
                "gamble": [0.75, 0.9],
                "reach": [0.9, 0.97],
                "match": [0.97, 1.03],
                "safe": [1.03, 1.12],
                "anchor": [1.12, 1.25],
            }
        elif segment_type == "中分":  # 中分段考生
            coefficients = {
                "gamble": [0.7, 0.9],
                "reach": [0.9, 0.98],
                "match": [0.98, 1.05],
                "safe": [1.05, 1.15],
                "anchor": [1.15, 1.3],
            }
        else:  # 低分段考生
            coefficients = {
                "gamble": [0.65, 0.85],
                "reach": [0.85, 0.97],
                "match": [0.97, 1.08],
                "safe": [1.08, 1.2],
                "anchor": [1.2, 1.5],
            }

        # 普通类志愿分配策略
        allocation = {
            "激进": {
                "gamble": 0.08,
                "reach": 0.25,
                "match": 0.30,
                "safe": 0.25,
                "anchor": 0.12,
            },
            "均衡": {
                "gamble": 0.05,
                "reach": 0.20,
                "match": 0.35,
                "safe": 0.25,
                "anchor": 0.15,
            },
            "保守": {
                "gamble": 0.03,
                "reach": 0.15,
                "match": 0.40,
                "safe": 0.25,
                "anchor": 0.17,
            },
        }

    else:  # 艺术类
        # 艺术类分段调整 (竞争更集中)
        art_high_segment = int(total_candidates * 0.10)  # 前10%
        art_medium_segment = int(total_candidates * 0.50)  # 前50%

        if rank <= art_high_segment:
            segment_type = "高分"
            segment_desc = f"前{art_high_segment}名(前10%)"
        elif rank <= art_medium_segment:
            segment_type = "中分"
            segment_desc = f"{art_high_segment+1}-{art_medium_segment}名(10%-50%)"
        else:
            segment_type = "低分"
            segment_desc = f"{art_medium_segment+1}名以后(50%以后)"

        if segment_type == "高分":  # 艺术类高分段
            coefficients = {
                "gamble": [0.7, 0.85],
                "reach": [0.85, 0.95],
                "match": [0.95, 1.05],
                "safe": [1.05, 1.15],
                "anchor": [1.15, 1.35],
            }
        elif segment_type == "中分":  # 艺术类中分段
            coefficients = {
                "gamble": [0.65, 0.8],
                "reach": [0.8, 0.93],
                "match": [0.93, 1.08],
                "safe": [1.08, 1.25],
                "anchor": [1.25, 1.6],
            }
        else:  # 艺术类低分段
            coefficients = {
                "gamble": [0.6, 0.75],
                "reach": [0.75, 0.9],
                "match": [0.9, 1.1],
                "safe": [1.1, 1.3],
                "anchor": [1.3, 2.0],
            }

        # 艺术类志愿分配策略(总志愿数60个)
        allocation = {
            "激进": {
                "gamble": 0.07,
                "reach": 0.23,
                "match": 0.35,
                "safe": 0.25,
                "anchor": 0.10,
            },
            "均衡": {
                "gamble": 0.05,
                "reach": 0.18,
                "match": 0.40,
                "safe": 0.25,
                "anchor": 0.12,
            },
            "保守": {
                "gamble": 0.03,
                "reach": 0.12,
                "match": 0.45,
                "safe": 0.25,
                "anchor": 0.15,
            },
        }

    # 计算各梯度的位次区间
    intervals = {}
    for level, coefs in coefficients.items():
        min_rank = max(1, int(rank * coefs[0]))  # 位次不能小于1
        max_rank = int(rank * coefs[1])
        intervals[level] = (min_rank, max_rank - 1)

    # 根据风险偏好分配志愿数量
    allocation_ratios = allocation[risk_preference]
    counts = {
        level: max(1, int(total_slots * ratio))
        for level, ratio in allocation_ratios.items()
    }

    # 确保总数正确
    total = sum(counts.values())
    if total != total_slots:
        # 调整match级的数量以补偿
        counts["match"] += total_slots - total

    # 动态调整因子说明
    adjustment_factors = {
        "专业热度": {"热门": +0.05, "冷门": -0.03},
        "地域": {"一线": +0.04, "三四线": -0.02},
        "招生计划": {"扩招": -0.03, "缩招": +0.06},
    }

    # 艺术类特殊调整
    if category == "艺术类":
        adjustment_factors["专业类型"] = {
            "美术类": +0.02 if segment_type == "高分" else -0.01,
            "音乐类": +0.01 if segment_type == "高分" else -0.02,
            "舞蹈类": -0.03 if segment_type == "低分" else +0.01,
        }

    # 初始化 tips 变量
    tips = ""

    # 添加考生信息
    tips += "\n" + "=" * 16 + "\n"
    tips += f"考生类型: {category} | 考生位次: {rank}名 | 风险偏好: {'激进型' if risk_preference == '激进' else '均衡型' if risk_preference == '均衡' else '保守型'}\n"
    tips += "=" * 16 + "\n"

    # 添加五级梯度位次区间信息
    tips += f"\n【五级梯度位次区间】(总志愿数: {total_slots}个)\n"
    for level, (min_r, max_r) in intervals.items():
        level_name = {
            "gamble": "赌",
            "reach": "冲",
            "match": "稳",
            "safe": "保",
            "anchor": "垫",
        }[level]
        tips += f"{level_name}级: 位次 {min_r:,} ~ {max_r:,} 名\n"

    # 添加志愿数量分配信息
    tips += "\n【志愿数量分配】\n"
    for level, count in counts.items():
        level_name = {
            "gamble": "赌",
            "reach": "冲",
            "match": "稳",
            "safe": "保",
            "anchor": "垫",
        }[level]
        tips += f"{level_name}级: {count}个志愿 ({count/total_slots:.1%})\n"

    # 添加动态调整因子信息
    tips += "\n【动态调整因子】\n"
    tips += "(实际填报时需根据以下因素调整预估位次):\n"
    for factor, values in adjustment_factors.items():
        tips += (
            f"- {factor}: {', '.join([f'{k}({v:+.0%})' for k, v in values.items()])}\n"
        )

    # 添加梯度策略说明
    tips += "\n" + "=" * 16 + "\n"
    tips += f"梯度策略说明 ({category}):\n"
    if category == "普通类":
        tips += (
            f"- 赌级: 冲击顶尖院校({intervals['gamble'][0]:,}名以上)，录取概率<10%\n"
        )
        tips += f"- 冲级: 尝试略高于自身位次的院校专业({intervals['reach'][0]:,}-{intervals['reach'][1]:,}名)\n"
        tips += f"- 稳级: 重点匹配院校({intervals['match'][0]:,}-{intervals['match'][1]:,}名)，录取概率40-60%\n"
        tips += f"- 保级: 确保录取的院校({intervals['safe'][0]:,}-{intervals['safe'][1]:,}名)\n"
        tips += f"- 垫级: 绝对保底院校({intervals['anchor'][0]:,}名以下)\n"
    else:
        tips += f"- 赌级: 顶尖艺术院校({intervals['gamble'][0]:,}名以上)\n"
        tips += f"- 冲级: 重点艺术院校({intervals['reach'][0]:,}-{intervals['reach'][1]:,}名)\n"
        tips += (
            f"- 稳级: 匹配院校({intervals['match'][0]:,}-{intervals['match'][1]:,}名)\n"
        )
        tips += f"- 保级: 确保录取院校({intervals['safe'][0]:,}-{intervals['safe'][1]:,}名)，地方艺术院校\n"
        tips += f"- 垫级: 绝对保底({intervals['anchor'][0]:,}名以下)，包含民办艺术院校和专科艺术专业\n"
    tips += "=" * 16 + "\n"

    # 如果 verbose 为 True，则打印 tips
    if verbose:
        print(tips)

    return {
        "category": category,
        "rank": rank,
        "risk_preference": risk_preference,
        "total_slots": total_slots,
        "intervals": intervals,
        "counts": counts,
        "adjustment_factors": adjustment_factors,
    }, tips


def plot_gradient_strategy(result, png_name):
    """可视化梯度策略"""
    category = result["category"]
    rank = result["rank"]
    intervals = result["intervals"]
    counts = result["counts"]
    total_slots = result["total_slots"]

    # 创建图形
    plt.figure(figsize=(14, 10))

    # 位次区间图
    plt.subplot(2, 1, 1)
    levels = ["gamble", "reach", "match", "safe", "anchor"]
    labels = ["赌", "冲", "稳", "保", "垫"]
    colors = ["#FF6B6B", "#FFD166", "#06D6A0", "#118AB2", "#073B4C"]

    # 绘制区间条
    for i, level in enumerate(levels):
        min_r, max_r = intervals[level]
        plt.barh(
            labels[i], max_r - min_r, left=min_r, color=colors[i], edgecolor="black"
        )

    # 标记考生位次
    plt.axvline(x=rank, color="red", linestyle="--", linewidth=2)
    plt.text(
        rank,
        4.7,
        f"考生位次: {rank:,}",
        color="red",
        ha="center",
        fontsize=12,
        weight="bold",
    )

    plt.title(f"山东新高考{category}梯度策略 (考生位次: {rank:,}名)", fontsize=16)
    plt.xlabel("位次", fontsize=12)
    plt.gca().invert_yaxis()  # 反转Y轴使赌级在顶部
    plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x):,}"))
    plt.grid(axis="x", linestyle="--", alpha=0.7)

    # 志愿数量分配饼图
    plt.subplot(2, 1, 2)
    sizes = [counts[level] for level in levels]
    labels_with_count = [f"{label}级\n{size}个" for label, size in zip(labels, sizes)]
    explode = (0.1, 0.05, 0, 0, 0)  # 突出赌级和冲级

    plt.pie(
        sizes,
        explode=explode,
        labels=labels_with_count,
        colors=colors,
        autopct="%1.1f%%",
        shadow=True,
        startangle=140,
        textprops={"fontsize": 12},
    )
    plt.axis("equal")
    plt.title(f"{total_slots}个志愿分配比例", fontsize=16)

    plt.tight_layout()
    timestamp = str(int(time.time() * 1000))
    g = png_name.split(".")
    png_name = f"{g[0]}_{timestamp}.{g[1]}"
    png_path = os.path.join(lesson_dir, "temp", png_name)
    plt.savefig(png_path, dpi=300)
    add_watermark(png_path, png_path, "公众号：技术田言", "simhei.ttf", 36, 0.8, 211)
    return png_path


async def gradient_intervals(record):
    # 位次区间-普通类-均衡-3456
    text = record.content.replace(" ", "").split("-")
    if len(text) != 4:
        send_text("请输入正确的格式，如：位次区间-普通类-均衡-3456", record.roomid)
        return None, None
    result, tips = calculate_gradient_intervals(
        int(text[3]), text[1], text[2], verbose=False
    )
    png_path = plot_gradient_strategy(result, record.roomid + ".png")
    path = png_path[len(lesson_dir) :].replace("\\", "/")
    send_text(tips, record.roomid)
    send_image(path, record.roomid)


def get_gradient_level(rank, intervals):
    """根据位次、类别、风险偏好和总考生数，返回梯度等级"""
    # 检查位次是否在任何一个区间内
    for level, (min_r, max_r) in intervals.items():
        if min_r <= rank <= max_r:
            return level

    # 如果位次不在任何区间内，返回 None
    return ""


def check_xk(xk, xkyq):
    """
    检查选科要求是否符合
    
    Args:
        xk: 考生选科
        xkyq: 专业选科要求
        
    Returns:
        bool: 是否符合选科要求
    """
    if xk == "":
        return True
    if xkyq == "" or xkyq == "不限" or not xkyq:
        return True
    xkyq = xkyq.replace("思想政治", "政治")
    yq_list = xkyq.split("和")
    flag = True
    for yq in yq_list:
        if yq[0] not in xk:
            flag = False
            break
    return flag


async def range_template(record):
    send_text(
        "<投档文件>\n位次:10000\n类型:普通类\n年份:2024\n风险偏好:均衡\n选科:物化生",
        record.roomid,
    )


@check_permission
async def get_gradient_file(record=None):
    text = record.content.replace(" ", "").split("\n")
    if len(text) != 6:
        send_text(
            "请输入正确的格式，如下：\n<投档文件>\n位次:10000\n类型:普通类\n年份:2024\n风险偏好:均衡\n选科:物化生",
            record.roomid,
        )
        return -1
    rank = int(text[1].split(":")[1])
    category = text[2].split(":")[1]
    year = text[3].split(":")[1]
    risk_preference = text[4].split(":")[1]
    xk = text[5].split(":")[1]

    result, tips = calculate_gradient_intervals(
        rank, category, risk_preference, verbose=False
    )
    min_r, max_r = result["intervals"]["gamble"][0], result["intervals"]["anchor"][1]
    intervals = result["intervals"]
    app = Application()
    df = app.toudang_range(category, year, min_r, max_r)
    if category != "普通类":
        df["梯度"] = df.apply(
            lambda row: get_gradient_level(
                app.score_to_rank(row["最低分数"], category, year), intervals
            ),
            axis=1,
        )
        df.sort_values(by="最低分数", ascending=False, inplace=True)
    else:
        df["梯度"] = df.apply(
            lambda row: get_gradient_level(row["最低位次"], intervals), axis=1
        )
        df.sort_values(by="最低位次", ascending=True, inplace=True)
        df["符合选科"] = df.apply(lambda row: check_xk(xk, row["选科要求"]), axis=1)
        df = df[df["符合选科"] == True]
        df.drop(columns=["符合选科"], inplace=True)

    df["梯度"] = df["梯度"].apply(
        lambda x: {
            "gamble": "赌",
            "reach": "冲",
            "match": "稳",
            "safe": "保",
            "anchor": "垫",
            "": "",
        }[x]
    )
    file_name = f"{category}_{year}_{risk_preference}_{rank}.xlsx"
    file_path = os.path.join(lesson_dir, "temp", file_name)
    df.to_excel(file_path, index=False)
    time.sleep(2)
    send_file(os.path.join("temp", file_name), record.roomid)
