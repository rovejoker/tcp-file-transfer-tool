# -*- coding: utf-8 -*-
"""
协议处理模块

提供 XProtocol 协议的实现，包括帧的创建、解析和校验。
"""

from .xprotocol import (
    XProtocol,
    VERSION,
    TYPE_JSON,
    TYPE_BINARY,
    TYPE_CHUNK,
    ACTION_UPLOAD,
    ACTION_DOWNLOAD,
    ACTION_LISTFILES,
    ACTION_HEARTBEAT,
    HEADER_FORMAT,
    HEADER_SIZE
)

__all__ = [
    'XProtocol',
    'VERSION',
    'TYPE_JSON',
    'TYPE_BINARY',
    'TYPE_CHUNK',
    'ACTION_UPLOAD',
    'ACTION_DOWNLOAD',
    'ACTION_LISTFILES',
    'ACTION_HEARTBEAT',
    'HEADER_FORMAT',
    'HEADER_SIZE'
]
