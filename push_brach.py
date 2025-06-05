import os
import sys
import getpass
from git import Repo, GitCommandError
import requests


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
    repo_path, branch_name, commit_message="自动提交", remote_name="origin"
):
    """
    将指定文件夹中的代码提交到远程分支

    参数:
        repo_path: 本地仓库路径
        branch_name: 要提交到的分支名称
        commit_message: 提交信息
        remote_name: 远程仓库名称

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


def main():
    # 获取GitHub个人访问令牌
    token = getpass.getpass("请输入GitHub个人访问令牌(PAT): ")

    # 登录GitHub
    if not login_github(token):
        print("登录失败，程序退出")
        sys.exit(1)

    # 获取仓库信息
    repo_path = input("请输入本地仓库路径: ")
    branch_name = input("请输入要提交的分支名称: ")
    commit_message = input("请输入提交信息(默认为'自动提交'): ") or "自动提交"
    remote_name = input("请输入远程仓库名称(默认为'origin'): ") or "origin"

    # 推送到远程分支
    result = push_branch(repo_path, branch_name, commit_message, remote_name)

    if result:
        print("操作成功完成")
    else:
        print("操作失败")


if __name__ == "__main__":
    main()
