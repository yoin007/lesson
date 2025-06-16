# _*_ coding: utf-8 _*_
# @Time     : 2025/06/14 19:50
# @Author   : Tech_T
from config.config import Config
from sendqueue import send_text


async def bd_share(record):
    """
    百度分享
    :param record: 记录
    :return: 分享链接
    """
    content = record.content.replace(" ", "").replace("：", ":")
    s_list = content.split(":")
    if len(s_list) != 2:
        return ""
    else:
        tips = f"1. 复制上面的文字\n2. 打开百度网盘APP\n3. 保存到自己网盘\n4. 查看或下载资料\n请注意：链接随时可能失效，请保存到自己的网盘后查看下载。"
        share_list = Config().get_config("pan_share", "application.yaml")
        share_link = share_list.get(s_list[0]).get(s_list[1])
        if share_link is None:
            send_text("查询参数有误，有正确输入！", record.roomid)
            return "fail"
        else:
            tips = f"{share_link}\n\n提示：\n{tips}"
            send_text(tips, record.roomid)
            return "ok"
