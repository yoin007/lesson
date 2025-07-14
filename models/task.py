# _*_ coding: utf-8 _*_
# @Time: 2025/05/26 15:27
# @Author: Tech_T

import asyncio
import datetime
import json
import random
import re
import sqlite3
import threading
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sendqueue import send_text
from config.log import LogConfig
from models.api import ZPAI, gk_countdown
from models.parking import watching_parking
from models.lesson.lesson import (
    refresh_schedule,
    today_teachers,
    create_month_dir,
    clear_temp_file,
)
from models.push_brach import push_qrcode


def parse_datetime(date_str):
    # 解析字符串为datetime对象
    try:
        datetime_obj = datetime.datetime.strptime(date_str, "%Y%m%d %H:%M:%S")
        year = datetime_obj.year
        month = datetime_obj.month
        day = datetime_obj.day
    except ValueError:
        year, month, day = 0, 0, 0
        hms = re.findall(r":", date_str)
        if len(hms) == 2:
            datetime_obj = datetime.datetime.strptime(date_str, "%H:%M:%S")
        else:
            datetime_obj = datetime.datetime.strptime(date_str, "%H:%M")
    # 提取年月日时分秒
    hour = datetime_obj.hour
    minute = datetime_obj.minute
    second = datetime_obj.second
    # 返回年月日时分秒列表
    return [year, month, day, hour, minute, second]


class Task:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scheduler.configure(timezone="Asia/Shanghai")
        self.log = LogConfig().get_logger()
        self.job_args = {}
        self.__enter__()

    def __enter__(self, db="databases/task.db"):
        self.__conn__ = sqlite3.connect(db)
        self.__cursor__ = self.__conn__.cursor()
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        if self.__conn__:
            self.__conn__.close()

    def __create_table__(self):
        try:
            self.__cursor__.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    func TEXT NOT NULL,
                    type TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    trigger_args TEXT NOT NULL,
                    args TEXT,
                    kwargs TEXT,
                    one_off BOOLEAN DEFAULT 1,
                    description TEXT,
                    consumed BOOLEAN DEFAULT 0
                )
                """
            )
            self.__conn__.commit()
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print("tasks already exists.")
            else:
                raise e
        except Exception as e:
            raise e

    def add_job(self, func, trigger, *args, **kwargs):
        job = self.scheduler.add_job(func, trigger, *args, **kwargs)
        if len(args) > 0:
            self.job_args[job.id] = args[0]
        if len(kwargs) > 0:
            # 检查 kwargs 中是否有 kwargs 键
            if "kwargs" in kwargs and "func" in kwargs["kwargs"]:
                self.job_args[job.id] = str(kwargs["kwargs"]["func"])
            # 直接检查 kwargs 中是否有 func 键
            elif "func" in kwargs:
                self.job_args[job.id] = str(kwargs["func"])
        return job

    def add_job_cron(self, func, date_str, *args, **kwargs):
        year, month, day, hour, minute, second = parse_datetime(date_str)
        if year == 0:
            trigger = IntervalTrigger(seconds=second, minutes=minute, hours=hour)
        else:
            trigger = CronTrigger(
                year=year, month=month, day=day, hour=hour, minute=minute, second=second
            )
        job = self.add_job(func, trigger, *args, **kwargs)
        return job

    def add_job_interval(self, func, seconds, *args, **kwargs):
        trigger = IntervalTrigger(seconds=seconds)
        job = self.add_job(func, trigger, *args, **kwargs)
        return job

    def random_daily_task(
        self, func, start_time="00:00:00", end_time="23:59:59", *args, **kwargs
    ):
        # 将字符串时间转换为datetime对象
        time_format = "%H:%M:%S"
        time_s = datetime.datetime.strptime(start_time, time_format)
        time_e = datetime.datetime.strptime(end_time, time_format)

        # 确保a在b之前
        if time_s > time_e:
            time_s, time_e = time_e, time_s

        # 计算时间差
        delta = time_e - time_s
        # 随机生成时间差
        random_seconds = random.randrange(int(delta.total_seconds()))
        # 生成随机时间
        random_time = time_s + datetime.timedelta(seconds=random_seconds)
        hour, minute, second = random_time.hour, random_time.minute, random_time.second
        # 计算下次运行的时间
        next_run_time = datetime.datetime.now().replace(
            hour=int(hour), minute=int(minute), second=int(second)
        )
        # 如果下次运行的时间已经过去，则将时间设置为明天的同一时间
        if next_run_time < datetime.datetime.now():
            next_run_time += datetime.timedelta(days=1)

        # 更新任务的触发器
        trigger = CronTrigger(
            year=next_run_time.year,
            month=next_run_time.month,
            day=next_run_time.day,
            hour=next_run_time.hour,
            minute=next_run_time.minute,
            second=next_run_time.second,
        )

        # 添加任务
        self.scheduler.add_job(func, trigger, *args, **kwargs)

    def show_tasks(self):
        jobs = self.scheduler.get_jobs()
        now = datetime.datetime.now()
        now_str = now.strftime("%H:%M:%S")
        tips = f"当前任务列表：{now_str}\n"
        cnt = 1
        for job in jobs:
            try:
                args = self.job_args[job.id]
            except:
                args = ""
            tips += f"{cnt}. {job.name}:\n {job.id}\n{args}\n{job.trigger}\n"
            if job.next_run_time:
                tips += f'下次运行时间：{job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")}\n\n'
            cnt += 1
        return tips

    def remove_task(self, job_id):
        self.scheduler.remove_job(job_id)
        try:
            del self.job_args[job_id]
        except:
            pass
        return True

    async def start(self):
        self.scheduler.start()

    async def stop(self):
        self.scheduler.shutdown()

    async def run(self, duration: int):
        await self.start()
        await asyncio.sleep(duration)
        await self.stop()

    def add_task_to_db(
        self,
        func_name,
        trigger_type,
        trigger_args,
        args=None,
        kwargs=None,
        description=None,
        one_off=True,
        consumed=False,
    ):
        """
        将任务添加到数据库
        :param func_name: 函数名称
        :param trigger_type: 触发器类型 (cron, interval)
        :param trigger_args: 触发器参数 (JSON格式)
        :param args: 函数参数
        :param kwargs: 函数关键字参数
        :param description: 任务描述
        :return: 任务ID
        """
        try:
            args_json = json.dumps(args) if args else None
            kwargs_json = json.dumps(kwargs) if kwargs else None

            self.__cursor__.execute(
                "INSERT INTO tasks (func, type, trigger_type, trigger_args, args, kwargs, description, one_off, consumed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    func_name,
                    "function",
                    trigger_type,
                    trigger_args,
                    args_json,
                    kwargs_json,
                    description,
                    one_off,
                    consumed,
                ),
            )
            self.__conn__.commit()
            return self.__cursor__.lastrowid
        except Exception as e:
            print(f"添加任务到数据库失败: {e}")
            return None

    def get_tasks_from_db(self):
        """
        从数据库获取所有启用的任务
        :return: 任务列表
        """
        try:
            self.__cursor__.execute("SELECT * FROM tasks WHERE consumed = 0")
            # self.__cursor__.execute("SELECT * FROM tasks")
            return self.__cursor__.fetchall()
        except Exception as e:
            print(f"从数据库获取任务失败: {e}")
            return []

    # 在Task类中添加以下方法
    def update_task_consumed(self, task_id, consumed=True):
        """
        更新任务的consumed状态
        :param task_id: 任务ID
        :param consumed: 是否已消费
        :return: 是否更新成功
        """
        try:
            # 创建新的数据库连接，确保在当前线程中使用
            with sqlite3.connect("databases/task.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tasks SET consumed = ? WHERE id = ? AND one_off = 1",
                    (consumed, task_id),
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"更新任务状态失败: {e}")
            return False


task_scheduler = Task()


async def get_task_list(record):
    tips = task_scheduler.show_tasks()
    send_text(tips, record.roomid)


async def stop_task(record):
    content = record.content
    match = re.match(r"^\-任务-(.*)", content)
    if not match:
        send_text("无效的任务ID格式，请使用'停止任务-{任务ID}'的格式", record.roomid)
        return

    job_id = match.group(1)
    tips = task_scheduler.remove_task(job_id)
    send_text(f"任务 {job_id} 已{'停止' if tips else '停止失败'}", record.roomid)


async def add_cron_remind(record):
    # TODO: 根据 提醒的 人员 添加 人员的单独提醒， ai_renmind_text 返回list，遍历list实现
    content = record.content
    if "提醒" not in content:
        return
    zp = ZPAI()
    r = zp.ai_remind_text(content).split("-")
    time_str = r[1]
    reminder_text = r[2]
    try:
        # 解析时间字符串，获取触发器参数
        year, month, day, hour, minute, second = parse_datetime(time_str)
        if year == 0:
            trigger_args = {}
            if hour > 0:
                trigger_args["hour"] = hour
            if minute > 0:
                trigger_args["minute"] = minute
            if second > 0:
                trigger_args["second"] = second
        else:
            trigger_args = {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
            }

        # 将任务添加到数据库
        kwargs = {"content": reminder_text, "receiver": record.roomid}
        task_id = task_scheduler.add_task_to_db(
            func_name="send_text",
            trigger_type="cron",
            trigger_args=json.dumps(trigger_args),
            kwargs=kwargs,
            description=f"提醒：{reminder_text}",
            one_off=True,  # 一次性任务
            consumed=False,
        )

        # 包装函数，使其在执行后更新consumed状态
        wrapped_func = task_wrapper(
            lambda: send_text(f"提醒：{reminder_text}", record.roomid), task_id
        )

        # 创建触发器
        if year == 0:
            trigger = CronTrigger(**trigger_args)
        else:
            trigger = CronTrigger(**trigger_args)

        # 添加任务到调度器
        job = task_scheduler.add_job(wrapped_func, trigger)

        send_text(
            f"已设置提醒：{time_str} - {reminder_text}\n任务ID：{job.id}",
            record.roomid,
        )
    except Exception as e:
        send_text(f"设置提醒失败：{str(e)}", record.roomid)


async def task_start():
    # 首先添加默认任务到数据库（如果不存在）
    init_default_tasks()

    # 打印调试信息
    print("开始加载任务...")

    # 从数据库加载任务
    try:
        load_tasks_from_db()
    except Exception as e:
        print(f"加载任务时出错: {e}")

    # 运行调度器
    await task_scheduler.run(3600 * 24 * 30)  # 运行30天


def init_default_tasks():
    """初始化默认任务到数据库（如果不存在）"""
    # 检查数据库中是否已有任务
    tasks = task_scheduler.get_tasks_from_db()
    if tasks:
        print("数据库中已有任务，不再初始化默认任务")
        return  # 已有任务，不需要初始化

    # 添加默认任务到数据库
    # 1. 刷新课程表任务
    task_scheduler.add_task_to_db(
        func_name="random_daily_task",
        trigger_type="cron",
        trigger_args=json.dumps({"hour": 3}),
        kwargs=json.dumps(
            {
                "func": "refresh_schedule",
                "start_time": "07:11:02",
                "end_time": "07:17:10",
            }
        ),
        description="每日刷新课程表",
        one_off=False,
        consumed=False,
    )

    # 2. 今日教师任务
    task_scheduler.add_task_to_db(
        func_name="today_teachers",
        trigger_type="cron",
        trigger_args=json.dumps({"hour": 2}),
        kwargs=json.dumps(
            {"func": "today_teachers", "start_time": "07:20:02", "end_time": "07:35:10"}
        ),
        description="每日推送今日教师",
        one_off=False,
        consumed=False,
    )

    # 3. 高考倒计时任务
    task_scheduler.add_task_to_db(
        func_name="gk_countdown",
        trigger_type="cron",
        trigger_args=json.dumps({"hour": 1}),
        kwargs=json.dumps(
            {"func": "gk_countdown", "start_time": "08:01:02", "end_time": "08:14:10"}
        ),
        description="高考倒计时",
        one_off=False,
        consumed=False,
    )

    # 4. 监控停车场任务
    task_scheduler.add_task_to_db(
        func_name="watching_parking",
        trigger_type="interval",
        trigger_args=json.dumps({"seconds": 60}),
        description="监控停车场",
        one_off=False,
        consumed=False,
    )

    # 5. 创建月份目录任务
    task_scheduler.add_task_to_db(
        func_name="create_month_dir",
        trigger_type="cron",
        trigger_args=json.dumps({"day": 1}),
        description="每月创建月份目录",
        one_off=False,
        consumed=False,
    )


# 在load_tasks_from_db函数之前添加以下函数
def task_wrapper(func, task_id):
    """
    任务包装器，在任务执行后更新consumed状态
    :param func: 原始任务函数
    :param task_id: 任务ID
    :return: 包装后的函数
    """

    def wrapper(*args, **kwargs):
        # 执行原始任务
        result = func(*args, **kwargs)
        # 更新任务状态
        task_scheduler.update_task_consumed(task_id)
        return result

    return wrapper


# def watching_parking():
#     """监控停车场任务"""
#     print("监控停车场任务")


def load_tasks_from_db():
    """从数据库加载任务到调度器"""
    # 函数映射表
    function_map = {
        "send_text": send_text,
        "gk_countdown": gk_countdown,
        "today_teachers": today_teachers,
        "watching_parking": watching_parking,
        "random_daily_task": task_scheduler.random_daily_task,
        "refresh_schedule": refresh_schedule,
        "create_month_dir": create_month_dir,
        "push_qrcode": push_qrcode,
        "clear_temp_file": clear_temp_file,
    }

    # 从数据库获取所有启用的任务
    tasks = task_scheduler.get_tasks_from_db()

    for task in tasks:
        task_id, func_name, task_type, trigger_type, trigger_args = (
            task[0],
            task[1],
            task[2],
            task[3],
            task[4],
        )
        args_json, kwargs_json = task[5], task[6]
        one_off = task[7]  # 获取one_off字段

        # 解析参数
        args = json.loads(args_json) if args_json else []
        # 处理kwargs_json，确保最终得到一个字典
        if isinstance(kwargs_json, str):
            try:
                # 第一次解析
                parsed_kwargs = json.loads(kwargs_json) if kwargs_json else {}
                # 检查解析结果是否仍然是字符串（可能是双重编码）
                if isinstance(parsed_kwargs, str):
                    try:
                        # 尝试第二次解析
                        kwargs = json.loads(parsed_kwargs)
                    except json.JSONDecodeError:
                        print(f"无法二次解析kwargs_json: {parsed_kwargs}")
                        kwargs = {}
                else:
                    kwargs = parsed_kwargs
            except json.JSONDecodeError:
                print(f"无法解析kwargs_json: {kwargs_json}")
                kwargs = {}
        else:
            kwargs = kwargs_json if kwargs_json else {}
        trigger_args = json.loads(trigger_args)

        # 获取函数对象
        if func_name in function_map:
            func = function_map[func_name]
        else:
            print(f"未知函数: {func_name}，跳过该任务")
            continue

        # 创建触发器
        if trigger_type == "cron":
            trigger = CronTrigger(**trigger_args)
        elif trigger_type == "interval":
            trigger = IntervalTrigger(**trigger_args)
        else:
            print(f"未知触发器类型: {trigger_type}，跳过该任务")
            continue

        # 特殊处理 random_daily_task
        if func_name == "random_daily_task" and "func" in kwargs.keys():
            func_key = kwargs["func"]
            if isinstance(func_key, str) and func_key in function_map:
                kwargs["func"] = function_map[func_key]
            else:
                print(f"未知函数: {func_key}，跳过该任务")
                continue  # 如果func_key不是有效的函数名，跳过这个任务

        # 如果是一次性任务，使用包装器包装函数
        if one_off:
            wrapped_func = task_wrapper(func, task_id)
        else:
            wrapped_func = func

        # 添加任务到调度器
        try:
            job = task_scheduler.add_job(
                wrapped_func, trigger, args=args, kwargs=kwargs
            )
            task_scheduler.log.info(f"{func_name}任务已添加到调度器，任务ID: {task_id}")
            # 更新任务下次运行时间
            if hasattr(job, "next_run_time") and job.next_run_time:
                next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"添加任务 {func_name} (ID: {task_id}) 失败: {e}")
            print(f"参数: args={args}, kwargs={kwargs}")


def incert_task_from_excel(excel_file, func_name='send_text', trigger_type='cron', description='', one_off=True, consumed=False):
    """从Excel文件导入任务"""
    import pandas as pd
    from datetime import datetime
    
    # 解析Excel文件
    df = pd.read_excel(excel_file)
    # 遍历DataFrame中的每一行
    for index, row in df.iterrows():
        # print(row)
        
        # 确保日期是datetime对象
        if isinstance(row['日期'], str):
            date_obj = datetime.strptime(row['日期'], '%Y-%m-%d %H:%M:%S')
        else:
            date_obj = row['日期']
            
        year = date_obj.year
        month = date_obj.month
        day = date_obj.day
        
        time_str = row['时间']
        hour, minute = map(int, str(time_str).split(':'))
        second = 0
        trigger_args = {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
            }
        args = []
        aters = 'notify@all' if row['AT'] else ''
        kwargs = {
            "content": row['提醒内容'],
            "receiver": row['接收者'],
            "aters": aters,
        }
        # 将任务添加到数据库
        task_id = task_scheduler.add_task_to_db(
            func_name,
            trigger_type,
            json.dumps(trigger_args),
            args,
            kwargs,
            description,
            one_off,
            consumed,  
        )
        print(f"任务 {task_id} 已添加到数据库")

