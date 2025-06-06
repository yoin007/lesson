import os
import sys
import getpass
from git import Repo, GitCommandError
import requests
from config.config import Config
from datetime import datetime
from client import Client
from sendqueue import send_text


def login_github(token):
    """
    使用个人访问令牌(Personal Access Token)登录GitHub
    """
    try:
        # 使用GitHub API验证令牌
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        response = requests.get("https://api.github.com/user", headers=headers)

        if response.status_code == 200:
            print(
                f"成功登录GitHub，欢迎 {response.json()['name'] or response.json()['login']}"
            )
            return True
        else:
            print(f"登录失败: {response.json().get('message', '未知错误')}")
            return False
    except Exception as e:
        print(f"登录过程中发生错误: {str(e)}")
        return False

def push_branch(
    repo_path, branch_name, commit_message="自动提交", remote_name="origin",
    proxy=None
):
    """
    将指定文件夹中的代码提交到远程分支

    参数:
        repo_path: 本地仓库路径
        branch_name: 要提交到的分支名称
        commit_message: 提交信息
        remote_name: 远程仓库名称
        proxy: 代理地址，格式为 "http://代理服务器地址:端口" 或 "socks5://代理服务器地址:端口"，默认为 None

    返回:
        成功返回True，失败返回False
    """
    try:
        # 检查路径是否存在
        if not os.path.exists(repo_path):
            print(f"错误: 路径 '{repo_path}' 不存在")
            return False

        # 初始化仓库对象
        repo = Repo(repo_path)

        # 如果设置了代理，则配置 Git 使用代理
        if proxy:
            print(f"设置代理: {proxy}")
            with repo.config_writer() as git_config:
                git_config.set_value("http", "proxy", proxy)
                git_config.set_value("https", "proxy", proxy)

        # 检查远程仓库是否存在
        try:
            remote = repo.remote(name=remote_name)
        except ValueError:
            print(f"错误: 远程仓库 '{remote_name}' 不存在")
            return False

        # 获取所有远程分支
        remote_branches = []
        for ref in remote.refs:
            remote_branches.append(ref.name.replace(f"{remote_name}/", ""))

        # 检查分支是否存在于远程
        branch_exists_remotely = branch_name in remote_branches

        # 检查本地分支是否存在
        local_branch_exists = branch_name in [b.name for b in repo.branches]

        # 如果本地分支不存在
        if not local_branch_exists:
            # 如果远程分支存在，则创建本地分支并跟踪远程分支
            if branch_exists_remotely:
                print(f"创建本地分支 '{branch_name}' 并跟踪远程分支")
                repo.git.checkout("-b", branch_name, f"{remote_name}/{branch_name}")
            else:
                print(f"远程分支 '{branch_name}' 不存在，无法推送")
                return False
        else:
            # 切换到指定分支
            repo.git.checkout(branch_name)

        # 添加所有更改
        repo.git.add(".")

        # 提交更改
        if repo.is_dirty():
            repo.git.commit("-m", commit_message)
            print(f"已提交更改: {commit_message}")
        else:
            print("没有需要提交的更改")

        # 推送到远程
        repo.git.push(remote_name, branch_name)
        print(f"成功推送到 {remote_name}/{branch_name}")

        return True
    except GitCommandError as e:
        print(f"Git命令错误: {str(e)}")
        return False
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return False

def get_qrcode(roomid, png_path):
    c = Client()
    r = c.group_qr(roomid)

    if r:
        rsp = requests.get(r)
        if rsp.status_code == 200:
            with open(png_path, "wb") as f:
                f.write(rsp.content)
            print("二维码已保存到", png_path)
            return True
    else:
        print("获取二维码失败")
        return False


def push_qrcode():
    admin = Config().get_config("admin")
    try:
        # 获取GitHub个人访问令牌
        token = Config().get_config("git_token")
        # 登录GitHub
        if not login_github(token):
            print("登录失败，程序退出")
            send_text("github登录失败，程序退出", admin)
            sys.exit(1)
        
        # 获取群号
        qrcode_git = Config().get_config("qrcode_git")
        if not qrcode_git:
            print("未配置群号，程序退出")
            send_text("未配置更新二维码群号，程序退出", admin)
            sys.exit(1)

        # 推送二维码
        branch_name = "main"
        commit_message = f"自动提交 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        remote_name = "origin"
        proxy = Config().get_config("proxy")
        root_path = Config().get_config("qr_root")
        for name, roomid in qrcode_git.items():
            repo_path = os.path.join(root_path, name)
            png_path = os.path.join(repo_path, "1.png")
            if get_qrcode(roomid, png_path):
                if push_branch(repo_path, branch_name, commit_message, remote_name, proxy=proxy):
                    send_text(f"{name}二维码推送成功", admin)
                else:
                    send_text(f"{name}推送失败", admin)

    except Exception as e:
        print(f"发生错误: {str(e)}")
        send_text(f"更新二位码发生错误: {str(e)}", admin)

async def change_roomid(record):
    text = record.content
    _, name, roomid = text.split("-")
    if 'chatroom' not in roomid:
        send_text("请输入正确的群号", record.sender)
        return False
    qrcode_git = Config().get_config("qrcode_git")
    if name in qrcode_git:
        qrcode_git[name] = roomid
        if Config().modify_config("qrcode_git", qrcode_git):
            print("修改成功")
            send_text("修改群成功", record.sender)
    else:
        print("未找到该群号")
        send_text("未找到该群号", record.sender)