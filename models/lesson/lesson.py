# _*_ coding: utf-8 _*_
# @Time: 2025/05/18
# @Author: Tech_T

from datetime import datetime, timedelta
import time
import threading
from config.log import LogConfig
from config.config import Config


class Lesson:
    _instance = None
    _lock = threading.Lock()  # 添加锁对象

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return
        self.initialized = True
        self.log = LogConfig().get_logger()
        self.config = Config()
        self.week_change = -5
        self._cache_ttl = 60 * 60 * 6
        self.lesson_dir = self.config.get_config("lesson_dir")
        self.admins = self.config.get_config("lesson_admin")
        self.refresh_cache()

    def refresh_cache(self):
        """刷新缓存"""
        self._last_refresh_time = time.time()
        # 清除所有缓存
        self._teacher_template_cache = None
        self._current_sechedule_cache = None
        self._class_template_cache = None
        self._contacts_cache = None
        self._time_table_cache = None
        # 重新加载数据
        try:
            self.current_month = self.month_info()
            self.week_info = self.get_week_info(next_week=False)
        except Exception as e:
            self.log.error(f"刷新缓存失败: {e}")
    
    @staticmethod
    def month_info():
        """获取当前月份"""
        return datetime.now().strftime("%Y%m")
    
    def get_week_info(self, next_week=False):
        """获取当前周数"""
        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # 如果是下周，则加7天
        if next_week:
            current_date += timedelta(days=7)
            
        # 获取当前周数
        current_week_number = current_date.isocalendar()[1] + self.week_change
        
        # 获取当前周的周一日期
        monday_date = current_date - timedelta(days=current_date.weekday())
        monday = monday_date.strftime('%Y%m%d')
        
        # 计算时间戳
        monday_timestamp = int(monday_date.timestamp())
        sunday_timestamp = int((monday_date + timedelta(days=7)).timestamp()) - 1
        
        return [current_week_number, monday, monday_timestamp, sunday_timestamp]