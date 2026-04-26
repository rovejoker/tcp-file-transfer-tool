# -*- coding: utf-8 -*-
"""
日志配置模块

提供统一的日志配置和获取方法。
"""

import logging
from logging import Logger
from typing import Optional


def configure_logging(level: int = logging.INFO):
    """
    配置日志
    
    Args:
        level: 日志级别，默认为 INFO
    """
    root_logger = logging.getLogger()
    
    if root_logger.handlers:
        root_logger.setLevel(level)
        return
    
    # 文件处理器：记录所有 INFO 及以上级别日志
    file_handler = logging.FileHandler('app.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # 控制台处理器：只显示 WARNING 及以上级别日志
    console_handler = logging.StreamHandler()
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
