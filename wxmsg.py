import json
from datetime import datetime
import re
import sqlite3


def process_nested_dict(d):
    """处理嵌套的字典，尝试解析可能是JSON的字符串"""
    if not isinstance(d, dict):
        return d

    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = process_nested_dict(v)
        elif (
            isinstance(v, str)
            and v
            and v.strip().startswith("{")
            and v.strip().endswith("}")
        ):
            # 尝试解析可能是JSON的字符串
            try:
                json_obj = json.loads(v)
                if isinstance(json_obj, dict):
                    d[k] = process_nested_dict(json_obj)
            except json.JSONDecodeError:
                # 记录详细错误信息但保持原始值不变
                pass
    return d


def filter_msg(msg):
    if not msg:
        return None
    try:
        if isinstance(msg, dict):
            return process_nested_dict(msg)
        return msg
    except Exception as e:
        print(f"处理消息失败: {e}")
        return None


class WxMsg:
    """微信消息
    Attributes:
        id (str): primary key
        type (int): 消息类型
        sender (str): 消息发送人
        roomid (str): （仅群消息有）群 id
        content (str): 消息内容
        ai_content (str): AI分析后的内容
        is_self (bool): 是否自己发的
        timestamp (int): 消息时间戳
        ext (str): 扩展信息
        thumb (str): 消息缩略图
    """

    def __init__(self, msg) -> None:
        # 确保输入是处理过的字典
        if isinstance(msg, dict):
            msg = filter_msg(msg)
        self.formate_msg(msg)

    def formate_msg(self, msg):
        # 使用字典的get方法替代getattr
        if isinstance(msg, dict):
            self.wxid = msg.get("wechatid", "")
            self.roomid = msg.get("friendid", "")
            self.is_self = True if msg.get("issend", "false") == "true" else False
            self.is_group = 1 if "@chatroom" in self.roomid else 0
            self.content = msg.get("content", "")
            self.type = msg.get("contenttype", 0)
            self.msg_id = msg.get("msgsvrid", "")
            self.create_time = msg.get("createTime", 0)
            self.ext = msg.get("ext", "")
        else:
            # 如果不是字典，尝试使用属性访问（兼容旧代码）
            self.wxid = getattr(msg, "wechatid", "")
            self.roomid = getattr(msg, "friendid", "")
            self.is_self = True if getattr(msg, "issend", "false") == "true" else False
            self.is_group = 1 if "@chatroom" in self.roomid else 0
            self.content = getattr(msg, "content", "")
            self.type = getattr(msg, "contenttype", 0)
            self.msg_id = getattr(msg, "msgsvrid", "")
            self.create_time = getattr(msg, "createTime", 0)
            self.ext = getattr(msg, "ext", "")
        
        self.thumb = ""
        self.is_at = self._is_at()
        self.parse_content()

    def parse_content(self):
        """解析消息内容"""
        content = self.content
        if isinstance(content, str):
            if ":" in content and "{" in content:
                parts = content.split(":", 1)
                if len(parts) > 1 and "{" in parts[1]:
                    self.sender = parts[0]
                    try:
                        json_content = json.loads(parts[1])
                        self.content = process_nested_dict(json_content)
                        self.thumb = json_content.get("Thumb", "")
                    except:
                        self.content = content
                        self.thumb = ""
            else:
                self.sender = (
                    self.roomid
                    if not self.is_group
                    else content.split(":\n")[0] if ":\n" in content else ""
                )
                self.content = (
                    content
                    if not self.is_group
                    else content.split(":\n")[1] if ":\n" in content else content
                )
                self.thumb = ""
        else:
            # 如果content已经是字典，直接使用
            self.sender = self.roomid

        # 根据消息类型处理内容
        self._process_by_type()

    def _process_by_type(self):
        """根据消息类型处理内容"""
        content = self.content
        
        # 处理不同类型的消息
        if self.type == 2:
            self.ext = self.content
            self.content = "[图片]"
            # 处理ext可能是字典的情况
            if isinstance(self.ext, dict) and "Thumb" in self.ext:
                self.thumb = self.ext["Thumb"]
            else:
                try:
                    self.thumb = self.ext.Thumb  # 兼容旧代码
                except (AttributeError, TypeError):
                    self.thumb = ""
        elif self.type == 3:
            self.sender = (
                self.roomid
                if not self.is_group
                else content.split(":http")[0] if isinstance(content, str) and ":http" in content else ""
            )
            self.ext = (
                content
                if not self.is_group
                else (
                    "http" + content.split(":http")[1]
                    if isinstance(content, str) and ":http" in content
                    else content
                )
            )
            self.content = "[语音消息]"
        elif self.type == 5:
            self.content = f"[系统消息] {self.content}"
        elif self.type == 6:
            self.ext = self.content
            # 处理ext可能是字典的情况
            if isinstance(self.ext, dict):
                title = self.ext.get("Title", "")
                type_str = self.ext.get("TypeStr", "")
                source = self.ext.get("Source", "")
            else:
                try:
                    title = self.ext.Title
                    type_str = self.ext.TypeStr
                    source = self.ext.Source
                except (AttributeError, TypeError):
                    title = type_str = source = ""
            self.content = f"[链接消息] {title} {type_str} {source}"
        # ... 其他类型的处理类似，这里简化为一个通用处理方法
        else:
            self._handle_other_types()

    def _handle_other_types(self):
        """处理其他类型的消息"""
        type_handlers = {
            8: self._handle_file,
            9: self._handle_card,
            10: self._handle_location,
            11: self._handle_redpacket,
            12: self._handle_transfer,
            13: self._handle_miniprogram,
            14: self._handle_emotion,
            15: self._handle_group_management,
            16: self._handle_redpacket_received,
            17: self._handle_group_system,
            18: self._handle_article,
            19: self._handle_voice_call,
            20: self._handle_video_call,
            21: self._handle_service_notification,
            22: self._handle_quote,
            23: self._handle_group_chain,
            24: self._handle_video_channel,
            25: self._handle_group_live,
            26: self._handle_pat,
            27: self._handle_share_music,
            28: self._handle_video_live,
            29: self._handle_customer_card,
            30: self._handle_enterprise_card,
            99: self._handle_unsupported,
        }
        
        handler = type_handlers.get(self.type)
        if handler:
            handler()

    def _handle_file(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("Title", "")
        else:
            try:
                title = self.ext.Title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[文件] {title}"

    def _handle_card(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            nickname = self.ext.get("Nickname", "")
        else:
            try:
                nickname = self.ext.Nickname
            except (AttributeError, TypeError):
                nickname = ""
        self.content = f"[名片] {nickname}"

    def _handle_location(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("Title", "")
        else:
            try:
                title = self.ext.Title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[位置] {title}"

    def _handle_redpacket(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("Title", "")
        else:
            try:
                title = self.ext.Title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[红包] {title}"

    def _handle_transfer(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            pay_subtype = self.ext.get("PaySubType", "")
            title = self.ext.get("Title", "")
            feedesc = self.ext.get("Feedesc", "")
        else:
            try:
                pay_subtype = self.ext.PaySubType
                title = self.ext.Title
                feedesc = self.ext.Feedesc
            except (AttributeError, TypeError):
                pay_subtype = title = feedesc = ""
        self.content = f"[转账{pay_subtype}] {title} {feedesc}"

    def _handle_miniprogram(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            source = self.ext.get("Source", "")
            title = self.ext.get("Title", "")
            thumb = self.ext.get("Thumb", "")
        else:
            try:
                source = self.ext.Source
                title = self.ext.Title
                thumb = self.ext.Thumb
            except (AttributeError, TypeError):
                source = title = thumb = ""
        self.content = f"[小程序] | {source} | {title}"
        self.thumb = thumb

    def _handle_emotion(self):
        self.ext = self.content
        self.content = "[微信表情]"

    def _handle_group_management(self):
        self.ext = self.content
        self.content = "[群管理消息]"

    def _handle_redpacket_received(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("Title", "")
        else:
            try:
                title = self.ext.Title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[领取红包消息] {title}"

    def _handle_group_system(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("title", "")
            user = self.ext.get("user", "")
        else:
            try:
                title = self.ext.title
                user = self.ext.user
            except (AttributeError, TypeError):
                title = user = ""
        self.content = f"[群聊系统消息] {title}"
        self.sender = user

    def _handle_article(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("Title", "")
        else:
            try:
                title = self.ext.Title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[公众号文章] {title}"

    def _handle_voice_call(self):
        self.ext = self.content
        self.content = "[语音通话]"

    def _handle_video_call(self):
        self.ext = self.content
        self.content = "[视频通话]"

    def _handle_service_notification(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("title", "")
        else:
            try:
                title = self.ext.title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[服务通知] {title}"

    def _handle_quote(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("title", "")
            display_name = self.ext.get("displayName", "")
            content = self.ext.get("content", "")
        else:
            try:
                title = self.ext.title
                display_name = self.ext.displayName
                content = self.ext.content
            except (AttributeError, TypeError):
                title = display_name = content = ""
        self.content = f"{title} \n [引用消息] {display_name}: {content}"

    def _handle_group_chain(self):
        self.ext = self.content
        self.content = "[群接龙]"

    def _handle_video_channel(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            des = self.ext.get("des", "")
        else:
            try:
                des = self.ext.des
            except (AttributeError, TypeError):
                des = ""
        self.content = f"[视频号消息] {des}"

    def _handle_group_live(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("Title", "")
        else:
            try:
                title = self.ext.Title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[群直播消息] {title}"

    def _handle_pat(self):
        self.content = f"[拍一拍] {self.content}"

    def _handle_share_music(self):
        self.ext = self.content
        self.content = "[分享音乐]"

    def _handle_video_live(self):
        self.ext = self.content
        self.content = "[视频号直播]"

    def _handle_customer_card(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("Title", "")
        else:
            try:
                title = self.ext.Title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[客服号名片] {title}"

    def _handle_enterprise_card(self):
        self.ext = self.content
        if isinstance(self.ext, dict):
            title = self.ext.get("Title", "")
        else:
            try:
                title = self.ext.Title
            except (AttributeError, TypeError):
                title = ""
        self.content = f"[企业微信名片] {title}"

    def _handle_unsupported(self):
        self.ext = self.content
        self.content = "[不支持的消息]"

    def __to_dict__(self):
        return {
            "wxid": self.wxid,
            "is_self": self.is_self,
            "is_group": self.is_group,
            "type": self.type,
            "msg_id": self.msg_id,
            "create_time": self.create_time,
            "sender": self.sender,
            "roomid": self.roomid,
            "content": self.content,
            "thumb": self.thumb,
            "ext": str(self.ext),
            "is_at": self._is_at(),
        }

    def __str__(self) -> str:
        # TODO: 根据联系人信息，显示联系人/群聊名称
        s = ""
        if self.is_self:
            s += f"### 发送消息 {self.msg_id} ###\n"
        else:
            s += f"### 收到消息 {self.msg_id} ###\n"
        if self.is_group:
            s += f"群聊消息：{self.roomid}\n"
        else:
            s += f"单聊消息\n"
        # 将毫秒时间戳转换为秒
        timestamp_seconds = self.create_time / 1000
        s += f"{self.sender} | {self.msg_id} | {datetime.fromtimestamp(timestamp_seconds)} | {self.type}"
        s += f"\ncontent: {self.content}"
        s += f"\nthumb: {self.thumb}" if self.thumb else ""
        s += f"\next: {self.ext}" if self.ext else ""
        return s

    def _is_at(self) -> bool:
        """是否被 @：群消息，在 @ 名单里，并且不是 @ 所有人"""
        if not self.is_group:
            return False  # 只有群消息才能 @

        if not self.wxid in self.ext:
            return False  # 不在 @ 清单里

        if re.findall(r"@(?:所有人|all|All)", self.content):
            return False  # 排除 @ 所有人

        return True


class MessageDB:
    """消息数据库"""

    def __enter__(self, db="databases/messages.db"):
        self.__conn__ = sqlite3.connect(db)
        self.__cursor__ = self.__conn__.cursor()
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        self.__conn__.commit()
        self.__conn__.close()

    def __create_table__(self):
        self.__cursor__.execute(
            """
            CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY autoincrement,
            wxid TEXT,
            msg_id TEXT,
            type INTEGER,
            sender TEXT,
            roomid TEXT,
            content TEXT,
            thumb TEXT,
            ext TEXT,
            is_at BOOLEAN,
            is_self BOOLEAN,
            is_group BOOLEAN,
            create_time INTEGER)"""
        )
        self.__conn__.commit()

    def insert(self, msg):
        self.__cursor__.execute(
            """
            INSERT INTO messages(wxid, msg_id, type, sender, roomid, content, thumb, ext, is_at, is_self, is_group, create_time)
            VALUES(:wxid, :msg_id, :type, :sender, :roomid, :content, :thumb, :ext, :is_at, :is_self, :is_group, :create_time)""",
            msg,
        )
        self.__conn__.commit()

    def select(self, msg_id):
        self.__cursor__.execute(
            """
            SELECT * FROM messages WHERE msg_id = :msg_id""",
            {"msg_id": msg_id},
        )
        result = self.__cursor__.fetchone()
        return result if result else None


if __name__ == "__main__":
    m = MessageDB()
    m.__enter__()
    m.__create_table__()
    m.__exit__()
