# -*- coding: utf-8 -*-
"""
客户端业务处理器

处理与服务器的通信，实现文件上传、下载和列表功能。
"""

import os
import time
import select
from typing import Optional, Tuple

from ..protocol import TYPE_JSON, TYPE_BINARY, TYPE_CHUNK, ACTION_UPLOAD, ACTION_DOWNLOAD, ACTION_LISTFILES, XProtocol
from ..utils import get_logger
from ..utils.file_utils import save_file, load_file, read_file_chunks, get_file_size, DEFAULT_CHUNK_SIZE, SMALL_FILE_THRESHOLD, calculate_file_hash, calculate_data_hash


class ClientHandler:
    """
    客户端业务处理器
    
    处理与服务器的通信，实现文件上传、下载和列表功能。
    根据文件大小自动选择传输方式：
    - 小文件（<=100MB）：一次性传输
    - 大文件（>100MB）：分块传输
    """
    
    def __init__(self, download_dir: str = "downloads"):
        self.logger = get_logger(__name__)
        self.chunk_size = DEFAULT_CHUNK_SIZE
        self.download_dir = download_dir
    
    def prepare_upload_request(self, filename: str, filepath: str) -> Tuple[Optional[dict], Optional[int], bool]:
        """准备上传请求"""
        if not os.path.exists(filepath):
            self.logger.error('文件不存在: {0}'.format(filepath))
            return None, None, False
        
        file_size = get_file_size(filepath)
        is_large = file_size > SMALL_FILE_THRESHOLD
        
        file_hash = calculate_file_hash(filepath)
        
        request = {
            "action": ACTION_UPLOAD,
            "filename": filename,
            "size": file_size,
            "is_large": is_large,
            "chunk_size": self.chunk_size if is_large else 0,
            "hash": file_hash
        }
        
        return request, file_size, is_large
    
    def upload_file(self, client_socket, frame_handler, filepath: str) -> bool:
        """上传文件到服务器（使用文件原始名称）"""
        filename = os.path.basename(filepath)
        return self.upload_file_with_name(client_socket, frame_handler, filepath, filename)
    
    def upload_file_with_name(self, client_socket, frame_handler, filepath: str, display_name: str, progress_callback=None) -> bool:
        """上传文件到服务器（使用指定的显示名称）"""
        request, file_size, is_large = self.prepare_upload_request(display_name, filepath)
        if request is None:
            return False
        
        try:
            frame_handler.send_json_frame(client_socket, request)
            
            frame_type, response = frame_handler.receive_frame(client_socket)
            if response.get("status") != "ready":
                self.logger.error('服务器拒绝上传: {0}'.format(response.get("message")))
                return False
            
            # 获取断点续传位置
            resume_from = response.get("resume_from", 0)
            
            if is_large:
                return self.upload_file_chunked(client_socket, frame_handler, filepath, progress_callback, resume_from)
            else:
                if progress_callback:
                    progress_callback(resume_from, file_size)
                result = self.upload_file_single(client_socket, frame_handler, filepath)
                if progress_callback:
                    progress_callback(file_size, file_size)
                return result
        
        except Exception as e:
            self.logger.error('上传文件失败: {0}'.format(e))
            return False
    
    def upload_file_single(self, client_socket, frame_handler, filepath: str) -> bool:
        """一次性上传文件"""
        try:
            file_data = load_file(filepath)
            frame_handler.send_binary_frame(client_socket, file_data)
            
            frame_type, response = frame_handler.receive_frame(client_socket)
            return response.get("status") == "success"
        except Exception as e:
            self.logger.error('一次性上传文件失败: {0}'.format(e))
            return False
    
    def upload_file_chunked(self, client_socket, frame_handler, filepath: str, progress_callback=None, resume_from: int = 0) -> bool:
        """分块上传文件（支持断点续传）"""
        try:
            file_size = os.path.getsize(filepath)
            uploaded_size = resume_from  # 从断点位置开始
            
            # 如果有断点，先输出提示
            if resume_from > 0:
                self.logger.info('继续上传文件，已跳过 {0} 字节'.format(resume_from))
            
            # 连续发送所有分块，不等待每块确认（提升上传速度）
            for chunk in read_file_chunks(filepath, self.chunk_size, start_offset=resume_from):
                frame_handler.send_chunk_frame(client_socket, chunk)
                uploaded_size += len(chunk)
                
                if progress_callback:
                    progress_callback(uploaded_size, file_size)
            
            # 所有分块发送完成后，等待最终确认
            frame_type, response = frame_handler.receive_frame(client_socket)
            if response.get("status") == "success":
                if progress_callback:
                    progress_callback(file_size, file_size)
                return True
            
            self.logger.error('服务器返回错误: {0}'.format(response.get("message", "未知错误")))
            return False
        except Exception as e:
            self.logger.error('分块上传文件失败: {0}'.format(e))
            return False
    
    def prepare_download_request(self, filename: str, resume_from: int = 0) -> dict:
        """准备下载请求（支持断点续传）"""
        return {
            "action": ACTION_DOWNLOAD,
            "filename": filename,
            "resume_from": resume_from
        }
    
    def download_file(self, client_socket, frame_handler, filename: str, progress_callback=None) -> bool:
        """从服务器下载文件（支持断点续传）"""
        # 检查本地是否已存在文件（用于断点续传）
        file_path = os.path.join(self.download_dir, filename)
        resume_from = 0
        if os.path.exists(file_path):
            resume_from = os.path.getsize(file_path)
            self.logger.info('检测到已存在文件，尝试断点续传，已下载 {0} 字节'.format(resume_from))
        
        request = self.prepare_download_request(filename, resume_from)
        
        try:
            frame_handler.send_json_frame(client_socket, request)
            
            frame_type, response = frame_handler.receive_frame(client_socket)
            
            if response.get("status") != "ready":
                self.logger.error('服务器拒绝下载: {0}'.format(response.get("message")))
                return False
            
            is_large = response.get("is_large", False)
            file_size = response.get("size", 0)
            expected_hash = response.get("hash", "")
            
            if is_large:
                return self.download_file_chunked(client_socket, frame_handler, filename, file_size, expected_hash, progress_callback, resume_from)
            else:
                if progress_callback:
                    progress_callback(resume_from, file_size)
                result = self.download_file_single(client_socket, frame_handler, filename, expected_hash)
                if progress_callback:
                    progress_callback(file_size, file_size)
                return result
        
        except Exception as e:
            self.logger.error('下载文件失败: {0}'.format(e))
            return False
    
    def download_file_single(self, client_socket, frame_handler, filename: str, expected_hash: str) -> bool:
        """一次性下载文件"""
        try:
            frame_type, file_data = frame_handler.receive_frame(client_socket)
            
            if expected_hash:
                actual_hash = calculate_data_hash(file_data)
                if actual_hash != expected_hash:
                    self.logger.error('文件哈希校验失败')
                    return False
            
            file_path = os.path.join(self.download_dir, filename)
            save_file(file_path, file_data)
            
            return True
        except Exception as e:
            self.logger.error('一次性下载文件失败: {0}'.format(e))
            return False
    
    def download_file_chunked(self, client_socket, frame_handler, filename: str, file_size: int, expected_hash: str, progress_callback=None, resume_from: int = 0, retry_count: int = 0) -> bool:
        """分块下载文件（支持断点续传）"""
        try:
            received_size = resume_from
            file_path = os.path.join(self.download_dir, filename)
            
            # 如果是断点续传，以追加模式打开；否则以写入模式打开
            mode = 'ab' if resume_from > 0 else 'wb'
            
            with open(file_path, mode) as f:
                while received_size < file_size:
                    frame_type, chunk = frame_handler.receive_frame(client_socket)
                    f.write(chunk)
                    received_size += len(chunk)
                    
                    if progress_callback:
                        progress_callback(received_size, file_size)
            
            # 校验文件完整性
            if expected_hash:
                file_data = load_file(file_path)
                actual_hash = calculate_data_hash(file_data)
                
                if actual_hash != expected_hash:
                    self.logger.error('文件哈希校验失败')
                    # 如果是断点续传，可能是之前的文件损坏，删除并重新下载
                    if resume_from > 0 and retry_count < 3:
                        self.logger.info('断点续传哈希校验失败，删除损坏文件并重试（第{0}次重试）'.format(retry_count + 1))
                        os.remove(file_path)
                        frame_handler.send_json_frame(client_socket, {"status": "error", "message": "文件哈希校验失败，需要重新下载"})
                        # 重新发起下载请求（从头开始）
                        return self.download_file(client_socket, frame_handler, filename, progress_callback)
                    else:
                        frame_handler.send_json_frame(client_socket, {"status": "error", "message": "文件哈希校验失败"})
                        return False
            
            if progress_callback:
                progress_callback(file_size, file_size)
            
            frame_handler.send_json_frame(client_socket, {"status": "success", "message": "文件下载成功"})
            return True
        except Exception as e:
            self.logger.error('分块下载文件失败: {0}'.format(e))
            try:
                frame_handler.send_json_frame(client_socket, {"status": "error", "message": str(e)})
            except Exception:
                pass
            return False
    
    def prepare_list_files_request(self) -> dict:
        """准备文件列表请求"""
        return {
            "action": ACTION_LISTFILES
        }
    
    def process_list_files_response(self, response) -> list:
        """处理文件列表响应"""
        if not isinstance(response, dict):
            return []
        
        # 检查响应状态
        if response.get("status") != "success":
            return []
        
        files = response.get("files", [])
        return files
