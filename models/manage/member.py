# _*_ coding:utf-8 _*_
# @Time:2025/05/20
# @Author: Tech_T

import sqlite3
from config.log import LogConfig
from client import Client
from sendqueue import send_text


class Member:
    def __init__(self):
        self.__conn__ = None
        self.__cursor__ = None
        self.log = LogConfig().get_logger()

    def __enter__(self, db="databases/member.db"):
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
                CREATE TABLE IF NOT EXISTS member (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT,
                    wxid TEXT,
                    alias TEXT,
                    score INTEGER DEFAULT 50,
                    balance INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    model Text,
                    ai_flag BOOLEAN DEFAULT 0,
                    birthday TEXT,
                    active BOOLEAN DEFAULT 1,
                    create_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    note TEXT
                )
            """
            )
            self.__conn__.commit()
            self.log.info("Member table created successfully.")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                self.log.warning("Member table already exists.")
            else:
                self.log.error(f"Error creating Member table: {e}")
                raise e

        try:
            self.__cursor__.execute(
                """
                CREATE TABLE IF NOT EXISTS contacts(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wxid TEXT,
                    wxid_re TEXT,
                    remark TEXT,
                    nick_name TEXT,
                    phone TEXT,
                    sex TEXT,
                    city TEXT,
                    province TEXT,
                    country TEXT,
                    notes TEXT
                )
            """
            )
            self.__conn__.commit()
            self.log.info("Contacts table created successfully.")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                self.log.warning("Contacts table already exists.")
            else:
                self.log.error(f"Error creating Contacts table: {e}")
                raise e

        try:
            self.__cursor__.execute(
                """
                CREATE TABLE IF NOT EXISTS permission(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    func TEXT,
                    func_name TEXT,
                    activate BOOLEAN DEFAULT 1,
                    black_list TEXT,
                    white_list TEXT,
                    type TEXT,
                    pattern TEXT,
                    keywords TEXT,
                    ai_flag BOOLEAN DEFAULT 0,
                    need_at BOOLEAN DEFAULT 0,
                    reply TEXT,
                    module TEXT,
                    level INTEGER DEFAULT 1,
                    example TEXT,
                    check_permission BOOLEAN DEFAULT 0,
                    score INTEGER DEFAULT 0,
                    balance INTEGER DEFAULT 0,
                    create_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            """
            )
            self.__conn__.commit()
            self.log.info("Permission table created successfully.")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                self.log.warning("Permission table already exists.")
            else:
                self.log.error(f"Error creating Permission table: {e}")
                raise e

        try:
            self.__cursor__.execute(
                """
                CREATE TABLE IF NOT EXISTS chatroom(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    roomid TEXT,
                    room_name TEXT
                )
            """
            )
            self.__conn__.commit()
            self.log.info("Chatroom table created successfully.")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                self.log.warning("Chatroom table already exists.")
            else:
                self.log.error(f"Error creating Chatroom table: {e}")
                raise e

    @staticmethod
    def wx_contacts(content_type=0):
        """获取微信联系人"""
        client = Client()
        contacts = client.contact_info(content_type)
        return contacts

    def db_contacts(self):
        """获取数据库联系人"""
        with self as m:
            m.__cursor__.execute("SELECT wxid FROM contacts")
            contacts = [contact[0] for contact in m.__cursor__.fetchall()]
        return contacts

    def db_chatroom(self):
        """获取数据库群聊"""
        with self as m:
            m.__cursor__.execute("SELECT roomid FROM chatroom")
            chatroom = [chatroom[0] for chatroom in m.__cursor__.fetchall()]
        return chatroom

    def update_contacts(self):
        """更新本地数据库联系人"""
        contacts_list = self.wx_contacts()
        contacts = self.db_contacts()
        updated_count = 0
        try:
            for contact in contacts_list:
                if contact["friendid"] not in contacts:
                    with self as m:
                        m.__cursor__.execute(
                            """
                            INSERT INTO contacts (wxid, wxid_re, remark, nick_name, phone, sex, city, province, country, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                contact["friendid"],
                                contact["friend_wechatno"],
                                contact["memo"],
                                contact["nickname"],
                                contact["phone"],
                                contact["gender"],
                                contact["city"],
                                contact["province"],
                                contact["country"],
                                "",
                            ),
                        )
                        self.__conn__.commit()
                        updated_count += m.__cursor__.rowcount
                else:
                    with self as m:
                        m.__cursor__.execute(
                            """
                            UPDATE contacts SET wxid_re = ?, remark = ?, nick_name = ?, phone = ?, sex = ?, city = ?, province = ?, country = ?
                            WHERE wxid = ?
                        """,
                            (
                                contact["friend_wechatno"],
                                contact["memo"],
                                contact["nickname"],
                                contact["phone"],
                                contact["gender"],
                                contact["city"],
                                contact["province"],
                                contact["country"],
                                contact["friendid"],
                            ),
                        )
                        self.__conn__.commit()
                        updated_count += m.__cursor__.rowcount

            if updated_count > 0:
                self.log.info(f"更新联系人成功，更新{updated_count}条数据")
                return True
            else:
                self.log.info("联系人无更新")
                return False
        except Exception as e:
            self.log.error(f"更新联系人失败：{e}")
            return False

    def update_chatroom(self):
        """更新本地数据库群聊"""
        wx_chatroom = self.wx_contacts(1)
        # print(wx_chatroom)
        chatroom_list = self.db_chatroom()
        updated_count = 0
        try:
            for chatroom in wx_chatroom:
                with self as m:
                    if chatroom["friendid"] not in chatroom_list:
                        m.__cursor__.execute(
                            """
                            INSERT INTO chatroom (roomid, room_name)
                            VALUES (?,?)
                        """,
                            (chatroom["friendid"], chatroom["nickname"]),
                        )
                        self.__conn__.commit()
                        updated_count += m.__cursor__.rowcount
                    else:
                        m.__cursor__.execute(
                            """
                            UPDATE chatroom SET room_name =?
                            WHERE roomid =?
                        """,
                            (chatroom["nickname"], chatroom["friendid"]),
                        )
                        self.__conn__.commit()
                        updated_count += m.__cursor__.rowcount

            if updated_count > 0:
                self.log.info(f"更新群聊成功，更新{updated_count}条数据")
                return True
            else:
                self.log.info("群聊无更新")
                return False
        except Exception as e:
            self.log.error(f"更新群聊失败：{e}")
            return False

    def wxid_remark(self, wxid):
        """获取微信联系人备注"""
        with self as m:
            m.__cursor__.execute(
                "SELECT remark, nick_name FROM contacts WHERE wxid =?", (wxid,)
            )
            result = m.__cursor__.fetchone()
            if not result:
                self.update_contacts()
                with self as m:
                    m.__cursor__.execute(
                        "SELECT remark, nick_name FROM contacts WHERE wxid =?", (wxid,)
                    )
                    result = m.__cursor__.fetchone()
        return result if result else ("", "")

    def chatroom_name(self, roomid):
        """获取群聊名称"""
        with self as m:
            m.__cursor__.execute(
                "SELECT room_name FROM chatroom WHERE roomid =?", (roomid,)
            )
            result = m.__cursor__.fetchone()
            if not result:
                self.update_chatroom()
                with self as m:
                    m.__cursor__.execute(
                        "SELECT room_name FROM chatroom WHERE roomid =?", (roomid,)
                    )
                    result = m.__cursor__.fetchone()
        return result if result else ("",)

    def insert_member(
        self,
        uuid,
        wxid,
        alias,
        score=50,
        balance=0,
        level=1,
        model="basic",
        ai_flag=0,
        birthday="",
        active=1,
        note="",
    ):
        """插入成员"""
        with self as m:
            m.__cursor__.execute(
                """
                INSERT INTO member (uuid, wxid, alias, score, balance, level, model, ai_flag, birthday, active, note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    uuid,
                    wxid,
                    alias,
                    score,
                    balance,
                    level,
                    model,
                    ai_flag,
                    birthday,
                    active,
                    note,
                ),
            )
            self.__conn__.commit()
            return m.__cursor__.rowcount

    def delte_member(self, uuid):
        """删除成员"""
        with self as m:
            m.__cursor__.execute("DELETE FROM member WHERE uuid =?", (uuid,))
            self.__conn__.commit()
            return m.__cursor__.rowcount

    def member_info(self, uuid):
        """获取成员信息"""
        with self as m:
            m.__cursor__.execute("SELECT * FROM member WHERE uuid =?", (uuid,))
            result = m.__cursor__.fetchone()
        return result if result else None

    def insert_permission(
        self,
        func,
        func_name,
        activate=1,
        black_list="",
        white_list="",
        type="",
        pattern="",
        keywords="",
        ai_flag=0,
        need_at=0,
        reply="",
        module="",
        level=1,
        example="",
        check_permission=1,
        score=0,
        balance=0,
        note="",
    ):
        """插入权限"""
        with self as m:
            m.__cursor__.execute(
                """
                INSERT INTO permission (func, func_name, activate, black_list, white_list, type, pattern, keywords, ai_flag, need_at, reply, module, level, example, check_permission, score, balance, note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    func,
                    func_name,
                    activate,
                    black_list,
                    white_list,
                    type,
                    pattern,
                    keywords,
                    ai_flag,
                    need_at,
                    reply,
                    module,
                    level,
                    example,
                    check_permission,
                    score,
                    balance,
                    note,
                ),
            )
            self.__conn__.commit()
            return m.__cursor__.rowcount

    def delte_permission(self, func):
        """删除权限"""
        with self as m:
            m.__cursor__.execute("DELETE FROM permission WHERE func =?", (func,))
            self.__conn__.commit()
            return m.__cursor__.rowcount

    def permission_info(self, id=0):
        """获取权限信息"""
        if id == 0:
            with self as m:
                m.__cursor__.execute("SELECT * FROM permission")
                result = m.__cursor__.fetchall()
            return result if result else None
        with self as m:
            m.__cursor__.execute("SELECT * FROM permission WHERE id =?", (id,))
            result = m.__cursor__.fetchone()
        return result if result else None

    def permission_func_list(self):
        """获取权限列表"""
        with self as m:
            m.__cursor__.execute("SELECT id, func, pattern FROM permission")
            result = m.__cursor__.fetchall()
        return result if result else None

    def activate_func(self, id):
        """激活函数"""
        with self as m:
            m.__cursor__.execute(
                "UPDATE permission SET activate =? WHERE id =?", (1, id)
            )
            self.__conn__.commit()
            return m.__cursor__.rowcount

    def deactivate_func(self, id):
        """禁用函数"""
        with self as m:
            m.__cursor__.execute(
                "UPDATE permission SET activate =? WHERE id =?", (0, id)
            )
            self.__conn__.commit()
            return m.__cursor__.rowcount

async def query_permission(record):
    """查询权限"""
    text = record.content
    if text == '权限查询':
        with Member() as m:
            permission_list = m.permission_func_list()
        if not permission_list:
            send_text('权限查询失败：权限列表为空', record.sender)
            return None
        tips = '权限列表：\n'
        for permission in permission_list:
            tips += f"id：{permission[0]}，名称：{permission[1]}，模式：{permission[2]}\n"
        send_text(tips, record.sender)
        return None
    pid = re.match(r"权限查询-(\d+)$", text)
    if not pid:
        send_text('权限查询失败：请检查查询指令！', record.sender)
        return None
    pid = pid.group(1)
    with Member() as m:
        permission = m.permission_info(pid)
    if not permission:
        send_text('权限查询失败：权限不存在', record.sender)
        return None
    tips = f"权限id：{permission[0]}\n" \
           f"权限名称：{permission[1]}\n" \
           f"权限状态：{'激活' if permission[2] else '禁用'}\n" \
           f"黑名单：{permission[3]}\n" \
           f"白名单：{permission[4]}\n" \
           f"权限类型：{permission[5]}\n" \
           f"权限模式：{permission[6]}\n" \
           f"关键词：{permission[7]}\n" \
           f"AI模式：{'开启' if permission[8] else '关闭'}\n" \
           f"@机器人：{'开启' if permission[9] else '关闭'}\n" \
           f"回复内容：{permission[10]}\n" \
           f"模块：{permission[11]}\n" \
           f"权限等级：{permission[12]}\n" \
           f"示例：{permission[13]}\n" \
           f"权限检查：{'开启' if permission[14] else '关闭'}\n" \
           f"积分：{permission[15]}\n" \
           f"余额：{permission[16]}\n" \
           f"备注：{permission[17]}"
    send_text(tips, record.sender)
    return None