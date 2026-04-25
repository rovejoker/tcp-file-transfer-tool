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
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def get_logger(name: str) -> Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        Logger: 日志记录器实例
    """
    return logging.getLogger(name)
