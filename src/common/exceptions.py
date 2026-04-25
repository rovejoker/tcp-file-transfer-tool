# -*- coding: utf-8 -*-
"""
统一异常处理模块

定义项目中使用的自定义异常类和异常处理工具。
"""

from typing import Optional, Dict, Any


class FileTransferError(Exception):
    """文件传输基础异常"""
    
    def __init__(self, message: str, code: int = 0, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ProtocolError(FileTransferError):
    """协议相关异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=100, details=details)


class ConnectionError(FileTransferError):
    """连接相关异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=200, details=details)


class ValidationError(FileTransferError):
    """数据验证异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=300, details=details)


class SecurityError(FileTransferError):
    """安全相关异常"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=400, details=details)


class HashMismatchError(FileTransferError):
    """哈希不匹配异常"""
    
    def __init__(self, message: str = "文件哈希校验失败"):
        super().__init__(message, code=500)
