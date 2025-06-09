import mysql.connector
from mysql.connector import Error
import time
import re
from sendqueue import QueueDB, send_text
from config.config import Config

config = Config()
park_admin = config.get_config("park_admin")[0]


async def get_parking_records(record):
    r = re.match(r"车辆进出查询(\d*)", record.content)
    try:
        cnts = int(r.group(1))
    except:
        cnts = 10
    try:
        # 从配置文件获取数据库连接信息
        db_config = config.get_config("park_db")
        # 建立数据库连接
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()

            # 查询最新的10条记录，并格式化InOutTime
            query = """
                SELECT 
                    InOutTime,
                    Plate, 
                    UserName, 
                    IOType
                FROM inoutrecord 
                ORDER BY InOutTime DESC 
                LIMIT %s
            """
            cursor.execute(query, (cnts,))

            # 获取查询结果
            records = cursor.fetchall()
            date = records[-1][0].strftime("%Y-%m-%d")
            tips = f"{date}最新{cnts}条记录:"
            for record in sorted(records, key=lambda x: x[0], reverse=True):
                r_time = record[0].strftime("%H:%M:%S")
                tips += f"\n车辆{record[3]}:\n{r_time} {record[2]} {record[1]}"
            send_text(tips, park_admin, "parking")

    except Error as e:
        send_text(f"连接数据库时出错: {e}", park_admin, "parking")

    finally:
        if "connection" in locals() and connection.is_connected():
            cursor.close()
            connection.close()


record_list = []


def watching_parking():
    # send_text = print
    global record_list
    try:
        # 从配置文件获取数据库连接信息
        db_config = config.get_config("park_db")
        # 建立数据库连接
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()
            query = """
                SELECT 
                    InOutTime,
                    Plate, 
                    UserName, 
                    IOType
                FROM inoutrecord 
                ORDER BY InOutTime DESC 
                LIMIT 15
            """
            cursor.execute(query)

            # 获取查询结果
            records = cursor.fetchall()
            tips = ""
            # 如果是第一次运行，初始化record_list并发送通知
            if not record_list:
                date = records[-1][0].strftime("%Y-%m-%d")
                tips += f"{date}:"
                record_list = [record[0] for record in records]
                for record in sorted(records, key=lambda x: x[0]):
                    r_time = record[0].strftime("%H:%M:%S")
                    tips += f"\n{record[3][-1]}:{r_time} {record[1]} {record[2][0]}"
                send_text(tips, park_admin, "parking")
                return

            # 获取新记录的时间列表
            new_record_times = [record[0] for record in records]

            # 找出新增的记录
            new_records = [record for record in records if record[0] not in record_list]
            if not new_records:
                return

            date = new_records[-1][0].strftime("%Y-%m-%d")
            tips += f"{date}:"
            # 发送新增记录的通知
            for record in sorted(new_records, key=lambda x: x[0]):
                r_time = record[0].strftime("%H:%M:%S")
                tips += f"\n{record[3][-1]}:{r_time} {record[1]} {record[2][0]}"
                record_list.insert(0, record[0])
            record_list = record_list[:15]
            send_text(tips, park_admin, "parking")

    except Error as e:
        send_text(f"连接数据库时出错: {e}", park_admin, "parking")
        raise e

    finally:
        if "connection" in locals() and connection.is_connected():
            cursor.close()
            connection.close()
