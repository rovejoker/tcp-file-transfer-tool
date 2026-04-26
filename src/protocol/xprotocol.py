# -*- coding: utf-8 -*-
"""
XProtocol 协议实现

定义帧结构、编解码规则和校验机制。
"""

import struct
import json
import zlib

VERSION = 1

TYPE_JSON = 1
TYPE_BINARY = 2
TYPE_CHUNK = 3

ACTION_UPLOAD = "upload"
ACTION_DOWNLOAD = "download"
ACTION_LISTFILES = "listfiles"
ACTION_HEARTBEAT = "heartbeat"

HEADER_FORMAT = "!IIII"
HEADER_SIZE = 16


class XProtocol:
    """
    XProtocol 协议实现类
    
    提供帧的打包、解包、编码和解码功能。
    """
    
    @staticmethod
    def build_frame(frame_type: int, data: bytes) -> bytes:
        """
        构建完整的帧（包含 CRC 校验）
        
        Args:
            frame_type: 帧类型
            data: 数据
        
        Returns:
            bytes: 完整的帧
        """
        data_length = len(data)
        # 计算 CRC32 校验码
        crc = zlib.crc32(data) & 0xffffffff
        header = struct.pack(HEADER_FORMAT, VERSION, frame_type, data_length, crc)
        return header + data
    
    @staticmethod
    def parse_header(header_data: bytes) -> tuple:
        """
        解析帧头部（包含 CRC 校验码）
        
        Args:
            header_data: 头部数据
        
        Returns:
            tuple: (版本, 帧类型, 数据长度, CRC校验码)
        """
        version, frame_type, data_length, crc = struct.unpack(HEADER_FORMAT, header_data)
        return version, frame_type, data_length, crc
    
    @staticmethod
    def verify_crc(data: bytes, expected_crc: int) -> bool:
        """
        验证数据的 CRC32 校验码
        
        Args:
            data: 数据
            expected_crc: 期望的 CRC32 校验码
        
        Returns:
            bool: 校验是否通过
        """
        actual_crc = zlib.crc32(data) & 0xffffffff
        return actual_crc == expected_crc
    
    @staticmethod
    def encode_json(data: dict) -> bytes:
        """
        编码 JSON 数据
        
        Args:
            data: JSON 数据（字典）
        
        Returns:
            bytes: 编码后的字节数据
        """
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    @staticmethod
    def decode_json(data: bytes) -> dict:
        """
        解码 JSON 数据
        
        Args:
            data: JSON 字节数据
        
        Returns:
            dict: 解码后的字典
        """
        return json.loads(data.decode('utf-8'))
    
    @staticmethod
    def compress_data(data: bytes) -> bytes:
        """
        压缩数据
        
        Args:
            data: 原始数据
        
        Returns:
            bytes: 压缩后的数据
        """
        return zlib.compress(data)
    
    @staticmethod
    def decompress_data(data: bytes) -> bytes:
        """
        解压数据
        
        Args:
            data: 压缩数据
        
        Returns:
            bytes: 解压后的数据
        """
        return zlib.decompress(data)
