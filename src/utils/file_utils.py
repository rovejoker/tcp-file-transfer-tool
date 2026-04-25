# -*- coding: utf-8 -*-
"""
文件操作工具

提供文件保存、加载和目录管理功能。
"""

import os
import time
import hashlib
from typing import List, Dict, Union, Generator

DEFAULT_CHUNK_SIZE = 1024 * 1024 * 4

SMALL_FILE_THRESHOLD = 50 * 1024 * 1024


def ensure_directory(dir_path: str) -> bool:
    """
    确保目录存在，如果不存在则创建
    
    Args:
        dir_path: 目录路径
    
    Returns:
        bool: 是否成功创建或目录已存在
    """
    try:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            return True
        return True
    except Exception as e:
        return False


def save_file(file_path: str, data: bytes) -> bool:
    """
    保存数据到文件
    
    Args:
        file_path: 文件路径
        data: 数据
    
    Returns:
        bool: 是否成功
    """
    try:
        ensure_directory(os.path.dirname(file_path))
        with open(file_path, 'wb') as f:
            f.write(data)
        return True
    except Exception as e:
        return False


def load_file(file_path: str) -> bytes:
    """
    加载文件内容
    
    Args:
        file_path: 文件路径
    
    Returns:
        bytes: 文件内容
    """
    try:
        with open(file_path, 'rb') as f:
            return f.read()
    except Exception as e:
        return b''


def get_file_size(file_path: str) -> int:
    """
    获取文件大小
    
    Args:
        file_path: 文件路径
    
    Returns:
        int: 文件大小（字节）
    """
    try:
        return os.path.getsize(file_path)
    except Exception as e:
        return 0


def read_file_chunks(file_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE, start_offset: int = 0) -> Generator[bytes, None, None]:
    """
    分块读取文件（支持断点续传）
    
    Args:
        file_path: 文件路径
        chunk_size: 块大小
        start_offset: 起始偏移量（用于断点续传）
    
    Returns:
        Generator: 块数据生成器
    """
    try:
        with open(file_path, 'rb') as f:
            # 如果有起始偏移量，跳过前面的字节
            if start_offset > 0:
                f.seek(start_offset)
            
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except Exception as e:
        yield from []


def list_files(dir_path: str) -> List[Dict[str, Union[str, int]]]:
    """
    列出目录中的文件
    
    Args:
        dir_path: 目录路径
    
    Returns:
        List[Dict]: 文件信息列表
    """
    files = []
    try:
        for filename in os.listdir(dir_path):
            file_path = os.path.join(dir_path, filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "mtime": time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(file_path)))
                })
    except Exception as e:
        pass
    return files


def is_filename_safe(filename: str) -> bool:
    """
    检查文件名是否安全（不包含路径字符且长度不超过限制）
    
    Args:
        filename: 文件名
    
    Returns:
        bool: 是否安全
    """
    # 检查文件名长度（限制为120字符）
    if len(filename) > 120:
        return False
    
    # 检查不安全字符
    unsafe_chars = ['/', '\\', '..', ':', '*', '?', '"', '<', '>', '|']
    for char in unsafe_chars:
        if char in filename:
            return False
    return True


def is_filename_length_valid(filename: str, max_length: int = 120) -> bool:
    """
    检查文件名长度是否在允许范围内
    
    Args:
        filename: 文件名
        max_length: 最大允许长度，默认为120
    
    Returns:
        bool: 长度是否有效
    """
    return len(filename) <= max_length


def get_max_filename_length() -> int:
    """
    获取最大允许的文件名长度
    
    Returns:
        int: 最大文件名长度
    """
    return 120


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，强制提取纯文件名，防止路径穿越攻击
    
    Args:
        filename: 原始文件名
    
    Returns:
        str: 清理后的纯文件名
    """
    # 使用 os.path.basename 强制提取纯文件名
    # 这会自动去除路径分隔符和 .. 等路径穿越字符
    return os.path.basename(filename)


def is_path_within_directory(file_path: str, allowed_dir: str) -> bool:
    """
    检查文件路径是否在允许的目录内（二次校验，防止路径穿越）
    
    Args:
        file_path: 要检查的文件路径
        allowed_dir: 允许的目录路径
    
    Returns:
        bool: 文件路径是否在允许的目录内
    """
    # 获取规范化的绝对路径
    file_path_abs = os.path.abspath(file_path)
    allowed_dir_abs = os.path.abspath(allowed_dir)
    
    # 确保路径末尾有分隔符
    if not allowed_dir_abs.endswith(os.sep):
        allowed_dir_abs += os.sep
    
    # 检查文件路径是否以允许的目录开头
    return file_path_abs.startswith(allowed_dir_abs)


def calculate_file_hash(file_path: str) -> str:
    """
    计算文件的 SHA256 哈希值
    
    Args:
        file_path: 文件路径
    
    Returns:
        str: 哈希值
    """
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        return ""


def calculate_data_hash(data: bytes) -> str:
    """
    计算数据的 SHA256 哈希值
    
    Args:
        data: 数据
    
    Returns:
        str: 哈希值
    """
    try:
        return hashlib.sha256(data).hexdigest()
    except Exception as e:
        return ""
