import json
from datetime import datetime
from types import SimpleNamespace
import re  # 添加缺失的导入


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
        self.is_self = getattr(msg, "issend", False)
        self.is_group = 1 if '@chatroom' in self.roomid else 0
        
        content = getattr(msg, "content", "")
        # 处理内容可能是JSON的情况
        if content and ':' in content and '{' in content:
            parts = content.split(':', 1)
            if len(parts) > 1 and '{' in parts[1]:
                self.sender = parts[0]
                try:
                    json_content = json.loads(parts[1])
                    self.content = parts[1]
                    self.thumb = json_content.get("Thumb", "")
                except:
                    self.content = content
                    self.thumb = ""
        else:
            self.sender = self.roomid if not self.is_group else content.split(':\n')[0] if ':\n' in content else ""
            self.content = content
            self.thumb = ""
            
        self.type = getattr(msg, "contenttype", 0)
        self.msg_id = getattr(msg, "msgsvrid", "")
        self.create_time = getattr(msg, "createTime", 0)
        self.ext = getattr(msg, "ext", "")

    def __to_dict__(self):
        return {
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
        }

    def __str__(self) -> str:
        s = f"{'自己发的:' if self.is_self else ''}"
        s += f"{self.sender}[{self.roomid}]|{self.msg_id}|{datetime.fromtimestamp(self.create_time)}|{self.type}"
        s += f"\n{self.content}"
        s += f"\n{self.thumb}"
        s += f"\n{self.ext}"
        return s

    def from_self(self) -> bool:
        """是否自己发的消息"""
        return self.is_self

    def from_group(self) -> bool:
        """是否群聊消息"""
        return self.is_group

    def is_at(self, wxid) -> bool:
        """是否被 @：群消息，在 @ 名单里，并且不是 @ 所有人"""
        if not self.from_group():
            return False  # 只有群消息才能 @

        if not self.wxid in self.ext:
            return False  # 不在 @ 清单里

        if re.findall(r"@(?:所有人|all|All)", self.content):
            return False  # 排除 @ 所有人

        return True

    def is_text(self) -> bool:
        """是否文本消息"""
        return self.type == 1

if __name__ == "__main__":
    msg = {'id': None, 'wechatid': 'wxid_3hio95ow9yh122', 'friendid': '56050207237@chatroom', 'msgsvrid': '4657847627768651992', 'issend': 'true', 'contenttype': 2, 'content': 'wxid_3hio95ow9yh122:{"Thumb":"http://b1.wcr222.top/0e2c4df62a691f11/2025/05/14/41658fc8b63e4172a4f10be967244210.jpg","Md5":""}', 'ext': '', 'type': 1, 'createTime': 1747209561316, 'owner': None, 'userContent': None}  
    wx_msg = WxMsg(msg).__to_dict__()
    print(wx_msg)