# _*_ coding: utf-8 _*_
# @Time: 2025/06/16 21:31
# @Author: Tech_T

import sqlite3
from datetime import datetime
import pandas as pd
from config.log import LogConfig
from sendqueue import send_text, send_image
from models.lesson.lesson import Lesson


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
            app.__cursor__.execute(sql)
            results = app.__cursor__.fetchall()
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
            tips += f"薪酬待遇：{result[13]}\n" if result[13] else ""
            tips += f"选课要求：{result[14]}\n" if result[14] else ""
            tips += f"考研方向：{result[15]}\n" if result[15] else ""
            tips += f"社会名人：{result[16]}\n" if result[16] else ""
            tips += f"专业介绍：{result[6]}" if result[6] else ""
            tips += "+" * 15 + "\n"
        return tips

    def query_yx(self, yxmc):
        if yxmc == "":
            return "请输入院校名称"
        sql = f"select * from schools where school_name='{yxmc}'"
        with self as app:
            app.__cursor__.execute(sql)
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
    
    def rank_to_score(self, rank, category, year):
        """
        专业排名转分数
        :param rank: 专业排名
        :param category: 专业类别
        :param year: 年份
        :return: 分数
        """
        if rank == "" or category == "" or year == "":
            return -1
        if category == '普通类':
            table_name = 'putongfenshuduan'
            query = f"""
            SELECT 分数
            FROM {table_name}
            WHERE 年份 = ? AND 累计人数 <= ?
            ORDER BY 累计人数 DESC
            LIMIT 1
            """
        elif category == '美术类':
            table_name = 'meishufenshuduan'
            query = f"""
            SELECT 分数
            FROM {table_name}
            WHERE 年份 = ? AND 累计人数 <= ? AND 类型 = '综合分'
            ORDER BY 累计人数 DESC
            LIMIT 1
            """
        with self as app:
            app.__cursor__.execute(query, (year, rank))
            result = app.__cursor__.fetchone()
        if result:
            return result[0]
        else:
            return -1

    def score_to_rank(self, score, category, year):
        """
        专业分数转排名
        :param score: 专业分数
        :param category: 专业类别
        :param year: 年份
        :return: 排名
        """
        if score == "" or category == "" or year == "":
            return -1
        if category == '普通类':
            table_name = 'putongfenshuduan'
            query = f"""
            SELECT 累计人数
            FROM {table_name}
            WHERE 年份 =? AND 分数 <=?
            ORDER BY 分数 DESC
            LIMIT 1
            """
        elif category == '美术类':
            table_name ='meishufenshuduan'
            query = f"""
            SELECT 累计人数
            FROM {table_name}
            WHERE 年份 =? AND 分数 <=? AND 类型 = '综合分'
            ORDER BY 分数 DESC
            LIMIT 1
            """
        with self as app:
            app.__cursor__.execute(query, (year, score))
            result = app.__cursor__.fetchone()
        if result:
            return result[0]
        else:
            return -1
        

    def toudang(self, category, zy, year='', yx='', rank=10, level='本科', counts=30):
        """
        查询专业
        :param zy: 专业
        :return: 专业
        """
        conditions = []
        params = []
        table_name = ''
        if zy:
            conditions.append("专业 LIKE ?")
            params.append(f"%{zy}%")
        if yx:
            conditions.append("院校 = ?")
            params.append(yx)
        print(year)
        if year:
            conditions.append("年份 = ?")
            params.append(year)
        if category:
            conditions.append("类型 =?")
            params.append(category)
            if category == '美术类':
                table_name = 'meishutoudang'
            elif category == '普通类':
                table_name = 'putongtoudang'
        if rank:
            if category == '美术类':
                rank = self.rank_to_score(rank, '美术类', year)
            conditions.append("最低位次 <=?")
            params.append(rank)
        if level:
            conditions.append("层次 = ?")
            params.append(level)
        where_clause = " AND ".join(conditions)
        sql = f"SELECT * FROM {table_name} WHERE {where_clause}" if conditions else "SELECT * FROM toudang"
        # print(sql)
        # print(params)
        with self as app:
            app.__cursor__.execute(sql, params)
            results = app.__cursor__.fetchall()
        if not results:
            return pd.DateFrame()
        results = results[:counts]
        if category == '美术类':
            df = pd.DataFrame(results, columns=['类型', '年份', '批次', '层次', '专业', '院校', '计划数', '最低分数', '院校代码'])
            df['最低分数'] = pd.to_numeric(df['最低分数'], errors='coerce').astype(float)
            df.sort_values(by='最低分数', ascending = False, inplace=True)
            df['位次'] = df.apply(lambda row: self.score_to_rank(row['最低分数'], row['类型'], row['年份']), axis=1)
        elif category == '普通类':
            df = pd.DataFrame(results, columns=['类型', '年份', '批次', '层次', '专业', '院校', '计划数', '最低位次', '院校代码'])
            df['最低位次'] = pd.to_numeric(df['最低位次'], errors='coerce').astype(int)
            df.sort_values(by='最低位次', ascending = True, inplace=True)
            df['分数'] = df.apply(lambda row: self.rank_to_score(row['最低位次'], row['类型'], row['年份']), axis=1)
        return df

def df_to_png(df, png_name, title):
    """
    将DataFrame转换为PNG图片
    :param df: DataFrame
    :return: PNG图片
    """
    if df.empty:
        return None
    l = Lesson()
    png = l.df_to_png(df, png_name, title, index_name='序号')
    add_watermark(png[0], png[0], '公众号：技术田言', 'simhei.ttf',36 , 0.8, 211)
    path = png[0][len(l.lesson_dir) :].replace("\\", "/")
    return path

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

async def zy_template(record):
    tips = "<专业投档>\n类别:美术类\n专业:不能为空\n年份:2024\n院校:可以为空\n位次:1000\n层次:本科"
    send_text(tips, record.roomid)

async def yx_template(record):
    tips = "<院校投档>\n类别:美术类\n专业:可以为空\n年份:2024\n院校:不能为空)\n层次:本科"
    send_text(tips, record.roomid)

async def zy_toudang(record=None):
    app = Application()
    text = record.content.replace(" ", "").replace("：", ":").split("\n")
    if len(text) != 7:
        send_text("查询参数有误，请参照下面的模板重新输入！", record.roomid)
        tips = "<专业投档>\n类别:美术类\n专业:不能为空\n年份:2024\n院校:可以为空\n位次:1000\n层次:本科"
        send_text(tips, record.roomid)
        return None
    
    df = app.toudang(text[1].split(':')[-1], text[2].split(':')[-1], text[3].split(':')[-1], text[4].split(':')[-1], text[5].split(':')[-1], text[6].split(':')[-1])
    png_name = record.roomid + '.png'
    title = f"{text[3].split(':')[-1]} {text[4].split(':')[-1]}{text[1].split(':')[-1]}{text[2].split(':')[-1]}投档情况"
    png = df_to_png(df, png_name, title)
    print(png)
    send_image(png, record.roomid)
    return -1

async def yx_toudang(record=None):
    app = Application()
    text = record.content.replace(" ", "").replace("：", ":").split("\n")
    # text = ['', '美术类', '', '2024', '北京师范大学', '本科']
    if len(text)!= 6:
        send_text("查询参数有误，请参照下面的模板重新输入！", record.roomid)
        tips = "<院校投档>\n类别:美术类\n专业:可以为空\n年份:2024\n院校:不能为空)\n层次:本科"
        send_text(tips, record.roomid)
        return 0

    df = app.toudang(text[1].split(':')[-1], text[2].split(':')[-1], text[3].split(':')[-1], text[4].split(':')[-1], 0, text[5].split(':')[-1], 1000)
    png_name = record.roomid + '.png'
    # png_name = 'yx.png'
    title = f"{text[3].split(':')[-1]} {text[4].split(':')[-1]}{text[1].split(':')[-1]}{text[2].split(':')[-1]}投档情况"
    png = df_to_png(df, png_name, title)
    send_image(png, record.roomid)
    return -1


from PIL import Image, ImageDraw, ImageFont

def add_watermark(image_path, output_path, watermark_text, font_path, font_size, opacity, step):
    # 打开图片
    image = Image.open(image_path).convert('RGBA')
    width, height = image.size
    # 创建一个与原图大小相同的透明图层用于绘制水印
    watermark_layer = Image.new('RGBA', image.size, (255, 255, 255, 0))
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
            rotated_text = Image.new('RGBA', (text_width, text_height), (255, 255, 255, 0))
            text_draw = ImageDraw.Draw(rotated_text)
            # 指定水印颜色为绿色
            text_draw.text((0, 0), watermark_text, font=font, fill=(0, 255, 0, int(255 * opacity)))
            rotated_text = rotated_text.rotate(30, expand=True)
            watermark_layer.paste(rotated_text, position, rotated_text)
            y += step
        x += text_width + step

    # 将水印图层与原图合并
    result = Image.alpha_composite(image, watermark_layer)
    # 保存添加水印后的图片
    result.save(output_path)