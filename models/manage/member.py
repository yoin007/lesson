# _*_ coding:utf-8 _*_
# @Time:2025/05/20
# @Author: Tech_T

import re
import sqlite3
from config.log import LogConfig
from config.config import Config
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
        insert_count = 0
        try:
            with self as m:
                for contact in contacts_list:
                    if contact["friendid"] not in contacts:
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
                        insert_count += m.__cursor__.rowcount
                    else:
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
                        updated_count += m.__cursor__.rowcount
                self.__conn__.commit()

            if updated_count > 0 or insert_count > 0:
                self.log.info(f"更新联系人成功，更新{updated_count}条数据")
                self.log.info(f"插入联系人成功，插入{insert_count}条数据")
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

    def member_info(self, uuid=""):
        """获取成员信息"""
        if uuid == "":
            with self as m:
                m.__cursor__.execute("SELECT * FROM member")
                result = m.__cursor__.fetchall()
            return result if result else None
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

    def delte_permission(self, id):
        """删除权限"""
        with self as m:
            m.__cursor__.execute("DELETE FROM permission WHERE id =?", (id,))
            self.__conn__.commit()
            return m.__cursor__.rowcount

    def permission_info(self, func=""):
        """获取权限信息"""
        if func == "":
            with self as m:
                m.__cursor__.execute("SELECT * FROM permission")
                result = m.__cursor__.fetchall()
            return result if result else None
        with self as m:
            m.__cursor__.execute("SELECT * FROM permission WHERE func =?", (func,))
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
    if text == "权限查询":
        with Member() as m:
            permission_list = m.permission_func_list()
        if not permission_list:
            send_text("权限查询失败：权限列表为空", record.sender)
            return None
        tips = "权限列表：\n"
        for permission in permission_list:
            tips += (
                f"id：{permission[0]}，名称：{permission[1]}，模式：{permission[2]}\n"
            )
        send_text(tips, record.sender)
        return None
    pid = re.match(r"权限查询-(\d+)$", text)
    if not pid:
        send_text("权限查询失败：请检查查询指令！", record.sender)
        return None
    pid = pid.group(1)
    with Member() as m:
        permission = m.permission_info(pid)
    if not permission:
        send_text("权限查询失败：权限不存在", record.sender)
        return None
    tips = (
        f"权限ID：{permission[0]}\n"
        f"功能：{permission[1]}\n"
        f"功能名称：{permission[2]}\n"
        f"是否启用：{permission[3]}\n"
        f"黑名单：{permission[4]}\n"
        f"白名单：{permission[5]}\n"
        f"类型：{permission[6]}\n"
        f"匹配模式：{permission[7]}\n"
        f"关键词：{permission[8]}\n"
        f"AI标记：{permission[9]}\n"
        f"是否需要@：{permission[10]}\n"
        f"回复内容：{permission[11]}\n"
        f"所属模块：{permission[12]}\n"
        f"权限等级：{permission[13]}\n"
        f"使用示例：{permission[14]}\n"
        f"权限检查：{permission[15]}\n"
        f"所需积分：{permission[16]}\n"
        f"所需余额：{permission[17]}"
    )
    send_text(tips, record.sender)
    return None


async def insert_permission(record):
    """插入权限"""
    text = record.content.replace("+权限\n", "")

    # 使用正则表达式匹配各个字段
    func = re.search(r"功能：(.+)\n", text)
    func_name = re.search(r"功能名称：(.+)\n", text)
    activate = re.search(r"是否启用：(.+)\n", text)
    black_list = re.search(r"黑名单：(.+)\n", text)
    white_list = re.search(r"白名单：(.+)\n", text)
    type_val = re.search(r"类型：(.+)\n", text)
    pattern = re.search(r"匹配模式：(.+)\n", text)
    keywords = re.search(r"关键词：(.+)\n", text)
    ai_flag = re.search(r"AI标记：(.+)\n", text)
    need_at = re.search(r"是否需要@：(.+)\n", text)
    # 使用非贪婪匹配和多行模式来获取回复内容
    reply = re.search(r"回复内容：([\s\S]*?)\n所属模块", text)
    module = re.search(r"所属模块：(.+)\n", text)
    level = re.search(r"权限等级：(.+)\n", text)
    example = re.search(r"使用示例：(.+)\n", text)
    check_permission = re.search(r"权限检查：(.+)\n", text)
    score = re.search(r"所需积分：(.+)\n", text)
    balance = re.search(r"所需余额：(.+)", text)
    # 处理回复内容的多行文本，去除首尾空白字符
    reply_content = reply.group(1).strip() if reply else ""
    # 验证必要字段
    if not all([func, func_name, pattern]):
        send_text(
            "添加权限失败：缺少必要字段（功能、功能名称、匹配模式）", record.sender
        )
        return None

    with Member() as m:
        result = m.insert_permission(
            func=func.group(1),
            func_name=func_name.group(1),
            activate=int(activate.group(1)) if activate else 1,
            black_list=(
                black_list.group(1)
                if black_list and black_list.group(1) != "None"
                else ""
            ),
            white_list=(
                white_list.group(1)
                if white_list and white_list.group(1) != "None"
                else ""
            ),
            type=type_val.group(1) if type_val and type_val.group(1) != "None" else "",
            pattern=pattern.group(1),
            keywords=(
                keywords.group(1) if keywords and keywords.group(1) != "None" else ""
            ),
            ai_flag=int(ai_flag.group(1)) if ai_flag else 0,
            need_at=int(need_at.group(1)) if need_at else 0,
            reply=reply_content,
            module=module.group(1) if module and module.group(1) != "None" else "",
            level=int(level.group(1)) if level else 1,
            example=example.group(1) if example and example.group(1) != "None" else "",
            check_permission=int(check_permission.group(1)) if check_permission else 1,
            score=int(score.group(1)) if score else 0,
            balance=int(balance.group(1)) if balance else 0,
        )

    if result > 0:
        send_text("添加权限成功", record.sender)
    else:
        send_text("添加权限失败", record.sender)
    return None


async def add_member(record):
    """插入会员：+会员：abc-10-lesson"""
    level = 1
    model = "basic"
    if "@chatroom" in record.roomid:
        send_text("群会员添加功能暂未实现！", record.sender)
        return 0
    results = record.content.split("-")
    if len(results) >= 3:
        try:
            level = results[1]
            model = model + "/" + results[2]
            member_str = (
                record.content.replace("：", ":")
                .replace(" ", "")
                .split("-")[0]
                .split(":")[1]
            )
            member_list = member_str.split(",")
            for mb in member_list:
                with Member() as m:
                    row = m.member_info(mb)
                if row:
                    send_text(f"会员已存在: {mb}", record.sender)
                else:
                    name = ""
                    alias = m.wxid_remark(mb)
                    if alias:
                        name = alias[0] if alias[0] else alias[1]
                    print(name, alias)
                    if name:
                        with Member() as m:
                            r = m.insert_member(mb, mb, name, level=level, model=model)
                            if r >= 1:
                                send_text(f"添加会员：{mb} {name}", record.sender)
                                return 0
                    send_text(
                        f"添加会员出错：{record.msg_id} {record.content}", record.sender
                    )
                    return -1
        except Exception as e:
            send_text(f"添加会员出错3：{record.msg_id}-{str(e)}", record.sender)
            return -1


async def del_member(record):
    """删除会员"""
    member_str = (
        record.content.replace("-会员", "")
        .replace("：", ":")
        .replace(" ", "")
        .split(":")[1]
    )
    member_list = member_str.split(",")
    for mb in member_list:
        with Member() as m:
            r = m.delte_member(mb)
            if r >= 1:
                send_text(f"删除会员：{mb}")
                return 0
    send_text(f"删除会员出错：{record.msg_id} {record.content}", record.sender)
    return -1


async def query_members(record):
    """查询会员"""
    with Member() as m:
        member_list = m.member_info()
    if not member_list:
        send_text("查询会员失败：会员列表为空", record.sender)
        return None
    tips = f"当前共有{len(member_list)}位会员：\n"
    for member in member_list:
        tips += f"uuid：{member[1]}, alias:{member[3]},level:{member[6]},model:{member[7]}\n"
    send_text(tips, record.sender)
    return None


async def start_func(record):
    """启动功能"""
    if record.sender not in Config().get_config("admin_list"):
        send_text("权限不足", record.sender)
        return None
    pattern = r"^START (.*)"
    match = re.search(pattern, record.content)
    if match:
        func_id = match.group(1)
        try:
            with Member() as m:
                m.activate_func(func_id)
                send_text(f"start_func: {func_id}", record.sender)
                return True
        except Exception as e:
            self.log.error(f"start_func Failed: {e}")
            send_text(f"start_func Failed: {e}", record.sender)
            return False


async def stop_func(record: any):
    if record.sender not in Config().get_config("admin_list"):
        return False
    pattern = r"^STOP (.*)"
    match = re.search(pattern, record.content)
    if match:
        func_id = match.group(1)
        try:
            with Member() as m:
                m.deactivate_func(func_id)
                send_text(f"stop_func: {func_id}", record.sender)
                return True
        except Exception as e:
            self.log.error(f"stop_func Failed: {e}")
            send_text(f"stop_func Failed: {e}", record.sender)
            return False


def check_permission(func):
    async def wrapper(record, *args, **kwargs):
        if has_permission(func, record, *args, **kwargs):
            return await func(record, *args, **kwargs)
        else:
            send_text(
                f"{record.msg_id}-{func.__name__}:鉴权失败,请联系管理员吧",
                record.sender,
            )
            return None

    return wrapper


def has_permission(func, record, *args, **kwargs):
    # TODO: 积分和余额的判断
    if record.is_group:
        uuid = record.sender + "#" + record.roomid
    else:
        uuid = record.sender
    with Member() as m:
        member_info = m.member_info(uuid)
        permission = m.permission_info(func.__name__)
    if not permission:
        send_text(f"{record.msg_id}-{func.__name__}:未注册权限", record.roomid)
        return False
    if permission[15] == 0:
        return True
    if not member_info:
        send_text(f"{record.msg_id}:未注册会员", record.roomid)
        return False
    if int(permission[13]) > int(member_info[6]):
        send_text(f"{record.msg_id}-{func.__name__}:会员等级不足", record.roomid)
        return False
    if permission[12] not in member_info[7].split("/"):
        send_text(f"{record.msg_id}-{func.__name__}:会员模块不足", record.roomid)
        return False
    return True
