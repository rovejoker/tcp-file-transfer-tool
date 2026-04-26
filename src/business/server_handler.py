# -*- coding: utf-8 -*-
"""
服务器业务处理器模块

处理客户端请求，实现文件上传、下载和列表功能。
根据文件大小自动选择传输方式：
- 小文件（<=50MB）：一次性传输
- 大文件（>50MB）：分块传输

支持单IP连接数限制，防止DOS攻击。
"""

import os
import time
from typing import Optional, Tuple

from ..protocol import TYPE_JSON, TYPE_BINARY, TYPE_CHUNK
from ..protocol import ACTION_UPLOAD, ACTION_DOWNLOAD, ACTION_LISTFILES, ACTION_HEARTBEAT
from ..utils.logger import get_logger
from ..utils.file_utils import (
    save_file, load_file, list_files, ensure_directory, read_file_chunks,
    DEFAULT_CHUNK_SIZE, SMALL_FILE_THRESHOLD, is_filename_safe,
    calculate_file_hash, calculate_data_hash, sanitize_filename, is_path_within_directory
)


class ServerHandler:
    """
    服务器业务处理器
    
    处理客户端的文件上传、下载和列表请求。
    支持单IP连接数限制和文件完整性校验。
    """
    
    def __init__(self, resource_dir: str = "resource", max_file_size_mb: int = 1024, 
                 max_connections_per_ip: int = 5):
        """
        初始化服务器处理器
        
        Args:
            resource_dir: 资源文件存储目录，默认为 "resource"
            max_file_size_mb: 最大文件大小限制（MB），默认为 1024（1GB）
            max_connections_per_ip: 单IP最大连接数，默认为 5
        """
        self.resource_dir = resource_dir
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.chunk_size = DEFAULT_CHUNK_SIZE
        self.max_connections_per_ip = max_connections_per_ip
        self.logger = get_logger(__name__)
        self.upload_tracking = {}
        self.connection_counts = {}
    
    def check_ip_connection_limit(self, client_address: Tuple[str, int]) -> bool:
        """
        检查客户端IP是否超过连接数限制
        
        Args:
            client_address: 客户端地址元组 (IP, port)
        
        Returns:
            bool: 是否允许连接
        """
        if client_address is None:
            return True
        
        client_ip = client_address[0]
        return self.connection_counts.get(client_ip, 0) < self.max_connections_per_ip
    
    def increment_connection_count(self, client_address: Tuple[str, int]):
        """
        增加客户端IP的连接计数
        
        Args:
            client_address: 客户端地址元组 (IP, port)
        """
        if client_address is not None:
            client_ip = client_address[0]
            self.connection_counts[client_ip] = self.connection_counts.get(client_ip, 0) + 1
            self.logger.debug('IP {0} 连接数增加: {1}'.format(client_ip, self.connection_counts[client_ip]))
    
    def decrement_connection_count(self, client_address: Tuple[str, int]):
        """
        减少客户端IP的连接计数
        
        Args:
            client_address: 客户端地址元组 (IP, port)
        """
        if client_address is not None:
            client_ip = client_address[0]
            if client_ip in self.connection_counts:
                self.connection_counts[client_ip] = max(0, self.connection_counts[client_ip] - 1)
                self.logger.debug('IP {0} 连接数减少: {1}'.format(client_ip, self.connection_counts[client_ip]))
    
    def handle_request(self, frame_type: int, decoded_data: dict, 
                      client_address: Optional[Tuple[str, int]] = None):
        """
        处理客户端请求（主入口）
        
        Args:
            frame_type: 帧类型（TYPE_JSON, TYPE_BINARY, TYPE_CHUNK）
            decoded_data: 解码后的数据
            client_address: 客户端地址元组
        
        Returns:
            dict/bytes/None: 响应数据
        """
        try:
            if frame_type == TYPE_JSON:
                return self._handle_json_command(decoded_data, client_address)
            elif frame_type == TYPE_BINARY and isinstance(decoded_data, bytes):
                return self._handle_binary_data(decoded_data, client_address)
            elif frame_type == TYPE_CHUNK and isinstance(decoded_data, bytes):
                return self._handle_chunk_data(decoded_data, client_address)
            else:
                return {"status": "error", "message": "未知帧类型: {0}".format(frame_type)}
        except Exception as e:
            self.logger.error('处理请求时发生错误: {0}'.format(e))
            return {"status": "error", "message": str(e)}
    
    def _handle_json_command(self, json_data: dict, client_address):
        """
        处理 JSON 指令
        
        Args:
            json_data: JSON数据字典
            client_address: 客户端地址元组
        
        Returns:
            dict: 响应字典
        """
        action = json_data.get("action")
        
        if action == ACTION_UPLOAD:
            return self._handle_upload_request(json_data, client_address)
        elif action == ACTION_DOWNLOAD:
            return self._handle_download_request(json_data)
        elif action == ACTION_LISTFILES:
            return self._handle_list_files_request()
        elif action == ACTION_HEARTBEAT:
            return self._handle_heartbeat_request()
        elif json_data.get("status") in ("success", "error"):
            return json_data
        else:
            return {"status": "error", "message": "未知指令: {0}".format(action)}
    
    def _handle_heartbeat_request(self):
        """
        处理心跳请求
        
        Returns:
            dict: 心跳响应
        """
        return {"status": "success", "action": ACTION_HEARTBEAT, "timestamp": int(time.time())}
    
    def _handle_upload_request(self, json_data: dict, client_address):
        """
        处理文件上传请求
        
        Args:
            json_data: 上传请求数据
            client_address: 客户端地址元组
        
        Returns:
            dict: 上传响应
        """
        filename = json_data.get("filename")
        file_size = json_data.get("size", 0)
        is_large = json_data.get("is_large", False)
        file_hash = json_data.get("hash", "")
        resume_from = json_data.get("resume_from", 0)
        
        if not filename:
            return {"status": "error", "message": "缺少文件名"}
        
        # 安全检查：强制提取纯文件名，防止路径穿越攻击
        filename = sanitize_filename(filename)
        
        if not is_filename_safe(filename):
            return {"status": "error", "message": "不安全的文件名，不允许包含路径字符"}
        
        if file_size > self.max_file_size_bytes:
            return {
                "status": "error", 
                "message": "文件大小超过限制（最大 {0} MB）".format(self.max_file_size_bytes // (1024 * 1024)),
                "max_size_mb": self.max_file_size_bytes // (1024 * 1024)
            }
        
        # 检查是否支持断点续传
        current_size = 0
        file_path = os.path.join(self.resource_dir, filename)
        
        # 二次校验：确保文件路径在允许的目录内
        if not is_path_within_directory(file_path, self.resource_dir):
            return {"status": "error", "message": "文件路径超出允许范围"}
        
        if os.path.exists(file_path):
            current_size = os.path.getsize(file_path)
        
        # 记录上传上下文
        if client_address:
            self.upload_tracking[client_address] = {
                'filename': filename,
                'file_size': file_size,
                'is_large': is_large,
                'chunk_size': json_data.get("chunk_size", self.chunk_size),
                'hash': file_hash,
                'resume_from': max(resume_from, current_size),
                'current_size': current_size
            }
        
        return {
            "status": "ready",
            "message": "准备接收文件: {0}".format(filename),
            "action": ACTION_UPLOAD,
            "filename": filename,
            "is_large": is_large,
            "chunk_size": self.chunk_size if is_large else 0,
            "resume_from": current_size
        }
    
    def _handle_download_request(self, json_data: dict):
        """
        处理文件下载请求（支持断点续传）
        
        Args:
            json_data: 下载请求数据
        
        Returns:
            dict: 下载响应
        """
        self.logger.info('收到下载请求: {0}'.format(json_data))
        ensure_directory(self.resource_dir)
        
        filename = json_data.get("filename")
        resume_from = json_data.get("resume_from", 0)
        
        if not filename:
            return {"status": "error", "message": "缺少文件名"}
        
        # 安全检查：强制提取纯文件名
        filename = sanitize_filename(filename)
        
        if not is_filename_safe(filename):
            return {"status": "error", "message": "不安全的文件名"}
        
        file_path = os.path.join(self.resource_dir, filename)
        
        # 二次校验：确保文件路径在允许的目录内
        if not is_path_within_directory(file_path, self.resource_dir):
            return {"status": "error", "message": "文件路径超出允许范围"}
        
        if not os.path.exists(file_path):
            return {"status": "error", "message": "文件不存在"}
        
        if not os.path.isfile(file_path):
            return {"status": "error", "message": "路径不是文件"}
        
        file_size = os.path.getsize(file_path)
        is_large = file_size > SMALL_FILE_THRESHOLD
        
        # 检查断点续传位置是否有效
        if resume_from < 0 or resume_from >= file_size:
            resume_from = 0
        
        file_hash = calculate_file_hash(file_path)
        
        return {
            "status": "ready",
            "message": "开始发送文件: {0}".format(filename),
            "action": ACTION_DOWNLOAD,
            "filename": filename,
            "size": file_size,
            "is_large": is_large,
            "chunk_size": self.chunk_size if is_large else 0,
            "hash": file_hash,
            "resume_from": resume_from
        }
    
    def _handle_list_files_request(self):
        """
        处理文件列表请求
        
        Returns:
            dict: 文件列表响应
        """
        ensure_directory(self.resource_dir)
        files = list_files(self.resource_dir)
        
        return {
            "status": "success",
            "action": ACTION_LISTFILES,
            "files": files
        }
    
    def _handle_binary_data(self, binary_data: bytes, client_address):
        """
        处理二进制数据（小文件一次性上传）
        
        Args:
            binary_data: 文件二进制数据
            client_address: 客户端地址元组
        
        Returns:
            dict: 上传结果响应
        """
        upload_info = self.upload_tracking.get(client_address)
        if not upload_info:
            return {"status": "error", "message": "未找到上传上下文"}
        
        filename = upload_info['filename']
        expected_hash = upload_info.get('hash', '')
        
        try:
            file_path = os.path.join(self.resource_dir, filename)
            save_file(file_path, binary_data)
            
            # 校验文件完整性
            if expected_hash:
                actual_hash = calculate_data_hash(binary_data)
                if actual_hash != expected_hash:
                    os.remove(file_path)
                    return {"status": "error", "message": "文件哈希校验失败"}
            
            self.logger.info('文件上传成功: {0}'.format(filename))
            return {"status": "success", "message": "文件上传成功"}
        except Exception as e:
            self.logger.error('文件上传失败: {0}'.format(e))
            return {"status": "error", "message": str(e)}
        finally:
            # 清理上传上下文
            if client_address in self.upload_tracking:
                del self.upload_tracking[client_address]
    
    def _handle_chunk_data(self, chunk_data: bytes, client_address):
        """
        处理分块数据（大文件分块上传，流式写入）
        
        Args:
            chunk_data: 文件块数据
            client_address: 客户端地址元组
        
        Returns:
            dict/None: 上传结果响应（完成时返回，中间分块返回None）
        """
        upload_info = self.upload_tracking.get(client_address)
        if not upload_info:
            return {"status": "error", "message": "未找到上传上下文"}
        
        filename = upload_info['filename']
        file_size = upload_info['file_size']
        expected_hash = upload_info.get('hash', '')
        current_size = upload_info.get('current_size', 0)
        
        file_path = os.path.join(self.resource_dir, filename)
        
        try:
            # 流式写入磁盘（边接收边写入，提升速度并减少内存占用）
            mode = 'ab' if current_size > 0 else 'wb'
            with open(file_path, mode) as f:
                f.write(chunk_data)
            
            current_size += len(chunk_data)
            upload_info['current_size'] = current_size
            
            if current_size >= file_size:
                # 文件接收完成，进行哈希校验
                if expected_hash:
                    actual_hash = calculate_file_hash(file_path)
                    if actual_hash != expected_hash:
                        os.remove(file_path)
                        # 清理上传上下文
                        if client_address in self.upload_tracking:
                            del self.upload_tracking[client_address]
                        return {"status": "error", "message": "文件哈希校验失败"}
                
                # 清理上传上下文（上传成功）
                if client_address in self.upload_tracking:
                    del self.upload_tracking[client_address]
                
                self.logger.info('文件上传成功: {0}'.format(filename))
                return {"status": "success", "message": "文件上传成功"}
            else:
                # 继续接收，不需要确认（提升上传速度）
                return None
        except Exception as e:
            # 清理上传上下文（上传失败）
            if client_address in self.upload_tracking:
                del self.upload_tracking[client_address]
            self.logger.error('文件上传失败: {0}'.format(e))
            return {"status": "error", "message": str(e)}
    
    def download_file_single(self, client_socket, frame_handler, filename: str):
        """
        一次性发送文件（适用于小文件）
        
        Args:
            client_socket: 客户端socket连接
            frame_handler: 帧处理器
            filename: 要发送的文件名
        """
        try:
            self.logger.info('开始发送文件: {0}'.format(filename))
            file_path = os.path.join(self.resource_dir, filename)
            file_data = load_file(file_path)
            self.logger.info('文件加载完成，大小: {0} 字节'.format(len(file_data)))
            frame_handler.send_binary_frame(client_socket, file_data)
            self.logger.info('文件发送成功: {0}'.format(filename))
            
            # 等待客户端确认，设置较长超时时间（30秒）
            frame_type, response = frame_handler.receive_frame(client_socket, timeout=30)
            if response and response.get("status") == "success":
                self.logger.info('客户端确认文件下载成功: {0}'.format(filename))
            else:
                self.logger.error('客户端报告下载失败: {0}'.format(response.get("message", "未知错误") if response else "无响应"))
                
        except Exception as e:
            self.logger.error('文件发送失败: {0}'.format(e))
    
    def download_file_chunked(self, client_socket, frame_handler, filename: str, 
                              resume_from: int = 0):
        """
        分块发送文件（适用于大文件，支持断点续传）
        
        Args:
            client_socket: 客户端socket连接
            frame_handler: 帧处理器
            filename: 要发送的文件名
            resume_from: 断点续传起始位置（字节）
        """
        try:
            file_path = os.path.join(self.resource_dir, filename)
            for chunk in read_file_chunks(file_path, self.chunk_size, resume_from):
                frame_handler.send_chunk_frame(client_socket, chunk)
            
            self.logger.info('文件分块发送完成: {0}'.format(filename))
            
            # 等待客户端确认，设置较长超时时间（30秒）
            frame_type, response = frame_handler.receive_frame(client_socket, timeout=30)
            if response and response.get("status") == "success":
                self.logger.info('客户端确认文件下载成功: {0}'.format(filename))
            else:
                self.logger.error('客户端报告下载失败: {0}'.format(response.get("message", "未知错误")))
                
        except Exception as e:
            self.logger.error('文件分块发送失败: {0}'.format(e))