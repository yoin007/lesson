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
admin_list = Config().get_config("admin_list")


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

    @lru_cache(maxsize=1024)
    def get_jh(self, zy, yx, year=""):
        return self._get_jihua_info(zy, yx, "计划数", year)

    @lru_cache(maxsize=1024)
    def get_xk(self, zy, yx, year=""):
        return self._get_jihua_info(zy, yx, "选科要求", year)

    @lru_cache(maxsize=1024)
    def get_xf(self, zy, yx, year=""):
        return self._get_jihua_info(zy, yx, "学费", year)

    # 批量处理替代逐行应用
    def batch_get_info(self, df, column_name, info_type):
        """批量获取信息"""
        # 创建唯一的(专业,院校)对
        unique_pairs = df[["专业", "院校"]].drop_duplicates()
        
        # 预处理专业名称
        unique_pairs["处理后专业"] = unique_pairs["专业"].apply(
            lambda x: x[2:] if isinstance(x, str) else str(x)[2:]
        )
        
        # 创建查询结果字典
        info_dict = {}
        
        # 构建SQL查询
        placeholders = ", ".join(["(?, ?)"] * len(unique_pairs))
        params = []
        for _, row in unique_pairs.iterrows():
            params.extend([row["院校"], f"{row['处理后专业']}%"])
        
        sql = f"""SELECT 院校名称, 专业名称, {info_type} 
            FROM jihua 
            WHERE (院校名称, 专业名称) IN ({placeholders}) 
            AND 年份=?"""
        params.append(self.year)
        
        # 执行批量查询
        with self as app:
            app.__cursor__.execute(sql, params)
            results = app.__cursor__.fetchall()
        
        # 填充字典
        for result in results:
            yx, zy_full, info = result
            # 提取专业名称的关键部分进行匹配
            for _, pair in unique_pairs.iterrows():
                if pair["院校"] == yx and zy_full.startswith(pair["处理后专业"]):
                    info_dict[(pair["专业"], yx)] = info
        
        # 应用到原始DataFrame
        df[column_name] = df.apply(
            lambda row: info_dict.get((row["专业"], row["院校"]), None),
            axis=1
        )
        
        return df


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
            # # 添加普通类特有的额外信息
            # data["选科要求"] = data.apply(
            #     lambda row: self.get_xk(
            #         row.专业[2:] if isinstance(row.专业, str) else str(row.专业)[2:],
            #         row.院校
            #     ),
            #     axis=1
            # )
            # data[f"{self.year}计划数"] = data.apply(
            #     lambda row: self.get_jh(
            #         row.专业[2:] if isinstance(row.专业, str) else str(row.专业)[2:],
            #         row.院校
            #     ),
            #     axis=1
            # )
            # data["学费"] = data.apply(
            #     lambda row: self.get_xf(
            #         row.专业[2:] if isinstance(row.专业, str) else str(row.专业)[2:],
            #         row.院校
            #     ),
            #     axis=1
            # )
            
            data = self.batch_get_info(data, "选科要求", "选科要求")
            data = self.batch_get_info(data, f"{self.year}计划数", "计划数")
            data = self.batch_get_info(data, "学费", "学费")
        
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

    # 计算考生位次百分比
    rank_percent = rank / total_candidates
    
    # 动态分段策略 - 基于考生总数
    high_segment = int(total_candidates * 0.05)
    medium_segment = int(total_candidates * 0.30)
    
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
    
    # 梯度范围动态调整函数
    def dynamic_range(base_factor, min_span_factor, max_span_factor, rank_span_factor=0.2):
        """
        动态梯度范围计算函数
        base_factor: 基础范围系数
        min_span_factor: 最小跨度系数
        max_span_factor: 最大跨度系数
        rank_span_factor: 位次跨度影响因子
        """
        # 基础范围
        base_span = base_factor * rank
        
        # 位次百分比影响（高位次扩大范围，低位次缩小范围）
        span_adjustment = 1 + (0.5 - rank_percent) * rank_span_factor
        
        # 总考生数影响（考生越多，合理范围越大）
        total_adjustment = 1 + (total_candidates / 100000) * 0.1
        
        # 计算最终跨度
        final_span = base_span * span_adjustment * total_adjustment
        
        # 应用最小和最大跨度限制
        min_span = min_span_factor * total_candidates
        max_span = max_span_factor * total_candidates
        return max(min_span, min(max_span, final_span))
    
    # 根据考生类型和分段确定策略系数
    if category == '普通类':
        # 普通类梯度范围系数
        gamble_span = dynamic_range(0.15, 0.001, 0.05)
        reach_span = dynamic_range(0.08, 0.001, 0.04)
        match_span = dynamic_range(0.07, 0.001, 0.03)
        safe_span = dynamic_range(0.10, 0.001, 0.04)
        anchor_span = dynamic_range(0.15, 0.005, 0.08)
        
        # 确保区间连续的计算
        intervals = {
            'gamble': (max(1, int(rank - gamble_span)), 0), 
            'reach': (0, 0),  # 占位符
            'match': (0, 0),  # 占位符
            'safe': (0, 0),   # 占位符
            'anchor': (0, 0)  # 占位符
        }
        
        # 计算连续的区间
        intervals['gamble'] = (max(1, int(rank - gamble_span)), int(rank - gamble_span * 0.6))
        intervals['reach'] = (int(intervals['gamble'][1] + 1), int(rank - reach_span * 0.3))
        intervals['match'] = (int(intervals['reach'][1] + 1), int(rank + match_span * 0.4))
        intervals['safe'] = (int(intervals['match'][1] + 1), int(rank + safe_span * 0.7))
        intervals['anchor'] = (int(intervals['safe'][1] + 1), int(rank + anchor_span))
        # 普通类志愿分配策略
        allocation = {
            '激进': {'gamble': 0.08, 'reach': 0.25, 'match': 0.30, 'safe': 0.25, 'anchor': 0.12},
            '均衡':   {'gamble': 0.05, 'reach': 0.20, 'match': 0.35, 'safe': 0.25, 'anchor': 0.15},
            '保守': {'gamble': 0.03, 'reach': 0.15, 'match': 0.40, 'safe': 0.25, 'anchor': 0.17}
        }
        
    else:  # 艺术类
        # 艺术类梯度范围系数
        gamble_span = dynamic_range(0.15, 0.001, 0.06)
        reach_span = dynamic_range(0.10, 0.001, 0.05)
        match_span = dynamic_range(0.08, 0.001, 0.04)
        safe_span = dynamic_range(0.12, 0.001, 0.05)
        anchor_span = dynamic_range(0.20, 0.005, 0.10)
        
        # 确保区间连续的计算
        intervals = {
            'gamble': (max(1, int(rank - gamble_span)), 0), 
            'reach': (0, 0),  # 占位符
            'match': (0, 0),  # 占位符
            'safe': (0, 0),   # 占位符
            'anchor': (0, 0)  # 占位符
        }
        
        # 计算连续的区间
        intervals['gamble'] = (max(1, int(rank - gamble_span)), int(rank - gamble_span * 0.5))
        intervals['reach'] = (int(intervals['gamble'][1] + 1), int(rank - reach_span * 0.2))
        intervals['match'] = (int(intervals['reach'][1] + 1), int(rank + match_span * 0.3))
        intervals['safe'] = (int(intervals['match'][1] + 1), int(rank + safe_span * 0.6))
        intervals['anchor'] = (int(intervals['safe'][1] + 1), int(rank + anchor_span))

        # 艺术类志愿分配策略(总志愿数60个)
        allocation = {
            '激进': {'gamble': 0.07, 'reach': 0.23, 'match': 0.35, 'safe': 0.25, 'anchor': 0.10},
            '均衡':   {'gamble': 0.05, 'reach': 0.18, 'match': 0.40, 'safe': 0.25, 'anchor': 0.12},
            '保守': {'gamble': 0.03, 'reach': 0.12, 'match': 0.45, 'safe': 0.25, 'anchor': 0.15}
        }
    
    # 确保区间合理性
    for level, (min_r, max_r) in intervals.items():
        if min_r < 1:
            min_r = 1
        if max_r > total_candidates:
            max_r = total_candidates
        if min_r > max_r:
            min_r, max_r = max_r, min_r
        intervals[level] = (min_r, max_r)
    
    # 根据风险偏好分配志愿数量
    allocation_ratios = allocation[risk_preference]
    counts = {level: max(1, int(total_slots * ratio)) for level, ratio in allocation_ratios.items()}
    
    # 确保总数正确
    total = sum(counts.values())
    if total != total_slots:
        # 调整match级的数量以补偿
        counts['match'] += total_slots - total
    
    # 动态调整因子说明
    adjustment_factors = {
        '专业热度': {'热门': +0.05, '冷门': -0.03},
        '地域': {'一线': +0.04, '三四线': -0.02},
        '招生计划': {'扩招': -0.03, '缩招': +0.06}
    }
    
    # 艺术类特殊调整
    if category == '艺术类':
        adjustment_factors['专业类型'] = {
            '美术类': +0.02 if segment_type == "高分" else -0.01,
            '音乐类': +0.01 if segment_type == "高分" else -0.02,
            '舞蹈类': -0.03 if segment_type == "低分" else +0.01
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
        'category': category,
        'total_candidates': total_candidates,
        'rank': rank,
        'segment': segment_type,
        'risk_preference': risk_preference,
        'total_slots': total_slots,
        'intervals': intervals,
        'counts': counts,
        'adjustment_factors': adjustment_factors
    }, tips


def plot_gradient_strategy(result, png_name='intervals.png'):
    """可视化梯度策略 - 优化X轴刻度和区间标签"""
    category = result['category']
    total_candidates = result['total_candidates']
    rank = result['rank']
    segment = result['segment']
    intervals = result['intervals']
    counts = result['counts']
    total_slots = result['total_slots']
    
    # 创建图形
    plt.figure(figsize=(14, 12))
    
    # 位次区间图
    plt.subplot(2, 1, 1)
    levels = ['gamble', 'reach', 'match', 'safe', 'anchor']
    level_names = ['赌', '冲', '稳', '保', '垫']
    colors = ['#FF6B6B', '#FFD166', '#06D6A0', '#118AB2', '#073B4C']
    
    # 确定X轴范围
    min_rank = min([intervals[level][0] for level in levels])
    max_rank = max([intervals[level][1] for level in levels])
    
    # 添加10%的边界缓冲
    rank_span = max_rank - min_rank
    x_min = max(1, int(min_rank - rank_span * 0.1))
    x_max = min(total_candidates, int(max_rank + rank_span * 0.1))
    
    # 动态设置刻度间隔
    if rank_span < 10000:  # 小范围
        x_ticks = np.linspace(x_min, x_max, num=10, dtype=int)
    elif rank_span < 100000:  # 中等范围
        step = max(1000, int(rank_span / 15))  # 至少1000名间隔
        x_ticks = np.arange(x_min, x_max + step, step)
    else:  # 大范围
        step = max(5000, int(rank_span / 20))  # 至少5000名间隔
        x_ticks = np.arange(x_min, x_max + step, step)
    
    # 绘制区间条
    for i, level in enumerate(levels):
        min_r, max_r = intervals[level]
        bar_width = max_r - min_r
        bar = plt.barh(level_names[i], bar_width, left=min_r, color=colors[i], 
                       edgecolor='black', height=0.7)
        
        # 添加区间范围标签
        label_x = min_r + bar_width / 2
        label_text = f"{min_r:,}~{max_r:,}"
        plt.text(label_x, i, label_text, ha='center', va='center', 
                 fontsize=10, fontweight='bold', color='white')
    
    # 标记考生位次
    plt.axvline(x=rank, color='red', linestyle='--', linewidth=2)
    plt.text(rank, 4.7, f'考生位次: {rank:,}', color='red', ha='center', 
             fontsize=12, weight='bold', bbox=dict(facecolor='white', alpha=0.8))
    
    # 标记分段位置（仅当在可视范围内）
    def add_segment_marker(segment_value, label):
        if x_min <= segment_value <= x_max:
            plt.axvline(x=segment_value, color='gray', linestyle=':', linewidth=1.5)
            plt.text(segment_value, 0.2, label, color='gray', ha='center', 
                     fontsize=9, bbox=dict(facecolor='white', alpha=0.7))
    
    if category == '普通类':
        high_segment = int(total_candidates * 0.05)
        medium_segment = int(total_candidates * 0.30)
        add_segment_marker(high_segment, f'高分段边界\n({high_segment:,}名)')
        add_segment_marker(medium_segment, f'中分段边界\n({medium_segment:,}名)')
    else:
        art_high_segment = int(total_candidates * 0.10)
        art_medium_segment = int(total_candidates * 0.50)
        add_segment_marker(art_high_segment, f'高分段边界\n({art_high_segment:,}名)')
        add_segment_marker(art_medium_segment, f'中分段边界\n({art_medium_segment:,}名)')
    
    # 设置图表属性
    plt.title(f'山东新高考{category}智能梯度策略\n(考生总数: {total_candidates:,}人 | 考生位次: {rank:,}名 | {segment}段)', 
              fontsize=16, pad=20)
    plt.xlabel('位次', fontsize=12)
    plt.gca().invert_yaxis()  # 反转Y轴使赌级在顶部
    plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x):,}'))
    plt.grid(axis='x', linestyle='--', alpha=0.7)
    
    # 设置X轴范围
    plt.xlim(x_min, x_max)
    plt.xticks(x_ticks, rotation=45)
    
    # 添加图例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=colors[0], label='赌'),
        Patch(facecolor=colors[1], label='冲'),
        Patch(facecolor=colors[2], label='稳'),
        Patch(facecolor=colors[3], label='保'),
        Patch(facecolor=colors[4], label='垫')
    ]
    plt.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.02, 1.15), 
               ncol=3, fontsize=10)
    
    # 志愿数量分配饼图
    plt.subplot(2, 1, 2)
    sizes = [counts[level] for level in levels]
    labels_with_count = [f'{name}级\n{size}个' for name, size in zip(level_names, sizes)]
    explode = (0.1, 0.05, 0, 0, 0)  # 突出赌级和冲级
    
    # 创建饼图
    wedges, texts, autotexts = plt.pie(sizes, explode=explode, labels=labels_with_count, 
                                       colors=colors, autopct='%1.1f%%', shadow=True, 
                                       startangle=140, textprops={'fontsize': 11})
    
    # 设置饼图文本样式
    for text in texts:
        text.set_fontsize(10)
    for autotext in autotexts:
        autotext.set_fontsize(9)
        autotext.set_color('white')
    
    plt.axis('equal')
    plt.title(f'{total_slots}个志愿分配比例', fontsize=14, pad=15)
    
    # 添加策略说明
    plt.figtext(0.5, 0.02, 
                f"注: 实际填报时需考虑专业热度、地域因素和招生计划变化对位次的影响", 
                ha="center", fontsize=10, color='#555555')
    
    plt.tight_layout(pad=3.0)
    plt.subplots_adjust(bottom=0.1, top=0.9)
    
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
# def get_gradient_file(record=None):
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
    # rank = 367087
    # category = "普通类"
    # year = "2024"
    # risk_preference = "均衡"
    # xk = "物化生"

    result, tips = calculate_gradient_intervals(
        rank, category, risk_preference, verbose=False
    )
    min_r, max_r = result["intervals"]["gamble"][0], result["intervals"]["anchor"][1]
    intervals = result["intervals"]
    app = Application()
    df = app.toudang_range(category, year, min_r, max_r)
    # print(len(df))
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

    timeout_seconds = 180
    check_interval = 3  # 每秒检查一次
    start_time = datetime.now()

    while not os.path.exists(file_path):
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed >= timeout_seconds:
            send_text(f"{file_path}文件未在180秒内生成", admin_list[0])
            raise TimeoutError(f"文件未在 {timeout_seconds} 秒内生成：{file_path}")
        time.sleep(check_interval)

    # 文件存在后发送
    send_file(os.path.join("temp", file_name), record.roomid)
