# -*- coding: utf-8 -*-
"""
日志配置模块

提供统一的日志配置和获取方法。
"""

import logging
import sys
import io
from logging import Logger
from typing import Optional


def _fix_windows_console_encoding():
    """修复Windows控制台中文显示问题"""
    if sys.platform == 'win32':
        try:
            # 设置控制台输出编码为UTF-8
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
            
            # 使用ctypes设置控制台代码页为UTF-8
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # 设置输出代码页为UTF-8 (65001)
            kernel32.SetConsoleOutputCP(65001)
            # 设置输入代码页为UTF-8
            kernel32.SetConsoleCP(65001)
        except Exception as e:
            # 如果设置失败，不影响程序运行
            pass


def configure_logging(level: int = logging.INFO):
    """
    配置日志
    
    Args:
        level: 日志级别，默认为 INFO
    """
    # 修复Windows控制台编码
    _fix_windows_console_encoding()
    
    root_logger = logging.getLogger()
    
    # 如果已经配置过，直接设置级别并返回
    if root_logger.handlers:
        root_logger.setLevel(level)
        return
    
    # 清除所有已存在的handler（防止重复配置）
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 文件处理器：记录所有 INFO 及以上级别日志
    # 使用UTF-8-sig编码，确保Windows记事本能正确识别
    file_handler = logging.FileHandler('app.log', encoding='utf-8-sig')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # 控制台处理器：只显示 WARNING 及以上级别日志
    # 创建自定义StreamHandler，确保正确处理中文
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        Logger: 日志记录器实例
    """
    return logging.getLogger(name)
