#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件管理小程序 - GitHub文件同步管理器
功能：本地文件管理 + GitHub云端同步 + 多端查看
作者：AI Assistant
版本：3.2.0
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import sys
import json
import shutil
import base64
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import threading
import time
import ssl
import certifi

try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

if not os.environ.get('SSL_CERT_FILE'):
    os.environ['SSL_CERT_FILE'] = certifi.where()

try:
    from github import Github, GithubException
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".file_manager")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("FileManager")


class FileItem:
    """
    文件实体类
    用于表示单个文件或文件夹的元数据和操作
    """
    
    def __init__(self, file_id: str, file_name: str, file_type: str, 
                 file_size: int, local_path: str, github_path: str = "", 
                 update_time: str = "", sync_status: str = "未同步",
                 is_folder: bool = False):
        self.id = file_id
        self.file_name = file_name
        self.file_type = file_type
        self.file_size = file_size
        self.local_path = local_path
        self.github_path = github_path
        self.update_time = update_time
        self.sync_status = sync_status
        self.is_folder = is_folder
    
    def format_size(self) -> str:
        """格式化文件大小为人类可读格式"""
        if self.is_folder:
            return "<文件夹>"
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    def to_dict(self) -> dict:
        """将文件对象序列化为字典"""
        return {
            'id': self.id,
            'file_name': self.file_name,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'local_path': self.local_path,
            'github_path': self.github_path,
            'update_time': self.update_time,
            'sync_status': self.sync_status,
            'is_folder': self.is_folder
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FileItem':
        """从字典反序列化文件对象"""
        return cls(
            file_id=data.get('id', ''),
            file_name=data.get('file_name', ''),
            file_type=data.get('file_type', ''),
            file_size=data.get('file_size', 0),
            local_path=data.get('local_path', ''),
            github_path=data.get('github_path', ''),
            update_time=data.get('update_time', ''),
            sync_status=data.get('sync_status', '未同步'),
            is_folder=data.get('is_folder', False)
        )
    
    def is_text_file(self) -> bool:
        """判断是否为可预览的文本文件"""
        if self.is_folder:
            return False
        text_extensions = {
            '.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml',
            '.yaml', '.yml', '.ini', '.cfg', '.conf', '.log', '.csv',
            '.c', '.cpp', '.h', '.java', '.go', '.rs', '.rb', '.php',
            '.sql', '.sh', '.bat', '.ps1', '.vue', '.jsx', '.tsx', '.ts'
        }
        _, ext = os.path.splitext(self.file_name.lower())
        return ext in text_extensions
    
    def get_category(self) -> str:
        """获取文件分类"""
        if self.is_folder:
            return "文件夹"
        _, ext = os.path.splitext(self.file_name.lower())
        
        doc_extensions = {'.txt', '.md', '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx'}
        code_extensions = {'.py', '.js', '.html', '.css', '.java', '.c', '.cpp', '.go', '.rs', '.php', '.sql', '.sh'}
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico', '.webp'}
        archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'}
        
        if ext in doc_extensions:
            return "文档"
        elif ext in code_extensions:
            return "代码"
        elif ext in image_extensions:
            return "图片"
        elif ext in archive_extensions:
            return "压缩包"
        else:
            return "其他"
    
    def get_icon(self) -> str:
        """获取文件图标"""
        if self.is_folder:
            return "📁"
        category = self.get_category()
        icons = {
            "文档": "📄",
            "代码": "💻",
            "图片": "🖼️",
            "压缩包": "📦",
            "其他": "📎"
        }
        return icons.get(category, "📎")


class GitHubSync:
    """
    GitHub云端同步类
    负责与GitHub仓库的交互操作
    """
    
    def __init__(self):
        self.github_token = ""
        self.repo_name = ""
        self.branch = "main"
        self.github_api = None
        self.repo = None
        self.connected = False
        self.error_msg = ""
    
    def connect(self, token: str, repo_name: str, branch: str = "main") -> Tuple[bool, str]:
        """
        连接GitHub仓库
        参数：token - GitHub访问令牌
             repo_name - 仓库名称（格式：用户名/仓库名）
             branch - 分支名称
        返回：(是否成功, 错误信息)
        """
        if not GITHUB_AVAILABLE:
            return False, "PyGitHub库未安装，请运行：pip install PyGithub"
        
        try:
            self.github_token = token
            self.repo_name = repo_name
            self.branch = branch
            
            self.github_api = Github(token)
            self.repo = self.github_api.get_repo(repo_name)
            
            test_branch = self.repo.get_branch(branch)
            self.connected = True
            return True, "连接成功"
            
        except Exception as e:
            self.connected = False
            error_msg = str(e)
            if "401" in error_msg:
                return False, "GitHub令牌无效或已过期"
            elif "404" in error_msg:
                return False, f"仓库 '{repo_name}' 不存在或无访问权限"
            elif "rate limit" in error_msg.lower():
                return False, "GitHub API访问频率限制，请稍后再试"
            else:
                return False, f"连接失败：{error_msg}"
    
    def push_file(self, local_path: str, github_path: str) -> Tuple[bool, str]:
        """
        推送文件到GitHub仓库
        参数：local_path - 本地文件路径
             github_path - GitHub仓库中的路径
        返回：(是否成功, 错误信息)
        """
        if not self.connected:
            return False, "未连接到GitHub，请先配置连接"

        try:
            with open(local_path, 'rb') as f:
                content = f.read()

            file_size = len(content)
            MAX_FILE_SIZE = 100 * 1024 * 1024
            if file_size > MAX_FILE_SIZE:
                return False, f"文件过大，GitHub单文件限制{MAX_FILE_SIZE // (1024*1024)}MB"

            try:
                existing_file = self.repo.get_contents(github_path, ref=self.branch)
                self.repo.update_file(
                    path=github_path,
                    message=f"更新文件: {os.path.basename(github_path)}",
                    content=content,
                    sha=existing_file.sha,
                    branch=self.branch
                )
                return True, "文件更新成功"
            except GithubException as e:
                if e.status == 404:
                    self.repo.create_file(
                        path=github_path,
                        message=f"上传文件: {os.path.basename(github_path)}",
                        content=content,
                        branch=self.branch
                    )
                    return True, "文件上传成功"
                else:
                    raise

        except GithubException as e:
            error_msg = str(e)
            if "403" in error_msg or e.status == 403:
                return False, "权限不足，请检查令牌是否有写入权限"
            elif "409" in error_msg or e.status == 409:
                return False, "文件冲突，请先拉取最新版本"
            else:
                return False, f"推送失败：{e.data.get('message', error_msg)}"
        except Exception as e:
            return False, f"推送失败：{e}"
    
    def push_folder(self, local_folder: str, github_base_path: str) -> Tuple[int, int, List[str]]:
        """
        推送整个文件夹到GitHub
        返回：(成功数量, 失败数量, 错误消息列表)
        """
        success_count = 0
        fail_count = 0
        errors = []
        
        for root, dirs, files in os.walk(local_folder):
            for filename in files:
                local_path = os.path.join(root, filename)
                relative_path = os.path.relpath(local_path, local_folder)
                github_path = os.path.join(github_base_path, relative_path).replace("\\", "/")
                
                success, msg = self.push_file(local_path, github_path)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{filename}: {msg}")
        
        return success_count, fail_count, errors
    
    def pull_file(self, github_path: str, local_path: str) -> Tuple[bool, str]:
        """
        从GitHub仓库拉取文件到本地
        参数：github_path - GitHub仓库中的路径
             local_path - 本地保存路径
        返回：(是否成功, 错误信息)
        """
        if not self.connected:
            return False, "未连接到GitHub，请先配置连接"
        
        try:
            file_content = self.repo.get_contents(github_path, ref=self.branch)
            
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as f:
                f.write(file_content.decoded_content)
            
            return True, "文件拉取成功"
            
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                return False, f"文件 '{github_path}' 在仓库中不存在"
            else:
                return False, f"拉取失败：{error_msg}"
    
    def pull_folder(self, github_path: str, local_path: str) -> Tuple[int, int, List[str]]:
        """
        从GitHub拉取整个文件夹
        返回：(成功数量, 失败数量, 错误消息列表)
        """
        success_count = 0
        fail_count = 0
        errors = []
        
        try:
            contents = self.repo.get_contents(github_path, ref=self.branch)
            
            for content in contents:
                if content.type == "file":
                    file_local_path = os.path.join(local_path, content.name)
                    success, msg = self.pull_file(content.path, file_local_path)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        errors.append(f"{content.name}: {msg}")
                elif content.type == "dir":
                    sub_success, sub_fail, sub_errors = self.pull_folder(
                        content.path, 
                        os.path.join(local_path, content.name)
                    )
                    success_count += sub_success
                    fail_count += sub_fail
                    errors.extend(sub_errors)
                    
        except Exception as e:
            errors.append(f"拉取文件夹失败: {str(e)}")
            
        return success_count, fail_count, errors
    
    def delete_file(self, github_path: str) -> Tuple[bool, str]:
        """
        删除GitHub仓库中的文件
        参数：github_path - GitHub仓库中的文件路径
        返回：(是否成功, 错误信息)
        """
        if not self.connected:
            return False, "未连接到GitHub，请先配置连接"
        
        try:
            file_content = self.repo.get_contents(github_path, ref=self.branch)
            self.repo.delete_file(
                path=github_path,
                message=f"删除文件: {os.path.basename(github_path)}",
                sha=file_content.sha,
                branch=self.branch
            )
            return True, "文件删除成功"
            
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                return False, f"文件 '{github_path}' 不存在"
            else:
                return False, f"删除失败：{error_msg}"
    
    def get_file_list(self, path: str = "") -> Tuple[bool, List[dict], str]:
        """
        获取GitHub仓库文件列表
        参数：path - 仓库中的文件夹路径（空字符串表示根目录）
        返回：(是否成功, 文件列表, 错误信息)
        """
        if not self.connected:
            return False, [], "未连接到GitHub，请先配置连接"
        
        try:
            contents = self.repo.get_contents(path, ref=self.branch)
            file_list = []
            
            for content in contents:
                file_list.append({
                    'name': content.name,
                    'path': content.path,
                    'size': content.size if content.type == "file" else 0,
                    'sha': content.sha,
                    'download_url': content.download_url,
                    'type': content.type,
                    'is_folder': content.type == "dir"
                })
            
            return True, file_list, "获取成功"
            
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                return True, [], "路径不存在"
            else:
                return False, [], f"获取失败：{error_msg}"
    
    def disconnect(self):
        """断开GitHub连接"""
        self.connected = False
        self.github_api = None
        self.repo = None


class FileStore:
    """
    本地文件管理类
    负责本地文件的增删改查和配置持久化
    """
    
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.getcwd()
            config_dir = os.path.join(base_dir, ".file_manager")
        
        self.config_dir = config_dir
        self.config_path = os.path.join(config_dir, "config.json")
        self.files_path = os.path.join(config_dir, "files.json")
        self.sync_dir = os.path.join(config_dir, "sync_files")
        
        self.files: Dict[str, FileItem] = {}
        self.github_config = {
            'token': '',
            'repo_name': '',
            'branch': 'main',
            'auto_sync': False
        }
        
        self._init_directories()
    
    def _init_directories(self):
        """初始化必要的目录"""
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.sync_dir, exist_ok=True)
    
    def _encrypt_token(self, token: str) -> str:
        """简单加密令牌（Base64编码）"""
        if not token:
            return ""
        return base64.b64encode(token.encode()).decode()
    
    def _decrypt_token(self, encrypted: str) -> str:
        """解密令牌"""
        if not encrypted:
            return ""
        try:
            return base64.b64decode(encrypted.encode()).decode()
        except (ValueError, base64.binascii.Error, UnicodeDecodeError):
            return ""
    
    def load_config(self) -> bool:
        """加载GitHub配置，优先级：config.json > 环境变量 > 默认值"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.github_config = config
                    self.github_config['token'] = self._decrypt_token(
                        config.get('encrypted_token', '')
                    )
                logger.info("从 config.json 加载配置")
                return True

            # config.json 不存在时，尝试从环境变量加载
            env_token = os.environ.get("GITHUB_TOKEN", "")
            env_repo = os.environ.get("GITHUB_REPO", "")
            env_branch = os.environ.get("GITHUB_BRANCH", "main")

            if env_token and env_repo:
                self.github_config['token'] = env_token
                self.github_config['repo_name'] = env_repo
                self.github_config['branch'] = env_branch
                logger.info("从环境变量加载配置")
                return True

            return False
        except Exception as e:
            logger.error(f"加载配置失败：{e}")
            return False
    
    def save_config(self, token: str = None, repo_name: str = None, 
                    branch: str = None, auto_sync: bool = None) -> bool:
        """保存GitHub配置"""
        try:
            # 检查仓库名称是否变更
            old_repo = self.github_config.get('repo_name', '')
            new_repo = repo_name if repo_name is not None else old_repo
            
            # 如果仓库名称变更，清空文件索引
            if old_repo and new_repo and old_repo != new_repo:
                logger.info(f"检测到仓库变更：{old_repo} -> {new_repo}，清空文件索引")
                self.files.clear()
            
            if token is not None:
                self.github_config['token'] = token
            if repo_name is not None:
                self.github_config['repo_name'] = repo_name
            if branch is not None:
                self.github_config['branch'] = branch
            if auto_sync is not None:
                self.github_config['auto_sync'] = auto_sync
            
            config_to_save = {
                'encrypted_token': self._encrypt_token(self.github_config['token']),
                'repo_name': self.github_config['repo_name'],
                'branch': self.github_config['branch'],
                'auto_sync': self.github_config['auto_sync']
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=2)
            
            # 保存清空后的文件索引
            self.save_files()
            return True
        except Exception as e:
            logger.error(f"保存配置失败：{e}")
            return False
    
    def load_files(self) -> bool:
        """加载本地文件索引"""
        try:
            if os.path.exists(self.files_path):
                with open(self.files_path, 'r', encoding='utf-8') as f:
                    files_data = json.load(f)
                    self.files = {
                        fid: FileItem.from_dict(data) 
                        for fid, data in files_data.items()
                    }
            
            if not self.files:
                self.scan_local_files()
            
            return True
        except Exception as e:
            logger.error(f"加载文件索引失败：{e}")
            self.scan_local_files()
            return False
    
    def save_files(self) -> bool:
        """保存文件索引"""
        try:
            files_data = {
                fid: f.to_dict() for fid, f in self.files.items()
            }
            with open(self.files_path, 'w', encoding='utf-8') as f:
                json.dump(files_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存文件索引失败：{e}")
            return False
    
    def scan_local_files(self, base_dir: str = None) -> int:
        """扫描本地同步文件夹，返回扫描到的文件数量"""
        if base_dir is None:
            base_dir = self.sync_dir
        
        # 收集当前实际存在的文件路径
        existing_paths = set()
        count = 0
        
        try:
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                existing_paths.add(item_path)
                if os.path.isfile(item_path):
                    self._add_file_to_index(item_path)
                    count += 1
                elif os.path.isdir(item_path):
                    self._scan_folder_recursive(item_path, existing_paths)
                    count += 1
            
            # 清理已删除文件的索引
            self._cleanup_deleted_files(existing_paths)
            self.save_files()
        except Exception as e:
            logger.error(f"扫描文件失败：{e}")
        return count
    
    def _scan_folder_recursive(self, folder_path: str, existing_paths: set) -> int:
        """递归扫描文件夹并收集所有文件路径"""
        count = 0
        try:
            self._add_folder_to_index(folder_path)
            count += 1
            
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                existing_paths.add(item_path)
                
                if os.path.isfile(item_path):
                    self._add_file_to_index(item_path)
                    count += 1
                elif os.path.isdir(item_path):
                    count += self._scan_folder_recursive(item_path, existing_paths)
        except Exception as e:
            logger.error(f"扫描文件夹失败 {folder_path}: {e}")
        return count
    
    def _cleanup_deleted_files(self, existing_paths: set):
        """清理已删除文件的索引"""
        deleted_count = 0
        files_to_remove = []
        
        for file_id, file_item in self.files.items():
            if file_item.local_path not in existing_paths:
                files_to_remove.append(file_id)
                deleted_count += 1
        
        for file_id in files_to_remove:
            del self.files[file_id]
        
        if deleted_count > 0:
            logger.info(f"清理了 {deleted_count} 个已删除文件的索引")
    
    def cleanup_nonexistent_files(self):
        """清理所有本地不存在的文件索引"""
        deleted_count = 0
        files_to_remove = []
        
        for file_id, file_item in self.files.items():
            if not os.path.exists(file_item.local_path):
                files_to_remove.append(file_id)
                deleted_count += 1
        
        for file_id in files_to_remove:
            del self.files[file_id]
        
        if deleted_count > 0:
            logger.info(f"清理了 {deleted_count} 个不存在的文件索引")
            self.save_files()
    
    def _add_file_to_index(self, local_path: str) -> FileItem:
        """将文件添加到索引（内部方法）"""
        file_id = hashlib.md5(local_path.encode()).hexdigest()[:12]
        
        if file_id in self.files:
            return self.files[file_id]
        
        filename = os.path.basename(local_path)
        _, ext = os.path.splitext(filename)
        file_size = os.path.getsize(local_path)
        update_time = datetime.fromtimestamp(
            os.path.getmtime(local_path)
        ).strftime("%Y-%m-%d %H:%M:%S")
        
        relative_path = os.path.relpath(local_path, self.sync_dir)
        github_path = relative_path.replace("\\", "/")
        
        file_item = FileItem(
            file_id=file_id,
            file_name=filename,
            file_type=ext.lower(),
            file_size=file_size,
            local_path=local_path,
            github_path=github_path,
            update_time=update_time,
            sync_status="未同步",
            is_folder=False
        )
        
        self.files[file_id] = file_item
        return file_item
    
    def _add_folder_to_index(self, local_path: str) -> FileItem:
        """将文件夹添加到索引"""
        file_id = hashlib.md5(local_path.encode()).hexdigest()[:12]
        
        if file_id in self.files:
            return self.files[file_id]
        
        folder_name = os.path.basename(local_path)
        update_time = datetime.fromtimestamp(
            os.path.getmtime(local_path)
        ).strftime("%Y-%m-%d %H:%M:%S")
        
        relative_path = os.path.relpath(local_path, self.sync_dir)
        github_path = relative_path.replace("\\", "/")
        
        folder_item = FileItem(
            file_id=file_id,
            file_name=folder_name,
            file_type="",
            file_size=0,
            local_path=local_path,
            github_path=github_path,
            update_time=update_time,
            sync_status="未同步",
            is_folder=True
        )
        
        self.files[file_id] = folder_item
        return folder_item
    
    def add_file(self, source_path: str, dest_folder: str = None) -> Tuple[bool, str, FileItem]:
        """
        添加文件到同步文件夹
        参数：source_path - 源文件路径
             dest_folder - 目标文件夹（相对于sync_dir）
        返回：(是否成功, 消息, 文件对象)
        """
        try:
            if not os.path.exists(source_path):
                return False, "源文件不存在", None
            
            filename = os.path.basename(source_path)
            
            if dest_folder:
                target_dir = os.path.join(self.sync_dir, dest_folder)
                os.makedirs(target_dir, exist_ok=True)
            else:
                target_dir = self.sync_dir
            
            dest_path = os.path.join(target_dir, filename)
            
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(dest_path):
                    filename = f"{base}_{counter}{ext}"
                    dest_path = os.path.join(target_dir, filename)
                    counter += 1
            
            shutil.copy2(source_path, dest_path)
            file_item = self._add_file_to_index(dest_path)
            self.save_files()
            
            return True, f"文件 '{filename}' 添加成功", file_item
            
        except Exception as e:
            return False, f"添加文件失败：{e}", None
    
    def add_folder(self, source_path: str, dest_folder: str = None) -> Tuple[bool, str, FileItem]:
        """
        添加整个文件夹
        参数：source_path - 源文件夹路径
             dest_folder - 目标位置（相对于sync_dir）
        返回：(是否成功, 消息, 文件夹对象)
        """
        try:
            if not os.path.exists(source_path):
                return False, "源文件夹不存在", None
            
            if not os.path.isdir(source_path):
                return False, "源路径不是文件夹", None
            
            folder_name = os.path.basename(source_path)
            
            if dest_folder:
                target_dir = os.path.join(self.sync_dir, dest_folder, folder_name)
            else:
                target_dir = os.path.join(self.sync_dir, folder_name)
            
            if os.path.exists(target_dir):
                counter = 1
                while os.path.exists(target_dir):
                    target_dir = f"{os.path.join(self.sync_dir, folder_name)}_{counter}"
                    counter += 1
            
            shutil.copytree(source_path, target_dir)
            folder_item = self._add_folder_to_index(target_dir)
            self.save_files()
            
            return True, f"文件夹 '{folder_name}' 添加成功", folder_item
            
        except Exception as e:
            return False, f"添加文件夹失败：{e}", None
    
    def create_folder(self, folder_name: str, parent_path: str = None) -> Tuple[bool, str, FileItem]:
        """
        创建新文件夹
        参数：folder_name - 文件夹名称
             parent_path - 父文件夹路径（相对于sync_dir）
        返回：(是否成功, 消息, 文件夹对象)
        """
        try:
            if not folder_name or folder_name.strip() == "":
                return False, "文件夹名称不能为空", None
            
            folder_name = folder_name.strip()
            
            if parent_path:
                folder_path = os.path.join(self.sync_dir, parent_path, folder_name)
            else:
                folder_path = os.path.join(self.sync_dir, folder_name)
            
            if os.path.exists(folder_path):
                return False, f"文件夹 '{folder_name}' 已存在", None
            
            os.makedirs(folder_path)
            folder_item = self._add_folder_to_index(folder_path)
            self.save_files()
            
            return True, f"文件夹 '{folder_name}' 创建成功", folder_item
            
        except Exception as e:
            return False, f"创建文件夹失败：{e}", None
    
    def delete_file(self, file_id: str) -> Tuple[bool, str]:
        """
        删除本地文件或文件夹
        参数：file_id - 文件ID
        返回：(是否成功, 消息)
        """
        try:
            if file_id not in self.files:
                return False, "文件不存在"
            
            file_item = self.files[file_id]
            local_path = file_item.local_path
            
            if os.path.exists(local_path):
                if file_item.is_folder:
                    shutil.rmtree(local_path)
                    for fid in list(self.files.keys()):
                        if self.files[fid].local_path.startswith(local_path + os.sep):
                            del self.files[fid]
                else:
                    os.remove(local_path)
            
            del self.files[file_id]
            self.save_files()
            
            return True, f"'{file_item.file_name}' 已删除"
            
        except Exception as e:
            return False, f"删除失败：{e}"
    
    def rename_file(self, file_id: str, new_name: str) -> Tuple[bool, str]:
        """
        重命名文件或文件夹
        参数：file_id - 文件ID
             new_name - 新文件名
        返回：(是否成功, 消息)
        """
        try:
            if file_id not in self.files:
                return False, "文件不存在"
            
            if not new_name or new_name.strip() == "":
                return False, "文件名不能为空"
            
            file_item = self.files[file_id]
            old_path = file_item.local_path
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            
            if os.path.exists(new_path):
                return False, "文件名已存在"
            
            os.rename(old_path, new_path)
            
            old_name = file_item.file_name
            file_item.file_name = new_name
            file_item.local_path = new_path
            
            if file_item.is_folder:
                for fid in self.files:
                    item = self.files[fid]
                    if item.local_path.startswith(old_path + os.sep):
                        item.local_path = item.local_path.replace(old_path, new_path)
                        item.github_path = os.path.relpath(item.local_path, self.sync_dir).replace("\\", "/")
            
            file_item.github_path = os.path.relpath(new_path, self.sync_dir).replace("\\", "/")
            file_item.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file_item.sync_status = "未同步"
            
            self.save_files()
            return True, f"已重命名为 '{new_name}'"
            
        except Exception as e:
            return False, f"重命名失败：{e}"
    
    def export_file(self, file_id: str, dest_path: str) -> Tuple[bool, str]:
        """
        导出/下载文件到指定位置
        参数：file_id - 文件ID
             dest_path - 目标保存路径
        返回：(是否成功, 消息)
        """
        try:
            if file_id not in self.files:
                return False, "文件不存在"
            
            file_item = self.files[file_id]
            
            if not os.path.exists(file_item.local_path):
                return False, "源文件不存在"
            
            if file_item.is_folder:
                if os.path.exists(dest_path):
                    return False, "目标位置已存在"
                shutil.copytree(file_item.local_path, dest_path)
                return True, f"文件夹已保存到：{dest_path}"
            else:
                shutil.copy2(file_item.local_path, dest_path)
                return True, f"文件已保存到：{dest_path}"
            
        except Exception as e:
            return False, f"导出失败：{e}"
    
    def get_items_in_folder(self, folder_path: str = None) -> List[FileItem]:
        """
        获取指定文件夹内的项目列表
        参数：folder_path - 文件夹路径（相对于sync_dir），None表示根目录
        返回：文件和文件夹列表
        """
        results = []
        
        if folder_path:
            target_dir = os.path.join(self.sync_dir, folder_path)
        else:
            target_dir = self.sync_dir
        
        if not os.path.exists(target_dir):
            return results
        
        try:
            items = os.listdir(target_dir)
            for item_name in items:
                item_path = os.path.join(target_dir, item_name)
                
                if os.path.isfile(item_path):
                    file_item = self._add_file_to_index(item_path)
                    results.append(file_item)
                elif os.path.isdir(item_path):
                    folder_item = self._add_folder_to_index(item_path)
                    results.append(folder_item)
            
            self.save_files()
        except Exception as e:
            logger.error(f"获取文件夹内容失败：{e}")
        
        return results
    
    def search(self, keyword: str, category: str = "全部", folder_path: str = None) -> List[FileItem]:
        """
        搜索文件
        参数：keyword - 搜索关键词
             category - 文件分类
             folder_path - 搜索的文件夹路径（None表示根目录）
        返回：匹配的文件列表
        """
        results = self.get_items_in_folder(folder_path)
        
        keyword = keyword.lower().strip()
        filtered = []
        
        for file_item in results:
            if category != "全部" and file_item.get_category() != category:
                continue
            
            if keyword == "":
                filtered.append(file_item)
            elif keyword in file_item.file_name.lower():
                filtered.append(file_item)
            elif keyword in file_item.file_type.lower():
                filtered.append(file_item)
        
        return filtered
    
    def get_file_by_id(self, file_id: str) -> Optional[FileItem]:
        """根据ID获取文件"""
        return self.files.get(file_id)
    
    def get_all_categories(self) -> List[str]:
        """获取所有文件分类"""
        categories = set()
        for file_item in self.files.values():
            categories.add(file_item.get_category())
        return sorted(list(categories))


class UIManager:
    """
    GUI界面管理类
    负责所有界面组件的创建和交互
    """
    
    def __init__(self, root: tk.Tk, file_store: FileStore, github_sync: GitHubSync):
        self.root = root
        self.file_store = file_store
        self.github_sync = github_sync
        
        self.selected_file_id = None
        self.current_category = "全部"
        self.search_var = tk.StringVar()
        
        self.current_folder = None
        self.folder_history = []
        
        self._setup_styles()
        self._create_ui()
        self._bind_events()
        self.refresh_list()
    
    def _setup_styles(self):
        """设置现代化界面样式"""
        style = ttk.Style()
        style.theme_use('clam')

        COLORS = {
            'primary': '#6366f1',
            'primary_hover': '#4f46e5',
            'secondary': '#64748b',
            'success': '#22c55e',
            'warning': '#f59e0b',
            'danger': '#ef4444',
            'info': '#06b6d4',
            'dark': '#1e293b',
            'gray_100': '#f1f5f9',
            'gray_200': '#e2e8f0',
            'gray_300': '#cbd5e1',
            'gray_400': '#94a3b8',
            'gray_500': '#64748b',
            'white': '#ffffff',
        }

        style.configure('Title.TLabel', font=('Microsoft YaHei', 18, 'bold'), foreground=COLORS['dark'])
        style.configure('Status.TLabel', font=('Microsoft YaHei', 9), foreground=COLORS['gray_500'])
        style.configure('Info.TLabel', font=('Microsoft YaHei', 10), foreground=COLORS['dark'])

        style.configure('Toolbar.TButton', font=('Microsoft YaHei', 10), padding=8)
        style.configure('Sidebar.TButton', font=('Microsoft YaHei', 10), padding=10)
        style.configure('Action.TButton', font=('Microsoft YaHei', 10, 'bold'), padding=8)

        style.configure('Modern.TFrame', background=COLORS['white'])

        style.configure('Treeview', font=('Microsoft YaHei', 10), rowheight=36,
                       background=COLORS['white'], fieldbackground=COLORS['white'],
                       borderwidth=0, relief='flat')
        style.configure('Treeview.Heading', font=('Microsoft YaHei', 10, 'bold'),
                       background=COLORS['gray_100'], foreground=COLORS['dark'],
                       borderwidth=0, relief='flat', padding=8)

        style.map('Treeview',
                 background=[('selected', COLORS['primary']), ('hover', COLORS['gray_100'])],
                 foreground=[('selected', COLORS['white'])])

        style.configure('Card.TFrame', background=COLORS['white'], relief='flat', borderwidth=0)

        style.configure('Sidebar.TFrame', background=COLORS['gray_100'])

        self._style = style
        self._colors = COLORS
        
    def _create_ui(self):
        """创建主界面"""
        self.root.title("GitHub文件同步管理器 v3.0")
        self.root.geometry("1300x750")
        self.root.minsize(1000, 650)
        self.root.configure(bg=self._colors['gray_100'])
        
        self._create_toolbar()
        self._create_main_area()
        self._create_status_bar()
    
    def _create_toolbar(self):
        """创建顶部工具栏"""
        COLORS = self._colors

        toolbar_frame = tk.Frame(self.root, bg=COLORS['white'], height=60)
        toolbar_frame.pack(fill=tk.X)
        toolbar_frame.pack_propagate(False)

        left_frame = tk.Frame(toolbar_frame, bg=COLORS['white'])
        left_frame.pack(side=tk.LEFT, padx=20, pady=10)

        title_label = tk.Label(left_frame, text="📁 文件管理器",
                              font=('Microsoft YaHei', 20, 'bold'),
                              fg=COLORS['primary'], bg=COLORS['white'])
        title_label.pack(side=tk.LEFT)

        version_label = tk.Label(left_frame, text="v3.0",
                                font=('Microsoft YaHei', 9),
                                fg=COLORS['gray_400'], bg=COLORS['white'])
        version_label.pack(side=tk.LEFT, padx=8, pady=10)

        search_frame = tk.Frame(toolbar_frame, bg=COLORS['white'])
        search_frame.pack(side=tk.RIGHT, padx=(5, 20), pady=12)

        search_inner = tk.Frame(search_frame, bg=COLORS['gray_100'], padx=8, pady=4)
        search_inner.pack()

        tk.Label(search_inner, text="🔍",
                font=('Microsoft YaHei', 11), bg=COLORS['gray_100'],
                fg=COLORS['gray_500']).pack(side=tk.LEFT)

        search_entry = tk.Entry(search_inner, textvariable=self.search_var,
                               width=18, font=('Microsoft YaHei', 10),
                               relief=tk.FLAT, bg=COLORS['gray_100'],
                               highlightthickness=0, insertbackground=COLORS['primary'])
        search_entry.pack(side=tk.LEFT, padx=6)
        search_entry.bind('<KeyRelease>', self._on_search)

        nav_outer = tk.Frame(toolbar_frame, bg=COLORS['white'])
        nav_outer.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=10)

        nav_top = tk.Frame(nav_outer, bg=COLORS['white'])
        nav_top.pack(fill=tk.X)

        self.back_btn = tk.Button(nav_top, text="⬆️ 返回",
                                  command=self._go_back,
                                  bg=COLORS['gray_300'], fg=COLORS['dark'],
                                  font=('Microsoft YaHei', 9, 'bold'),
                                  relief=tk.FLAT, padx=10, pady=4,
                                  cursor='hand2', state=tk.DISABLED,
                                  activebackground=COLORS['primary'],
                                  activeforeground=COLORS['white'],
                                  width=6)
        self.back_btn.pack(side=tk.LEFT, padx=(0, 8))

        path_container = tk.Frame(nav_top, bg=COLORS['white'])
        path_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.path_canvas = tk.Canvas(path_container, bg=COLORS['white'], highlightthickness=0, height=24)
        self.path_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)

        self.path_label = tk.Label(self.path_canvas, text="📍 当前位置：根目录",
                                   font=('Microsoft YaHei', 10), fg=COLORS['dark'], bg=COLORS['white'],
                                   anchor='w')
        self.path_label_id = self.path_canvas.create_window(0, 0, window=self.path_label, anchor='nw')

        path_hscroll = tk.Scrollbar(path_container, orient=tk.HORIZONTAL,
                                     command=self.path_canvas.xview)
        path_hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.path_canvas.configure(xscrollcommand=path_hscroll.set)

        def _on_path_mousewheel(event):
            self.path_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        self.path_canvas.bind_all('<Shift-MouseWheel>', _on_path_mousewheel)

        # 路径文字变化时更新滚动区域
        def _update_scroll_region(event=None):
            self.path_canvas.configure(scrollregion=self.path_canvas.bbox("all"))
            canvas_w = self.path_canvas.winfo_width()
            label_w = self.path_label.winfo_reqwidth()
            self.path_canvas.itemconfig(self.path_label_id, width=max(canvas_w, label_w))
        self.path_label.bind('<Configure>', _update_scroll_region)
        self.path_canvas.bind('<Configure>', _update_scroll_region)
    
    def _create_main_area(self):
        """创建主区域（三栏布局）"""
        COLORS = self._colors

        main_frame = tk.Frame(self.root, bg=COLORS['gray_100'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        self._create_sidebar(main_frame)

        center_frame = tk.Frame(main_frame, bg=COLORS['white'], relief='flat', bd=0)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        list_header = tk.Frame(center_frame, bg=COLORS['primary'], height=38)
        list_header.pack(fill=tk.X)
        list_header.pack_propagate(False)
        tk.Label(list_header, text="📋 文件列表", font=('Microsoft YaHei', 12, 'bold'),
                bg=COLORS['primary'], fg='white').pack(pady=8)

        action_bar = tk.Frame(center_frame, bg=COLORS['gray_100'], height=46)
        action_bar.pack(fill=tk.X, padx=8, pady=(8, 0))
        action_bar.pack_propagate(False)

        buttons = [
            ("📤 上传文件", self._on_upload_file, "#6366f1"),
            ("📁 打开文件夹", self._on_upload_folder, "#8b5cf6"),
            ("➕ 新建文件夹", self._on_new_folder, "#22c55e"),
            ("⬇️ 下载", self._on_download, "#06b6d4"),
            ("✏️ 重命名", self._on_rename, "#f59e0b"),
            ("🗑️ 删除", self._on_delete, "#ef4444"),
            ("🔄 刷新", self.refresh_list, "#64748b"),
        ]

        def on_enter(e, btn, color):
            btn.configure(bg=color, relief=tk.SUNKEN)
        def on_leave(e, btn, color):
            btn.configure(bg=color, relief=tk.FLAT)

        for text, command, color in buttons:
            btn = tk.Button(action_bar, text=text, font=('Microsoft YaHei', 9, 'bold'),
                          command=command, bg=color, fg='white',
                          relief=tk.FLAT, padx=10, pady=5,
                          cursor='hand2', bd=0, highlightthickness=0)
            btn.pack(side=tk.LEFT, padx=3, pady=5)
            btn.bind("<Enter>", lambda e, b=btn, c=color: on_enter(e, b, c))
            btn.bind("<Leave>", lambda e, b=btn, c=color: on_leave(e, b, c))

        self._create_file_list(center_frame)
        self._create_preview_panel(main_frame)
    
    def _create_sidebar(self, parent):
        """创建左侧边栏"""
        COLORS = self._colors

        sidebar_frame = tk.Frame(parent, bg=COLORS['white'], width=190, relief='flat', bd=0)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        sidebar_frame.pack_propagate(False)

        header = tk.Frame(sidebar_frame, bg=COLORS['primary'], height=42)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📂 文件分类", font=('Microsoft YaHei', 12, 'bold'),
                bg=COLORS['primary'], fg='white').pack(pady=10)

        categories = [
            ("📋 全部", "全部"),
            ("📁 文件夹", "文件夹"),
            ("📄 文档", "文档"),
            ("💻 代码", "代码"),
            ("🖼️ 图片", "图片"),
            ("📦 压缩包", "压缩包"),
            ("📎 其他", "其他")
        ]

        self.category_buttons = {}
        def on_cat_enter(e, b):
            b.configure(bg=COLORS['gray_100'])
        def on_cat_leave(e, b):
            b.configure(bg=COLORS['white'])

        for text, category in categories:
            btn = tk.Button(sidebar_frame, text=text, font=('Microsoft YaHei', 10),
                          command=lambda c=category: self._on_category_change(c),
                          bg=COLORS['white'], fg=COLORS['dark'], relief=tk.FLAT,
                          anchor='w', padx=18, pady=10, cursor='hand2', bd=0)
            btn.pack(fill=tk.X, padx=6, pady=1)
            self.category_buttons[category] = btn
            btn.bind('<Enter>', lambda e, b=btn: on_cat_enter(e, b))
            btn.bind('<Leave>', lambda e, b=btn: on_cat_leave(e, b))

        separator = tk.Frame(sidebar_frame, bg=COLORS['gray_200'], height=1)
        separator.pack(fill=tk.X, padx=10, pady=12)

        github_header = tk.Frame(sidebar_frame, bg=COLORS['success'], height=40)
        github_header.pack(fill=tk.X)
        github_header.pack_propagate(False)
        tk.Label(github_header, text="☁️ GitHub同步", font=('Microsoft YaHei', 11, 'bold'),
                bg=COLORS['success'], fg='white').pack(pady=10)
        
        github_buttons = [
            ("⚙️ 配置GitHub", self._show_github_config),
            ("⬆️ 推送到云端", self._push_to_github),
            ("⬇️ 拉取到本地", self._pull_from_github),
            ("☁️ 管理云端文件", self._manage_github_files),
        ]
        
        for text, command in github_buttons:
            btn = tk.Button(sidebar_frame, text=text, font=('微软雅黑', 10),
                          command=command, bg='#ffffff', fg='#2c3e50',
                          relief=tk.FLAT, anchor='w', padx=15, pady=8,
                          cursor='hand2')
            btn.pack(fill=tk.X, padx=5, pady=1)
            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg='#ecf0f1'))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(bg='#ffffff'))
        
        self.sync_status_label = tk.Label(sidebar_frame, text="● 未连接",
                                         font=('微软雅黑', 9), fg='#95a5a6',
                                         bg='#ffffff')
        self.sync_status_label.pack(pady=10)
    
    def _create_file_list(self, parent):
        """创建中间文件列表"""
        list_frame = tk.Frame(parent, bg='#ffffff')
        list_frame.pack(fill=tk.BOTH, expand=True)

        tree_frame = tk.Frame(list_frame, bg='#ffffff')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('icon', 'name', 'type', 'size', 'category', 'status', 'update_time')
        self.file_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                      selectmode='extended')
        
        self.file_tree.heading('icon', text='')
        self.file_tree.heading('name', text='名称')
        self.file_tree.heading('type', text='类型')
        self.file_tree.heading('size', text='大小')
        self.file_tree.heading('category', text='分类')
        self.file_tree.heading('status', text='同步状态')
        self.file_tree.heading('update_time', text='修改时间')
        
        self.file_tree.column('icon', width=40, minwidth=40, anchor='center')
        self.file_tree.column('name', width=220, minwidth=150)
        self.file_tree.column('type', width=80, minwidth=60, anchor='center')
        self.file_tree.column('size', width=100, minwidth=80, anchor='center')
        self.file_tree.column('category', width=80, minwidth=60, anchor='center')
        self.file_tree.column('status', width=100, minwidth=80, anchor='center')
        self.file_tree.column('update_time', width=150, minwidth=120)
        
        self.file_tree.tag_configure('synced', foreground='#27ae60')
        self.file_tree.tag_configure('unsynced', foreground='#f39c12')
        self.file_tree.tag_configure('failed', foreground='#e74c3c')
        self.file_tree.tag_configure('folder', foreground='#3498db')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, 
                                  command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _create_preview_panel(self, parent):
        """创建右侧预览面板"""
        COLORS = self._colors

        preview_frame = tk.Frame(parent, bg=COLORS['white'], width=300, relief='flat', bd=0)
        preview_frame.pack(side=tk.RIGHT, fill=tk.Y)
        preview_frame.pack_propagate(False)

        header = tk.Frame(preview_frame, bg="#8b5cf6", height=42)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="👁️ 文件详情", font=('Microsoft YaHei', 12, 'bold'),
                bg="#8b5cf6", fg='white').pack(pady=10)

        detail_frame = tk.Frame(preview_frame, bg=COLORS['white'], padx=15, pady=12)
        detail_frame.pack(fill=tk.X)

        self.detail_labels = {}
        detail_items = [
            ('file_name', '名称'),
            ('file_type', '类型'),
            ('file_size', '大小'),
            ('update_time', '修改时间'),
            ('sync_status', '同步状态')
        ]

        for key, label_text in detail_items:
            frame = tk.Frame(detail_frame, bg=COLORS['white'])
            frame.pack(fill=tk.X, pady=3)
            
            tk.Label(frame, text=f"{label_text}：", font=('微软雅黑', 9),
                    fg='#7f8c8d', bg='#ffffff', width=10, anchor='w').pack(side=tk.LEFT)
            
            self.detail_labels[key] = tk.Label(frame, text="-", font=('微软雅黑', 9),
                                               fg='#2c3e50', bg='#ffffff',
                                               anchor='w')
            self.detail_labels[key].pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        separator = tk.Frame(preview_frame, bg='#ecf0f1', height=2)
        separator.pack(fill=tk.X, padx=10, pady=10)
        
        preview_label = tk.Label(preview_frame, text="📄 文件内容预览",
                                font=('微软雅黑', 10, 'bold'),
                                fg='#2c3e50', bg='#ffffff')
        preview_label.pack(anchor='w', padx=10)
        
        self.preview_text = scrolledtext.ScrolledText(preview_frame, width=35, 
                                                       height=15, wrap=tk.WORD,
                                                       font=('Consolas', 9),
                                                       bg='#f8f9fa', fg='#2c3e50',
                                                       relief=tk.FLAT,
                                                       padx=10, pady=10)
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.preview_text.config(state=tk.DISABLED)
        
        action_frame = tk.Frame(preview_frame, bg='#ffffff')
        action_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(action_frame, text="📥 下载", font=('微软雅黑', 10),
                 command=self._on_download, bg='#27ae60', fg='white',
                 relief=tk.FLAT, padx=12, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=3)
        
        tk.Button(action_frame, text="📂 打开", font=('微软雅黑', 10),
                 command=self._on_open_file, bg='#3498db', fg='white',
                 relief=tk.FLAT, padx=12, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=3)
        
        tk.Button(action_frame, text="📁 进入", font=('微软雅黑', 10),
                 command=self._enter_folder, bg='#9b59b6', fg='white',
                 relief=tk.FLAT, padx=12, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=3)
    
    def _create_status_bar(self):
        """创建底部状态栏"""
        COLORS = self._colors

        status_frame = tk.Frame(self.root, bg=COLORS['dark'], height=28)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)

        self.status_label = tk.Label(status_frame, text="✓ 就绪",
                                    font=('Microsoft YaHei', 9), fg='white', bg=COLORS['dark'])
        self.status_label.pack(side=tk.LEFT, padx=12, pady=4)

        self.file_count_label = tk.Label(status_frame, text="共 0 个项目",
                                         font=('Microsoft YaHei', 9), fg='white', bg=COLORS['dark'])
        self.file_count_label.pack(side=tk.RIGHT, padx=12, pady=4)
    
    def _bind_events(self):
        """绑定事件"""
        self.file_tree.bind('<<TreeviewSelect>>', self._on_file_select)
        self.file_tree.bind('<Double-1>', self._on_file_double_click)
        self.file_tree.bind('<Button-3>', self._show_context_menu)
        self.file_tree.bind('<Control-a>', self._select_all)

        self.root.bind('<Delete>', lambda e: self._on_delete())
        self.root.bind('<Return>', lambda e: self._on_file_double_click(None) if self.get_selected_file() else None)
        self.root.bind('<BackSpace>', lambda e: self._go_back())
        self.root.bind('<F5>', lambda e: self.refresh_list())

        self._setup_drag_drop()
    
    def _update_path_display(self):
        """更新路径显示"""
        if self.current_folder:
            self.path_label.config(text=f"📍 当前位置：{self.current_folder}")
            self.back_btn.config(state=tk.NORMAL)
        else:
            self.path_label.config(text="📍 当前位置：根目录")
            self.back_btn.config(state=tk.DISABLED)
        # 更新滚动区域
        self.path_canvas.update_idletasks()
        self.path_canvas.configure(scrollregion=self.path_canvas.bbox("all"))
        canvas_w = self.path_canvas.winfo_width()
        label_w = self.path_label.winfo_reqwidth()
        self.path_canvas.itemconfig(self.path_label_id, width=max(canvas_w, label_w))
    
    def _go_back(self):
        """返回上一级目录"""
        if self.folder_history:
            self.current_folder = self.folder_history.pop()
        else:
            self.current_folder = None
        
        self._update_path_display()
        self.refresh_list()
    
    def _enter_folder(self):
        """进入选中的文件夹"""
        file_item = self.get_selected_file()
        if not file_item:
            self.show_error("请先选择一个文件夹")
            return
        
        if not file_item.is_folder:
            self.show_error("选中的不是文件夹")
            return
        
        if self.current_folder:
            self.folder_history.append(self.current_folder)
            self.current_folder = os.path.join(self.current_folder, file_item.file_name)
        else:
            self.folder_history.append(None)
            self.current_folder = file_item.file_name
        
        self._update_path_display()
        self.refresh_list()
    
    def refresh_list(self):
        """刷新文件列表"""
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        keyword = self.search_var.get()
        files = self.file_store.search(keyword, self.current_category, self.current_folder)
        
        folders_first = sorted(files, key=lambda x: (not x.is_folder, x.file_name.lower()))
        
        for file_item in folders_first:
            size_str = file_item.format_size()
            category = file_item.get_category()
            icon = file_item.get_icon()
            
            if file_item.is_folder:
                tag = 'folder'
            else:
                tag = {
                    '已同步': 'synced',
                    '未同步': 'unsynced',
                    '同步失败': 'failed'
                }.get(file_item.sync_status, '')
            
            self.file_tree.insert('', tk.END, iid=file_item.id, values=(
                icon,
                file_item.file_name,
                file_item.file_type if not file_item.is_folder else "<DIR>",
                size_str,
                category,
                file_item.sync_status,
                file_item.update_time
            ), tags=(tag,))
        
        self.file_count_label.config(text=f"共 {len(files)} 个项目")
        self.show_status(f"✓ 已刷新，共 {len(files)} 个项目")
    
    def preview_file(self, file_item: FileItem):
        """预览文件"""
        for key, label in self.detail_labels.items():
            if key == 'file_size':
                label.config(text=file_item.format_size())
            else:
                label.config(text=str(getattr(file_item, key, '-')))
        
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete('1.0', tk.END)
        
        if file_item.is_folder:
            self.preview_text.insert('1.0', f"📁 文件夹：{file_item.file_name}\n\n")
            self.preview_text.insert(tk.END, "双击或点击\"进入\"按钮可查看文件夹内容。")
        elif file_item.is_text_file() and os.path.exists(file_item.local_path):
            try:
                with open(file_item.local_path, 'r', encoding='utf-8') as f:
                    content = f.read(10000)
                    self.preview_text.insert('1.0', content)
                    if len(content) >= 10000:
                        self.preview_text.insert(tk.END, "\n\n... (文件过大，仅显示前10000字符)")
            except Exception as e:
                self.preview_text.insert('1.0', f"无法读取文件内容：{e}")
        else:
            self.preview_text.insert('1.0', "此文件类型不支持预览。\n\n您可以：\n• 点击\"下载\"导出文件\n• 点击\"打开\"用系统程序打开")
        
        self.preview_text.config(state=tk.DISABLED)
    
    def show_status(self, message: str):
        """显示状态消息"""
        self.status_label.config(text=message)
    
    def show_error(self, message: str):
        """显示错误消息"""
        messagebox.showerror("错误", message)
    
    def show_success(self, message: str):
        """显示成功消息"""
        messagebox.showinfo("成功", message)
    
    def show_sync_status(self, msg: str, connected: bool):
        """显示同步状态"""
        if connected:
            self.sync_status_label.config(text=f"● {msg}", foreground='#27ae60')
        else:
            self.sync_status_label.config(text=f"● {msg}", foreground='#95a5a6')
    
    def get_selected_file(self) -> Optional[FileItem]:
        """获取选中的文件"""
        selection = self.file_tree.selection()
        if selection:
            file_id = selection[0]
            return self.file_store.get_file_by_id(file_id)
        return None
    
    def _on_file_select(self, event):
        """文件选择事件"""
        file_item = self.get_selected_file()
        if file_item:
            self.selected_file_id = file_item.id
            self.preview_file(file_item)
    
    def _on_file_double_click(self, event):
        """文件双击事件"""
        file_item = self.get_selected_file()
        if file_item:
            if file_item.is_folder:
                self._enter_folder()
            else:
                self._on_open_file()
    
    def _setup_drag_drop(self):
        """设置拖拽功能"""
        self._drag_data = []
        self._setup_drop_in()
        self._setup_drag_out()

    def _setup_drop_in(self):
        """设置拖入功能（从外部拖文件到窗口）"""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            if isinstance(self.root, TkinterDnD.Tk):
                self.file_tree.drop_target_register(DND_FILES)
                self.file_tree.dnd_bind('<<Drop>>', self._on_drop_in)
        except ImportError:
            logger.warning("tkinterdnd2 未安装，拖入功能不可用")
            try:
                import windnd
                windnd.hook_dropfiles(self.file_tree, func=self._on_drop_in)
            except ImportError:
                logger.warning("windnd 也未安装，拖入功能不可用")
                self.show_status("提示：可使用 Ctrl+V 粘贴文件到窗口")

    def _on_drop_in(self, event):
        """处理拖入的文件"""
        if event.data:
            files = self.root.tk.splitlist(event.data)
            if files:
                file_paths = []
                for f in files:
                    if isinstance(f, bytes):
                        file_paths.append(os.fsdecode(f))
                    else:
                        file_paths.append(f)
                self._handle_dropped_files(file_paths)

    def _setup_drag_out(self):
        """设置拖出功能（从窗口拖文件到外部）"""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            if isinstance(self.root, TkinterDnD.Tk):
                self.file_tree.drag_source_register(1, DND_FILES)

                def on_drag_start(event):
                    selection = self.file_tree.selection()
                    if not selection:
                        return
                    self._drag_data = []
                    for item_id in selection:
                        file_item = self.file_store.get_file_by_id(item_id)
                        if file_item and os.path.exists(file_item.local_path):
                            self._drag_data.append(file_item.local_path)

                    if self._drag_data:
                        file_list = '\n'.join(self._drag_data)
                        event.data = file_list

                def on_drag_end(event):
                    if self._drag_data:
                        self.show_status(f"已拖出 {len(self._drag_data)} 个文件")
                    self._drag_data = []

                self.file_tree.bind('<B1-Motion>', on_drag_start)
                self.file_tree.bind('<<DragEnd>>', on_drag_end)
        except ImportError:
            logger.warning("tkinterdnd2 未安装，拖出功能不可用")

    def _handle_dropped_files(self, file_paths):
        """处理拖放的文件"""
        success_count = 0
        fail_count = 0

        for path in file_paths:
            if os.path.isfile(path):
                success, msg, _ = self.file_store.add_file(path, self.current_folder)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    logger.warning(f"添加文件失败：{msg}")
            elif os.path.isdir(path):
                success, msg, _ = self.file_store.add_folder(path, self.current_folder)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    logger.warning(f"添加文件夹失败：{msg}")

        self.refresh_list()
        if success_count > 0:
            self.show_success(f"成功添加 {success_count} 个项目")
        if fail_count > 0:
            self.show_error(f"{fail_count} 个项目添加失败")
    
    def _show_context_menu(self, event):
        """显示右键菜单"""
        item = self.file_tree.identify_row(event.y)
        if item:
            selection = self.file_tree.selection()
            if item not in selection:
                self.file_tree.selection_set(item)
            
            context_menu = tk.Menu(self.root, tearoff=0, font=('微软雅黑', 9))
            
            selected_files = self.get_selected_files()
            if len(selected_files) > 1:
                context_menu.add_command(label=f"📥 下载选中的 {len(selected_files)} 个项目", 
                                        command=self._download_selected)
                context_menu.add_command(label=f"🗑️ 删除选中的 {len(selected_files)} 个项目", 
                                        command=self._delete_selected)
            else:
                file_item = self.get_selected_file()
                if file_item:
                    if file_item.is_folder:
                        context_menu.add_command(label="📁 进入文件夹", command=self._enter_folder)
                    else:
                        context_menu.add_command(label="📥 下载", command=self._on_download)
                        context_menu.add_command(label="📂 打开", command=self._on_open_file)
                    context_menu.add_separator()
                    context_menu.add_command(label="✏️ 重命名", command=self._on_rename)
                    context_menu.add_command(label="🗑️ 删除", command=self._on_delete)
            
            context_menu.add_separator()
            context_menu.add_command(label="📤 上传文件", command=self._on_upload_file)
            context_menu.add_command(label="📁 上传文件夹", command=self._on_upload_folder)
            context_menu.add_command(label="➕ 新建文件夹", command=self._on_new_folder)
            context_menu.add_separator()
            context_menu.add_command(label="🔄 刷新", command=self.refresh_list)
            
            context_menu.post(event.x_root, event.y_root)
    
    def _select_all(self, event):
        """全选"""
        children = self.file_tree.get_children()
        for child in children:
            self.file_tree.selection_add(child)
        return "break"
    
    def get_selected_files(self) -> List[FileItem]:
        """获取所有选中的文件"""
        selection = self.file_tree.selection()
        files = []
        for file_id in selection:
            file_item = self.file_store.get_file_by_id(file_id)
            if file_item:
                files.append(file_item)
        return files
    
    def _download_selected(self):
        """下载所有选中的文件"""
        selected_files = self.get_selected_files()
        if not selected_files:
            self.show_error("请先选择要下载的项目")
            return
        
        dest_dir = filedialog.askdirectory(title="选择保存位置")
        if not dest_dir:
            return
        
        success_count = 0
        fail_count = 0
        
        for file_item in selected_files:
            if not os.path.exists(file_item.local_path):
                fail_count += 1
                continue
            
            dest_path = os.path.join(dest_dir, file_item.file_name)
            
            if file_item.is_folder:
                if os.path.exists(dest_path):
                    base_name = file_item.file_name
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(dest_dir, f"{base_name}_{counter}")
                        counter += 1
                
                try:
                    shutil.copytree(file_item.local_path, dest_path)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    logger.error(f"复制文件夹失败：{e}")
            else:
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(file_item.file_name)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
                        counter += 1
                
                try:
                    shutil.copy2(file_item.local_path, dest_path)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    logger.error(f"复制文件失败：{e}")
        
        if success_count > 0:
            self.show_success(f"成功下载 {success_count} 个项目到：{dest_dir}")
        if fail_count > 0:
            self.show_error(f"{fail_count} 个项目下载失败")
    
    def _delete_selected(self):
        """删除所有选中的文件"""
        selected_files = self.get_selected_files()
        if not selected_files:
            self.show_error("请先选择要删除的项目")
            return
        
        folder_count = sum(1 for f in selected_files if f.is_folder)
        file_count = len(selected_files) - folder_count
        
        warning = ""
        if folder_count > 0:
            warning = f"\n\n注意：包含 {folder_count} 个文件夹，所有内容都将被删除！"
        
        if not messagebox.askyesno("确认删除", 
                                   f"确定要删除选中的 {file_count} 个文件和 {folder_count} 个文件夹吗？{warning}\n\n此操作不可恢复！"):
            return
        
        success_count = 0
        fail_count = 0
        
        for file_item in selected_files:
            success, msg = self.file_store.delete_file(file_item.id)
            if success:
                success_count += 1
            else:
                fail_count += 1
        
        self.refresh_list()
        if success_count > 0:
            self.show_success(f"成功删除 {success_count} 个项目")
        if fail_count > 0:
            self.show_error(f"{fail_count} 个项目删除失败")
    
    def _on_search(self, event):
        """搜索事件"""
        self.refresh_list()
    
    def _on_category_change(self, category: str):
        """分类切换事件"""
        self.current_category = category
        self.refresh_list()
    
    def _on_upload_file(self):
        """上传文件"""
        file_paths = filedialog.askopenfilenames(
            title="选择要上传的文件",
            filetypes=[
                ("所有文件", "*.*"),
                ("文档文件", "*.txt *.md *.doc *.docx *.pdf"),
                ("代码文件", "*.py *.js *.html *.css *.java"),
                ("图片文件", "*.jpg *.png *.gif *.bmp"),
            ]
        )
        
        if file_paths:
            success_count = 0
            for path in file_paths:
                success, msg, _ = self.file_store.add_file(path, self.current_folder)
                if success:
                    success_count += 1
                else:
                    self.show_error(msg)
            
            self.refresh_list()
            if success_count > 0:
                self.show_success(f"成功上传 {success_count} 个文件")
    
    def _on_upload_folder(self):
        """上传文件夹"""
        folder_path = filedialog.askdirectory(title="选择要上传的文件夹")
        
        if folder_path:
            success, msg, _ = self.file_store.add_folder(folder_path, self.current_folder)
            if success:
                self.refresh_list()
                self.show_success(msg)
            else:
                self.show_error(msg)
    
    def _on_new_folder(self):
        """新建文件夹"""
        dialog = tk.Toplevel(self.root)
        dialog.title("新建文件夹")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg='#ffffff')
        
        tk.Label(dialog, text="请输入文件夹名称：",
                font=('微软雅黑', 10), bg='#ffffff', fg='#2c3e50').pack(pady=15)
        
        frame = tk.Frame(dialog, bg='#ffffff')
        frame.pack(pady=5, padx=20, fill=tk.X)
        
        name_var = tk.StringVar()
        entry = tk.Entry(frame, textvariable=name_var, width=40,
                        font=('微软雅黑', 10), relief=tk.FLAT, bg='#ecf0f1')
        entry.pack(pady=5, ipady=5)
        entry.focus()
        entry.bind('<Return>', lambda e: do_create())

        def do_create():
            folder_name = name_var.get().strip()
            if folder_name:
                success, msg, _ = self.file_store.create_folder(folder_name, self.current_folder)
                if success:
                    self.refresh_list()
                    self.show_success(msg)
                    dialog.destroy()
                else:
                    self.show_error(msg)
        
        btn_frame = tk.Frame(dialog, bg='#ffffff')
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="创建", font=('微软雅黑', 10),
                 command=do_create, bg='#1abc9c', fg='white',
                 relief=tk.FLAT, padx=20, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", font=('微软雅黑', 10),
                 command=dialog.destroy, bg='#95a5a6', fg='white',
                 relief=tk.FLAT, padx=20, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
    
    def _on_download(self):
        """下载/导出文件或文件夹"""
        selected_files = self.get_selected_files()
        
        if not selected_files:
            self.show_error("请先选择要下载的项目")
            return
        
        if len(selected_files) > 1:
            self._download_selected()
            return
        
        file_item = selected_files[0]
        
        if not os.path.exists(file_item.local_path):
            self.show_error("源文件不存在")
            return
        
        if file_item.is_folder:
            dest_path = filedialog.askdirectory(title="选择保存位置")
            if dest_path:
                dest_path = os.path.join(dest_path, file_item.file_name)
                success, msg = self.file_store.export_file(file_item.id, dest_path)
                if success:
                    self.show_success(msg)
                else:
                    self.show_error(msg)
        else:
            dest_path = filedialog.asksaveasfilename(
                title="保存文件",
                initialfile=file_item.file_name,
                defaultextension=file_item.file_type,
                filetypes=[
                    ("所有文件", "*.*"),
                    (f"{file_item.file_type}文件", f"*{file_item.file_type}"),
                ]
            )
            
            if dest_path:
                success, msg = self.file_store.export_file(file_item.id, dest_path)
                if success:
                    self.show_success(msg)
                else:
                    self.show_error(msg)
    
    def _on_open_file(self):
        """打开文件"""
        file_item = self.get_selected_file()
        if not file_item:
            self.show_error("请先选择要打开的文件")
            return
        
        if file_item.is_folder:
            self._enter_folder()
            return
        
        if not os.path.exists(file_item.local_path):
            self.show_error("文件不存在")
            return
        
        try:
            os.startfile(file_item.local_path)
        except Exception as e:
            self.show_error(f"无法打开文件：{e}")
    
    def _on_rename(self):
        """重命名文件或文件夹"""
        file_item = self.get_selected_file()
        if not file_item:
            self.show_error("请先选择要重命名的项目")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("重命名")
        dialog.geometry("450x180")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg='#ffffff')
        
        item_type = "文件夹" if file_item.is_folder else "文件"
        tk.Label(dialog, text=f"当前{item_type}名：{file_item.file_name}",
                font=('微软雅黑', 10), bg='#ffffff', fg='#2c3e50').pack(pady=15)
        
        frame = tk.Frame(dialog, bg='#ffffff')
        frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(frame, text=f"新{item_type}名：", font=('微软雅黑', 10),
                bg='#ffffff', fg='#7f8c8d').pack(side=tk.LEFT)
        new_name_var = tk.StringVar(value=file_item.file_name)
        entry = tk.Entry(frame, textvariable=new_name_var, width=35,
                        font=('微软雅黑', 10), relief=tk.FLAT, bg='#ecf0f1')
        entry.pack(side=tk.LEFT, padx=5, pady=5)
        entry.select_range(0, tk.END)
        entry.focus()
        entry.bind('<Return>', lambda e: do_rename())

        def do_rename():
            new_name = new_name_var.get().strip()
            if new_name:
                success, msg = self.file_store.rename_file(file_item.id, new_name)
                if success:
                    self.refresh_list()
                    self.show_success(msg)
                    dialog.destroy()
                else:
                    self.show_error(msg)
        
        btn_frame = tk.Frame(dialog, bg='#ffffff')
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="确定", font=('微软雅黑', 10),
                 command=do_rename, bg='#3498db', fg='white',
                 relief=tk.FLAT, padx=20, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", font=('微软雅黑', 10),
                 command=dialog.destroy, bg='#95a5a6', fg='white',
                 relief=tk.FLAT, padx=20, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
    
    def _on_delete(self):
        """删除文件或文件夹"""
        file_item = self.get_selected_file()
        if not file_item:
            self.show_error("请先选择要删除的项目")
            return
        
        item_type = "文件夹" if file_item.is_folder else "文件"
        warning = ""
        if file_item.is_folder:
            warning = "\n\n注意：文件夹内所有内容都将被删除！"
        
        if messagebox.askyesno("确认删除", 
                              f"确定要删除{item_type} '{file_item.file_name}' 吗？{warning}\n\n此操作不可恢复！"):
            success, msg = self.file_store.delete_file(file_item.id)
            if success:
                self.refresh_list()
                self.show_success(msg)
            else:
                self.show_error(msg)
    
    def _show_github_config(self):
        """显示GitHub配置对话框"""
        config_dialog = tk.Toplevel(self.root)
        config_dialog.title("GitHub配置")
        config_dialog.geometry("550x380")
        config_dialog.transient(self.root)
        config_dialog.grab_set()
        config_dialog.configure(bg='#ffffff')
        
        tk.Label(config_dialog, text="GitHub仓库配置", 
                font=('微软雅黑', 14, 'bold'), bg='#ffffff', fg='#2c3e50').pack(pady=15)
        
        fields_frame = tk.Frame(config_dialog, bg='#ffffff')
        fields_frame.pack(fill=tk.X, padx=30)
        
        tk.Label(fields_frame, text="访问令牌：", font=('微软雅黑', 10),
                bg='#ffffff', fg='#7f8c8d').grid(row=0, column=0, sticky=tk.W, pady=8)
        token_var = tk.StringVar(value=self.file_store.github_config.get('token', ''))
        token_entry = tk.Entry(fields_frame, textvariable=token_var, width=45,
                              font=('微软雅黑', 10), show="*", relief=tk.FLAT, bg='#ecf0f1')
        token_entry.grid(row=0, column=1, pady=8, padx=10, ipady=5)
        
        tk.Label(fields_frame, text="仓库名称：", font=('微软雅黑', 10),
                bg='#ffffff', fg='#7f8c8d').grid(row=1, column=0, sticky=tk.W, pady=8)
        repo_var = tk.StringVar(value=self.file_store.github_config.get('repo_name', ''))
        tk.Entry(fields_frame, textvariable=repo_var, width=45,
                font=('微软雅黑', 10), relief=tk.FLAT, bg='#ecf0f1').grid(row=1, column=1, pady=8, padx=10, ipady=5)
        tk.Label(fields_frame, text="格式：用户名/仓库名", 
                font=('微软雅黑', 9), fg='#95a5a6', bg='#ffffff').grid(row=1, column=2, sticky=tk.W)
        
        tk.Label(fields_frame, text="分支名称：", font=('微软雅黑', 10),
                bg='#ffffff', fg='#7f8c8d').grid(row=2, column=0, sticky=tk.W, pady=8)
        branch_var = tk.StringVar(value=self.file_store.github_config.get('branch', 'main'))
        tk.Entry(fields_frame, textvariable=branch_var, width=45,
                font=('微软雅黑', 10), relief=tk.FLAT, bg='#ecf0f1').grid(row=2, column=1, pady=8, padx=10, ipady=5)
        
        help_frame = tk.LabelFrame(config_dialog, text="帮助说明", 
                                   font=('微软雅黑', 10), bg='#ffffff', fg='#2c3e50',
                                   padx=10, pady=10)
        help_frame.pack(fill=tk.X, padx=30, pady=15)
        
        help_text = """1. 访问令牌：在 GitHub Settings > Developer settings > Personal access tokens 创建
2. 令牌权限需要勾选：repo（完整仓库访问权限）
3. 仓库名称格式：您的用户名/仓库名（如：zhangsan/my-files）
4. 分支通常为 main 或 master"""
        
        tk.Label(help_frame, text=help_text, font=('微软雅黑', 9),
                bg='#ffffff', fg='#7f8c8d', justify=tk.LEFT).pack()
        
        def test_connection():
            token = token_var.get().strip()
            repo = repo_var.get().strip()
            branch = branch_var.get().strip()
            
            if not token or not repo:
                self.show_error("请填写令牌和仓库名称")
                return
            
            self.show_status("⏳ 正在连接GitHub...")
            success, msg = self.github_sync.connect(token, repo, branch)
            
            if success:
                self.file_store.save_config(token, repo, branch)
                self.show_sync_status("已连接", True)
                self.show_success("GitHub连接成功！")
            else:
                self.show_sync_status("连接失败", False)
                self.show_error(msg)
        
        btn_frame = tk.Frame(config_dialog, bg='#ffffff')
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="测试连接", font=('微软雅黑', 10),
                 command=test_connection, bg='#3498db', fg='white',
                 relief=tk.FLAT, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="保存配置", font=('微软雅黑', 10),
                 command=lambda: (
                     self.file_store.save_config(
                         token_var.get().strip(),
                         repo_var.get().strip(),
                         branch_var.get().strip()
                     ),
                     self.show_success("配置已保存"),
                     config_dialog.destroy()
                 ), bg='#27ae60', fg='white',
                 relief=tk.FLAT, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", font=('微软雅黑', 10),
                 command=config_dialog.destroy, bg='#95a5a6', fg='white',
                 relief=tk.FLAT, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
    
    def _push_to_github(self):
        """推送文件到GitHub"""
        if not self.github_sync.connected:
            self.show_error("请先配置并连接GitHub")
            return
        
        # 推送前先清理不存在的文件索引
        self.file_store.cleanup_nonexistent_files()
        
        files = list(self.file_store.files.values())
        if not files:
            self.show_error("没有文件需要推送")
            return
        
        def push_task():
            self.root.after(0, lambda: self.show_status(" 正在获取GitHub文件列表..."))
            success, github_files, msg = self.github_sync.get_file_list()
            
            if not success:
                self.root.after(0, lambda: self.show_error(f"获取云端文件列表失败：{msg}"))
                return
            
            github_file_names = {f['name'] for f in github_files}
            
            # 调试信息：打印所有待推送的文件
            logger.debug(f"推送调试 - 本地文件总数：{len(files)}")
            logger.debug(f"推送调试 - GitHub根目录文件：{github_file_names}")
            for i, f in enumerate(files):
                logger.debug(f"  [{i}] {f.file_name} (类型: {'文件夹' if f.is_folder else '文件'}, 路径: {f.local_path})")

            success_count = 0
            update_count = 0
            fail_count = 0
            fail_details = []

            for file_item in files:
                is_update = file_item.file_name in github_file_names

                if file_item.is_folder:
                    action = "更新" if is_update else "推送"
                    self.root.after(0, lambda f=file_item, a=action: self.show_status(f"⏳ 正在{a}文件夹：{f.file_name}"))
                    logger.info(f"推送文件夹: {file_item.file_name}, 本地路径: {file_item.local_path}, GitHub路径: {file_item.github_path}")
                    s, f, errors = self.github_sync.push_folder(
                        file_item.local_path,
                        file_item.github_path
                    )
                    success_count += s
                    fail_count += f
                    if errors:
                        fail_details.extend(errors)
                        logger.warning(f"文件夹推送失败详情: {errors}")
                    if is_update:
                        update_count += s
                else:
                    action = "更新" if is_update else "推送"
                    self.root.after(0, lambda f=file_item, a=action: self.show_status(f"⏳ 正在{a}：{f.file_name}"))
                    logger.info(f"推送文件: {file_item.file_name}, 本地路径: {file_item.local_path}, GitHub路径: {file_item.github_path}")
                    success, msg = self.github_sync.push_file(
                        file_item.local_path,
                        file_item.github_path
                    )

                    if success:
                        file_item.sync_status = "已同步"
                        success_count += 1
                        if is_update:
                            update_count += 1
                    else:
                        file_item.sync_status = "同步失败"
                        fail_count += 1
                        fail_details.append(f"{file_item.file_name}: {msg}")
                        logger.error(f"推送失败: {file_item.file_name}, 错误: {msg}")
            
            logger.info(f"推送结果 - 成功: {success_count}, 更新: {update_count}, 失败: {fail_count}")
            if fail_details:
                logger.warning(f"推送失败详情: {fail_details}")
            
            self.file_store.save_files()
            self.root.after(0, lambda: self.refresh_list())
            self.root.after(0, lambda: self.show_status(
                f"✓ 推送完成：成功 {success_count}（其中更新 {update_count}），失败 {fail_count}"
            ))

            if fail_count == 0:
                self.root.after(0, lambda: self.show_success(
                    f"成功推送 {success_count} 个文件（更新 {update_count} 个）"
                ))
            else:
                self.root.after(0, lambda: self.show_error(
                    f"推送完成：成功 {success_count}（更新 {update_count}），失败 {fail_count}"
                ))
        
        threading.Thread(target=push_task, daemon=True).start()
    
    def _pull_from_github(self):
        """从GitHub拉取文件"""
        if not self.github_sync.connected:
            self.show_error("请先配置并连接GitHub")
            return
        
        def pull_task():
            self.root.after(0, lambda: self.show_status("⏳ 正在获取GitHub文件列表..."))
            success, file_list, msg = self.github_sync.get_file_list()
            
            if not success:
                self.root.after(0, lambda: self.show_error(msg))
                return
            
            pull_count = 0
            skip_count = 0
            
            for github_file in file_list:
                local_path = os.path.join(
                    self.file_store.sync_dir,
                    github_file['name']
                )
                
                if os.path.exists(local_path):
                    skip_count += 1
                    self.root.after(0, lambda g=github_file: self.show_status(f"⏭️ 跳过已存在：{g['name']}"))
                    continue
                
                if github_file.get('is_folder', False):
                    self.root.after(0, lambda g=github_file: self.show_status(f"⏳ 正在拉取文件夹：{g['name']}"))
                    s, f, _ = self.github_sync.pull_folder(github_file['path'], local_path)
                    pull_count += s
                else:
                    self.root.after(0, lambda g=github_file: self.show_status(f"⏳ 正在拉取：{g['name']}"))
                    success, msg = self.github_sync.pull_file(
                        github_file['path'],
                        local_path
                    )
                    
                    if success:
                        pull_count += 1
            
            self.file_store.scan_local_files()
            self.root.after(0, lambda: self.refresh_list())
            self.root.after(0, lambda: self.show_status(
                f"✓ 拉取完成：成功 {pull_count}，跳过 {skip_count}"
            ))
            self.root.after(0, lambda: self.show_success(
                f"成功拉取 {pull_count} 个文件，跳过 {skip_count} 个已存在文件"
            ))
        
        threading.Thread(target=pull_task, daemon=True).start()

    def _manage_github_files(self):
        """管理GitHub云端文件（浏览和删除）"""
        if not self.github_sync.connected:
            self.show_error("请先配置并连接GitHub")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("云端文件管理")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg='#ffffff')

        # 标题
        tk.Label(dialog, text="☁️ 云端文件管理",
                font=('Microsoft YaHei', 14, 'bold'), bg='#ffffff', fg='#2c3e50').pack(pady=10)

        # 路径和返回按钮
        nav_frame = tk.Frame(dialog, bg='#ffffff')
        nav_frame.pack(fill=tk.X, padx=15, pady=(0, 5))

        cloud_path_var = tk.StringVar(value="/")
        tk.Label(nav_frame, textvariable=cloud_path_var,
                font=('Microsoft YaHei', 10), bg='#ffffff', fg='#2c3e50').pack(side=tk.LEFT)

        cloud_folder_history = []

        # 文件列表
        list_frame = tk.Frame(dialog, bg='#ffffff')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        columns = ('name', 'type', 'size')
        cloud_tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                  selectmode='extended')
        cloud_tree.heading('name', text='名称')
        cloud_tree.heading('type', text='类型')
        cloud_tree.heading('size', text='大小')
        cloud_tree.column('name', width=350)
        cloud_tree.column('type', width=100, anchor='center')
        cloud_tree.column('size', width=120, anchor='center')

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=cloud_tree.yview)
        cloud_tree.configure(yscrollcommand=scrollbar.set)
        cloud_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def get_current_path():
            path = cloud_path_var.get()
            return "" if path == "/" else path.lstrip("/")

        def refresh_cloud_list():
            for item in cloud_tree.get_children():
                cloud_tree.delete(item)

            current_path = get_current_path()
            success, file_list, msg = self.github_sync.get_file_list(current_path)
            if not success:
                self.show_error(f"获取文件列表失败：{msg}")
                return

            folders = sorted([f for f in file_list if f['is_folder']], key=lambda x: x['name'].lower())
            files = sorted([f for f in file_list if not f['is_folder']], key=lambda x: x['name'].lower())

            for f in folders:
                cloud_tree.insert('', tk.END, iid=f['path'], values=(
                    f"📁 {f['name']}", "文件夹", "-"
                ))

            for f in files:
                size = f['size']
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024*1024):.1f} MB"

                _, ext = os.path.splitext(f['name'])
                cloud_tree.insert('', tk.END, iid=f['path'], values=(
                    f"📄 {f['name']}", ext or "文件", size_str
                ))

        def go_back():
            if cloud_folder_history:
                prev_path = cloud_folder_history.pop()
                cloud_path_var.set(prev_path if prev_path else "/")
                refresh_cloud_list()

        def enter_cloud_folder(event=None):
            selection = cloud_tree.selection()
            if not selection:
                return
            item_path = selection[0]
            current_path = get_current_path()
            success, file_list, _ = self.github_sync.get_file_list(current_path)
            if success:
                for f in file_list:
                    if f['path'] == item_path and f['is_folder']:
                        cloud_folder_history.append(get_current_path())
                        cloud_path_var.set("/" + item_path if not item_path.startswith("/") else item_path)
                        refresh_cloud_list()
                        return

        def delete_cloud_files():
            selections = cloud_tree.selection()
            if not selections:
                self.show_error("请先选择要删除的文件")
                return

            files_to_delete = []
            folders_to_delete = []
            for item_path in selections:
                values = cloud_tree.item(item_path, 'values')
                if values and values[1] == "文件夹":
                    folders_to_delete.append(item_path)
                else:
                    files_to_delete.append(item_path)

            parts = []
            if files_to_delete:
                parts.append(f"{len(files_to_delete)} 个文件")
            if folders_to_delete:
                parts.append(f"{len(folders_to_delete)} 个文件夹")
            warning = ""
            if folders_to_delete:
                warning = "\n\n注意：删除文件夹会删除其中所有内容！"

            if not messagebox.askyesno("确认删除",
                                       f"确定要从 GitHub 删除 {' 和 '.join(parts)} 吗？{warning}\n\n此操作不可恢复！"):
                return

            success_count = 0
            fail_count = 0
            errors = []

            for item_path in files_to_delete + folders_to_delete:
                success, msg = self.github_sync.delete_file(item_path)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{os.path.basename(item_path)}: {msg}")

            refresh_cloud_list()

            if fail_count == 0:
                self.show_success(f"成功删除 {success_count} 个项目")
            else:
                detail = "\n".join(errors[:5])
                if len(errors) > 5:
                    detail += f"\n...等共 {len(errors)} 个错误"
                self.show_error(f"删除完成：成功 {success_count}，失败 {fail_count}\n{detail}")

        def download_cloud_files():
            selections = cloud_tree.selection()
            if not selections:
                self.show_error("请先选择要下载的文件或文件夹")
                return

            dest_dir = filedialog.askdirectory(title="选择保存位置")
            if not dest_dir:
                return

            files_to_download = []
            folders_to_download = []
            for item_path in selections:
                values = cloud_tree.item(item_path, 'values')
                if values and values[1] == "文件夹":
                    folders_to_download.append(item_path)
                else:
                    files_to_download.append(item_path)

            success_count = 0
            fail_count = 0
            errors = []

            for github_path in files_to_download:
                file_name = os.path.basename(github_path)
                local_path = os.path.join(dest_dir, file_name)
                success, msg = self.github_sync.pull_file(github_path, local_path)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{file_name}: {msg}")

            for github_path in folders_to_download:
                folder_name = os.path.basename(github_path)
                local_path = os.path.join(dest_dir, folder_name)
                s, f, errs = self.github_sync.pull_folder(github_path, local_path)
                success_count += s
                fail_count += f
                errors.extend(errs)

            if fail_count == 0:
                self.show_success(f"成功下载 {success_count} 个项目到：{dest_dir}")
            else:
                detail = "\n".join(errors[:5])
                if len(errors) > 5:
                    detail += f"\n...等共 {len(errors)} 个错误"
                self.show_error(f"下载完成：成功 {success_count}，失败 {fail_count}\n{detail}")

        cloud_tree.bind('<Double-1>', enter_cloud_folder)

        # 右键菜单
        def show_cloud_context_menu(event):
            item = cloud_tree.identify_row(event.y)
            if item:
                if item not in cloud_tree.selection():
                    cloud_tree.selection_set(item)

                menu = tk.Menu(dialog, tearoff=0, font=('微软雅黑', 9))
                menu.add_command(label="📥 下载选中", command=download_cloud_files)
                menu.add_command(label="🗑 删除选中", command=delete_cloud_files)
                menu.add_separator()
                menu.add_command(label="🔄 刷新", command=refresh_cloud_list)
                menu.post(event.x_root, event.y_root)

        cloud_tree.bind('<Button-3>', show_cloud_context_menu)

        # 返回按钮
        tk.Button(nav_frame, text="⬆ 返回", font=('Microsoft YaHei', 9),
                 command=go_back, bg='#95a5a6', fg='white',
                 relief=tk.FLAT, padx=8, pady=2, cursor='hand2').pack(side=tk.RIGHT)

        # 底部按钮（先打包，防止被 Treeview 挤出）
        btn_frame = tk.Frame(dialog, bg='#ffffff')
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=10)

        tk.Button(btn_frame, text="📥 下载选中", font=('Microsoft YaHei', 10),
                 command=download_cloud_files, bg='#27ae60', fg='white',
                 relief=tk.FLAT, padx=12, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="🗑 删除选中", font=('Microsoft YaHei', 10),
                 command=delete_cloud_files, bg='#e74c3c', fg='white',
                 relief=tk.FLAT, padx=12, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="🔄 刷新", font=('Microsoft YaHei', 10),
                 command=refresh_cloud_list, bg='#3498db', fg='white',
                 relief=tk.FLAT, padx=12, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="关闭", font=('Microsoft YaHei', 10),
                 command=dialog.destroy, bg='#95a5a6', fg='white',
                 relief=tk.FLAT, padx=12, pady=5, cursor='hand2').pack(side=tk.RIGHT, padx=3)

        # 初始加载
        refresh_cloud_list()


class FileManagerApp:
    """
    文件管理器主应用类
    负责初始化和启动整个应用
    """

    def __init__(self):
        try:
            from tkinterdnd2 import TkinterDnD
            self.root = TkinterDnD.Tk()
        except ImportError:
            logger.warning("tkinterdnd2 未安装，拖放功能将不可用")
            self.root = tk.Tk()
        self.file_store = FileStore()
        self.github_sync = GitHubSync()
        self.ui_manager = None

        self._init_app()
    
    def _init_app(self):
        """初始化应用"""
        self.file_store.load_config()
        self.file_store.load_files()
        
        if self.file_store.github_config.get('token'):
            self.github_sync.connect(
                self.file_store.github_config['token'],
                self.file_store.github_config['repo_name'],
                self.file_store.github_config.get('branch', 'main')
            )
        
        self.ui_manager = UIManager(
            self.root,
            self.file_store,
            self.github_sync
        )
        
        if self.github_sync.connected:
            self.ui_manager.show_sync_status("已连接", True)
    
    def run(self):
        """运行应用"""
        self.root.mainloop()


def main():
    """主函数"""
    if not GITHUB_AVAILABLE:
        logger.warning("PyGitHub库未安装，请运行：pip install PyGithub")
        logger.warning("程序将在无GitHub同步功能模式下运行")

    app = FileManagerApp()
    app.run()


if __name__ == "__main__":
    main()
