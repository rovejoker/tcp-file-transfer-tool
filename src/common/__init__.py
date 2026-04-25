# -*- coding: utf-8 -*-
"""
通用模块

提供统一的配置管理、异常处理等基础功能。
"""

from .config_manager import ConfigManager
from .config_ui import ConfigUI
from .exceptions import (
    FileTransferError,
    ProtocolError,
    ConnectionError,
    ValidationError,
    SecurityError,
    HashMismatchError
)

__all__ = [
    'ConfigManager',
    'ConfigUI',
    'FileTransferError',
    'ProtocolError',
    'ConnectionError',
    'ValidationError',
    'SecurityError',
    'HashMismatchError'
]
