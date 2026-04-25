# -*- coding: utf-8 -*-
"""
帧处理器

负责帧的接收、发送和解析。
"""

from typing import Tuple, Any, Optional, Callable

from ..protocol import XProtocol, HEADER_SIZE, TYPE_JSON, TYPE_BINARY, TYPE_CHUNK
from ..utils.logger import get_logger


class FrameHandler:
    """
    帧处理器
    
    提供帧的接收、发送和解析功能。
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def receive_frame(self, sock, progress_callback: Optional[Callable[[int, int], None]] = None, timeout: float = None) -> Tuple[int, Any]:
        """
        从 Socket 接收完整的帧
        
        Args:
            sock: Socket 对象
            progress_callback: 进度回调函数 (current_size, total_size)
            timeout: 超时时间（秒），None 表示无限等待
        
        Returns:
            tuple: (帧类型, 解码后的数据)
        """
        # 设置超时
        original_timeout = None
        if timeout is not None:
            original_timeout = sock.gettimeout()
            sock.settimeout(timeout)
        
        try:
            header_data = sock.recv(HEADER_SIZE)
            if not header_data or len(header_data) != HEADER_SIZE:
                raise ValueError("无法接收完整头部数据")
            
            version, frame_type, data_length = XProtocol.parse_header(header_data)
            
            received_data = b''
            while len(received_data) < data_length:
                chunk = sock.recv(min(data_length - len(received_data), 65536))
                if not chunk:
                    raise ValueError("无法接收完整数据")
                received_data += chunk
                
                if progress_callback and data_length > 0:
                    progress_callback(len(received_data), data_length)
            
            if frame_type == TYPE_JSON:
                decoded_data = XProtocol.decode_json(received_data)
            elif frame_type == TYPE_BINARY:
                decoded_data = received_data
            elif frame_type == TYPE_CHUNK:
                decoded_data = received_data
            else:
                decoded_data = received_data
            
            return frame_type, decoded_data
        finally:
            # 恢复原始超时设置
            if timeout is not None and original_timeout is not None:
                sock.settimeout(original_timeout)
    
    def send_frame(self, sock, frame_type: int, data: bytes):
        """
        发送帧到 Socket
        
        Args:
            sock: Socket 对象
            frame_type: 帧类型
            data: 数据
        """
        frame = XProtocol.build_frame(frame_type, data)
        sock.sendall(frame)
    
    def send_json_frame(self, sock, data: dict):
        """
        发送 JSON 帧
        
        Args:
            sock: Socket 对象
            data: JSON 数据（字典）
        """
        json_bytes = XProtocol.encode_json(data)
        self.send_frame(sock, TYPE_JSON, json_bytes)
    
    def send_binary_frame(self, sock, data: bytes):
        """
        发送二进制帧
        
        Args:
            sock: Socket 对象
            data: 二进制数据
        """
        self.send_frame(sock, TYPE_BINARY, data)
    
    def send_chunk_frame(self, sock, data: bytes):
        """
        发送分块帧
        
        Args:
            sock: Socket 对象
            data: 分块数据
        """
        self.send_frame(sock, TYPE_CHUNK, data)
