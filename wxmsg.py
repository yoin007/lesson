import json
from datetime import datetime
from types import SimpleNamespace
import re  # 添加缺失的导入
import sqlite3

def dict_to_obj(d):
    """将字典转换为对象，处理嵌套的情况"""
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = dict_to_obj(v)
        elif isinstance(v, str) and v.startswith('{') and v.endswith('}'):
            # 尝试解析可能是JSON的字符串
            try:
                json_obj = json.loads(v)
                if isinstance(json_obj, dict):
                    d[k] = dict_to_obj(json_obj)
            except:
                pass  # 如果不是有效的JSON，保持原样
    return SimpleNamespace(**d)

def filter_msg(msg):
    msg = dict_to_obj(msg)
    return msg

class WxMsg():
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
        # 确保输入是对象而不是字典
        if isinstance(msg, dict):
            msg = filter_msg(msg)
        self.formate_msg(msg)
    
    def formate_msg(self, msg):
        self.wxid = getattr(msg, "wechatid", "")
        self.roomid = getattr(msg, "friendid", "")
        self.is_self = True if getattr(msg, "issend", 'false') == 'true' else False
        self.is_group = 1 if '@chatroom' in self.roomid else 0
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
            if ':' in content and '{' in content:
                parts = content.split(':', 1)
                if len(parts) > 1 and '{' in parts[1]:
                    self.sender = parts[0]
                    try:
                        json_content = json.loads(parts[1])
                        self.content = dict_to_obj(json_content)
                        self.thumb = json_content.get("Thumb", "")
                    except:
                        self.content = content
                        self.thumb = ""
            else:
                self.sender = self.roomid if not self.is_group else content.split(':\n')[0] if ':\n' in content else ""
                self.content = content if not self.is_group else content.split(':\n')[1] if ':\n' in content else content
                self.thumb = ""
        else:
            # 如果content已经是对象，直接使用
            self.sender = self.roomid
            
        match self.type:
            case 2:
                self.ext = self.content
                self.content = f"[图片]"
                self.thumb = self.ext.Thumb
            case 3:
                self.sender = self.roomid if not self.is_group else content.split(':http')[0] if ':http' in content else ""
                self.ext = content if not self.is_group else 'http'+ content.split(':http')[1] if ':http' in content else content
                self.content = '[语音消息]'
            case 5:
                self.content = f'[系统消息] {self.content}'
            case 6:
                self.ext = self.content
                self.content = f"[链接消息] {self.ext.Title} {self.ext.TypeStr} {self.ext.Source}"
            case 8:
                self.ext = self.content
                self.content = f"[文件] {self.ext.Title}"
            case 9:
                self.ext = self.content
                self.content = f"[名片] {self.ext.Nickname}"
            case 10:
                self.ext = self.content
                self.content = f"[位置] {self.ext.Title}"
            case 11:
                self.ext = self.content
                self.content = f"[红包] {self.ext.Title}"
            case 12:
                self.ext = self.content
                self.content = f"[转账{self.ext.PaySubType}] {self.ext.Title} {self.ext.Feedesc}"
            case 13:
                self.ext = self.content
                self.content = f"[小程序] | {self.ext.Source} | {self.ext.Title}"
                self.thumb = self.ext.Thumb
            case 14:
                self.ext = self.content
                self.content = '[微信表情]'
            case 15:
                self.ext = self.content
                self.content = f"[群管理消息]"
            case 16:
                self.ext = self.content
                self.content = f"[领取红包消息] {self.ext.Title}"
            case 17:
                self.ext = self.content
                self.content = f"[群聊系统消息] {self.ext.title}"
                self.sender = self.ext.user
            case 18:
                self.ext = self.content
                self.content = f"[公众号文章] {self.ext.Title}"
            case 19:
                self.ext = self.content
                self.content = f"[语音通话]"
            case 20:
                self.ext = self.content
                self.content = f"[视频通话]"
            case 21:
                self.ext = self.content
                self.content = f"[服务通知] {self.ext.title}"
            case 22:
                self.ext = self.content
                self.content = f"{self.ext.title} \n [引用消息] {self.ext.displayName}: {self.ext.content}"
            case 23:
                self.ext = self.content
                self.content = f"[群接龙]"
            case 24:
                self.ext = self.content
                self.content = f"[视频号消息] {self.ext.des}"
            case 25:
                self.ext = self.content
                self.content = f"[群直播消息] {self.ext.Title}"
            case 26:
                self.content = f"[拍一拍] {self.content}"
            case 27:
                self.ext = self.content
                self.content = f"[分享音乐]"
            case 28:
                self.ext = self.content
                self.content = f"[视频号直播]"
            case 29:
                self.ext = self.content
                self.content = f"[客服号名片] {self.ext.Title}"
            case 30:
                self.ext = self.content
                self.content = f"[企业微信名片] {self.ext.Title}"
            case 99:
                self.ext = self.content
                self.content = f"[不支持的消息]"

    def __to_dict__(self):
        return {
            'wxid': self.wxid,
            'is_self': self.is_self,
            'is_group': self.is_group,
            'type': self.type,
            'msg_id': self.msg_id,
            'create_time': self.create_time,
            'sender': self.sender,
            'roomid': self.roomid,
            'content': self.content,
            'thumb': self.thumb,
            'ext': self.ext,
            'is_at': self._is_at(),
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

class MessageDB():
    """消息数据库"""
    def __enter__(self, db = 'databases/messages.db'):
        self.__conn__ = sqlite3.connect(db)
        self.__cursor__ = self.__conn__.cursor()
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        self.__conn__.commit()
        self.__conn__.close()

    def __create_table__(self):
        self.__cursor__.execute('''
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
            create_time INTEGER)''')
        self.__conn__.commit()

    def insert(self, msg):
        self.__cursor__.execute('''
            INSERT INTO messages(wxid, msg_id, type, sender, roomid, content, thumb, ext, is_at, is_self, is_group, create_time)
            VALUES(:wxid, :msg_id, :type, :sender, :roomid, :content, :thumb, :ext, :is_at, :is_self, :is_group, :create_time)''', msg)
        self.__conn__.commit()
    
    def select(self, msg_id):
        self.__cursor__.execute('''
            SELECT * FROM messages WHERE msg_id = :msg_id''', {'msg_id': msg_id})
        result =  self.__cursor__.fetchone()
        return result if result else None
        

if __name__ == "__main__":
    m = MessageDB()
    m.__enter__()
    m.__create_table__()
    m.__exit__()