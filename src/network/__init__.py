# -*- coding: utf-8 -*-
"""
网络通信模块

提供 Socket 管理和帧处理功能。
"""

from .socket_manager import SocketManager
from .frame_handler import FrameHandler

__all__ = ['SocketManager', 'FrameHandler']
