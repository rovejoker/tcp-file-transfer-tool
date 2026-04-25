# -*- coding: utf-8 -*-
"""
Socket 管理器

提供通用的 TCP Socket 服务器和客户端初始化功能。
"""

import socket
from typing import Optional, Tuple

from ..utils.logger import get_logger


class SocketManager:
    """
    Socket 管理器类
    
    提供服务器和客户端 Socket 的标准化初始化方法。
    """
    
    def __init__(self, host: str = '', port: int = 0, max_connections: int = 100):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.socket_obj: Optional[socket.socket] = None
        self.logger = get_logger(__name__)
    
    def create_socket(self) -> socket.socket:
        """创建并配置 Socket 对象"""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        return s
    
    def bind_and_listen(self) -> bool:
        """绑定端口并开始监听"""
        try:
            self.socket_obj = self.create_socket()
            self.socket_obj.bind((self.host, self.port))
            self.socket_obj.listen(self.max_connections)
            self.logger.info('Socket 已绑定到 {0}:{1}'.format(self.host, self.port))
            return True
        except Exception as e:
            self.logger.error('绑定失败: {0}'.format(e))
            return False
    
    def accept_connection(self) -> Optional[Tuple[socket.socket, Tuple[str, int]]]:
        """接受客户端连接"""
        try:
            if self.socket_obj:
                client_socket, client_address = self.socket_obj.accept()
                self.logger.info('接受连接: {0}'.format(client_address))
                return client_socket, client_address
            return None
        except Exception as e:
            self.logger.error('接受连接失败: {0}'.format(e))
            return None
    
    def connect(self) -> bool:
        """连接到服务器"""
        try:
            self.socket_obj = self.create_socket()
            self.socket_obj.connect((self.host, self.port))
            self.logger.info('已连接到 {0}:{1}'.format(self.host, self.port))
            return True
        except Exception as e:
            self.logger.error('连接失败: {0}'.format(e))
            return False
    
    def close(self):
        """关闭 Socket"""
        try:
            if self.socket_obj:
                self.socket_obj.close()
                self.logger.info('Socket 已关闭')
        except Exception as e:
            self.logger.error('关闭 Socket 失败: {0}'.format(e))
