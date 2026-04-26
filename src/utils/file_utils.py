# -*- coding: utf-8 -*-
"""
文件操作工具模块

提供文件保存、加载、目录管理和安全校验等功能。
所有文件操作都经过安全验证，防止路径穿越攻击。
"""

import os
import time
import hashlib
from typing import List, Dict, Union, Generator

# 默认分块大小：4MB（平衡内存占用和传输效率）
DEFAULT_CHUNK_SIZE = 1024 * 1024 * 4

# 小文件阈值：50MB（小于等于此值使用一次性传输）
SMALL_FILE_THRESHOLD = 50 * 1024 * 1024

# 最大文件名长度限制
MAX_FILENAME_LENGTH = 120


def ensure_directory(dir_path: str) -> bool:
    """
    确保目录存在，如果不存在则递归创建
    
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
    except Exception:
        return False


def save_file(file_path: str, data: bytes) -> bool:
    """
    保存数据到文件（自动创建父目录）
    
    Args:
        file_path: 文件路径
        data: 要保存的二进制数据
        
    Returns:
        bool: 是否保存成功
    """
    try:
        ensure_directory(os.path.dirname(file_path))
        with open(file_path, 'wb') as f:
            f.write(data)
        return True
    except Exception:
        return False


def load_file(file_path: str) -> bytes:
    """
    加载文件内容为二进制数据
    
    Args:
        file_path: 文件路径
        
    Returns:
        bytes: 文件内容（失败返回空字节串）
    """
    try:
        with open(file_path, 'rb') as f:
            return f.read()
    except Exception:
        return b''


def get_file_size(file_path: str) -> int:
    """
    获取文件大小（字节）
    
    Args:
        file_path: 文件路径
        
    Returns:
        int: 文件大小（失败返回0）
    """
    try:
        return os.path.getsize(file_path)
    except Exception:
        return 0


def read_file_chunks(file_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE, 
                     start_offset: int = 0) -> Generator[bytes, None, None]:
    """
    分块读取文件（支持断点续传）
    
    Args:
        file_path: 文件路径
        chunk_size: 每块大小，默认4MB
        start_offset: 起始偏移量（用于断点续传）
        
    Yields:
        bytes: 文件块数据
    """
    try:
        with open(file_path, 'rb') as f:
            if start_offset > 0:
                f.seek(start_offset)
            
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except Exception:
        return


def list_files(dir_path: str) -> List[Dict[str, Union[str, int]]]:
    """
    列出目录中的所有文件（不包含子目录）
    
    Args:
        dir_path: 目录路径
        
    Returns:
        List[Dict]: 文件信息列表，包含 name, size, mtime
    """
    files = []
    try:
        for filename in os.listdir(dir_path):
            file_path = os.path.join(dir_path, filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "mtime": time.strftime('%Y-%m-%d %H:%M', 
                                         time.localtime(os.path.getmtime(file_path)))
                })
    except Exception:
        pass
    return files


def is_filename_safe(filename: str) -> bool:
    """
    检查文件名是否安全（防止路径穿越攻击）
    
    安全规则：
    - 不为空或仅包含空白字符
    - 长度不超过 MAX_FILENAME_LENGTH
    - 不包含路径分隔符（/、\）
    - 不包含路径穿越字符（..）
    - 不包含特殊字符（: * ? " < > |）
    - 不是 Windows 保留文件名（如 CON、PRN、AUX、NUL、COM1-9、LPT1-9）
    
    Args:
        filename: 要检查的文件名
        
    Returns:
        bool: 是否安全
    """
    # 检查空文件名或仅包含空白字符
    if not filename or filename.strip() == '':
        return False
    
    # 检查文件名长度
    if len(filename) > MAX_FILENAME_LENGTH:
        return False
    
    # 检查不安全字符
    unsafe_chars = ['/', '\\', '..', ':', '*', '?', '"', '<', '>', '|']
    for char in unsafe_chars:
        if char in filename:
            return False
    
    # 检查 Windows 保留文件名
    windows_reserved = ['CON', 'PRN', 'AUX', 'NUL'] + \
                       ['COM{}'.format(i) for i in range(1, 10)] + \
                       ['LPT{}'.format(i) for i in range(1, 10)]
    if filename.upper() in windows_reserved:
        return False
    
    return True


def is_filename_length_valid(filename: str, max_length: int = MAX_FILENAME_LENGTH) -> bool:
    """
    检查文件名长度是否在允许范围内
    
    Args:
        filename: 要检查的文件名
        max_length: 最大允许长度，默认120
        
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
    return MAX_FILENAME_LENGTH


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，强制提取纯文件名
    
    使用 os.path.basename 自动去除路径分隔符和路径穿越字符，
    防止恶意路径注入。
    
    Args:
        filename: 原始文件名
        
    Returns:
        str: 清理后的纯文件名
    """
    return os.path.basename(filename)


def is_path_within_directory(file_path: str, allowed_dir: str) -> bool:
    """
    二次校验：确保文件路径在允许的目录内
    
    防止路径穿越攻击的最终防线，比较规范化后的绝对路径。
    
    Args:
        file_path: 要检查的文件路径
        allowed_dir: 允许的目录路径
        
    Returns:
        bool: 文件路径是否在允许的目录内
    """
    file_path_abs = os.path.abspath(file_path)
    allowed_dir_abs = os.path.abspath(allowed_dir)
    
    if not allowed_dir_abs.endswith(os.sep):
        allowed_dir_abs += os.sep
    
    return file_path_abs.startswith(allowed_dir_abs)


def calculate_file_hash(file_path: str) -> str:
    """
    计算文件的 SHA256 哈希值（用于完整性校验）
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 哈希值字符串（失败返回空串）
    """
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception:
        return ""


def calculate_data_hash(data: bytes) -> str:
    """
    计算二进制数据的 SHA256 哈希值（用于完整性校验）
    
    Args:
        data: 二进制数据
        
    Returns:
        str: 哈希值字符串（失败返回空串）
    """
    try:
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return ""