# -*- coding: utf-8 -*-
"""
TCP 文件传输工具

提供完整的文件传输功能，包括协议处理、网络通信和业务逻辑。
"""

__version__ = "1.0.0"

from .protocol import XProtocol, VERSION, TYPE_JSON, TYPE_BINARY, ACTION_UPLOAD, ACTION_DOWNLOAD, ACTION_LISTFILES, ACTION_HEARTBEAT, HEADER_SIZE
from .network import SocketManager, FrameHandler
from .business import ServerHandler, ClientHandler

__all__ = [
    'XProtocol',
    'VERSION',
    'TYPE_JSON',
    'TYPE_BINARY',
    'ACTION_UPLOAD',
    'ACTION_DOWNLOAD',
    'ACTION_LISTFILES',
    'ACTION_HEARTBEAT',
    'HEADER_SIZE',
    'SocketManager',
    'FrameHandler',
    'ServerHandler',
    'ClientHandler'
]
