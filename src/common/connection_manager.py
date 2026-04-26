# -*- coding: utf-8 -*-
"""
连接管理器模块

管理客户端与服务器的连接状态、心跳检测和自动重连功能。
"""

import socket
import threading
import time
import select


class ConnectionManager:
    """
    连接管理器
    
    负责管理socket连接、心跳检测和自动重连。
    """
    
    def __init__(self):
        self.connection_lost = False
        self.is_transferring = False
        self._heartbeat_thread = None
        self._heartbeat_stop_event = None
        self._heartbeat_interval = 3
        self._max_timeouts = 2
    
    def start_heartbeat(self, client_socket, frame_handler):
        """
        启动心跳监控线程
        
        Args:
            client_socket: 客户端socket连接
            frame_handler: 帧处理器
        """
        self._heartbeat_stop_event = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_monitor,
            args=(client_socket, frame_handler),
            daemon=True
        )
        self._heartbeat_thread.start()
    
    def stop_heartbeat(self):
        """停止心跳监控"""
        if self._heartbeat_stop_event:
            self._heartbeat_stop_event.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1)
    
    def _heartbeat_monitor(self, client_socket, frame_handler):
        """心跳监控线程"""
        timeout_count = 0
        
        while not self._heartbeat_stop_event.is_set():
            # 如果正在传输文件，暂停心跳检测
            if self.is_transferring:
                time.sleep(0.5)
                continue
            
            try:
                heartbeat_request = {"action": "heartbeat", "timestamp": int(time.time())}
                frame_handler.send_json_frame(client_socket, heartbeat_request)
                
                frame_type, response = frame_handler.receive_frame(client_socket, timeout=5)
                
                if response is None or response.get("status") != "success":
                    timeout_count += 1
                    if timeout_count >= self._max_timeouts:
                        print("\n连接超时，心跳检测失败")
                        self.connection_lost = True
                        break
                else:
                    timeout_count = 0
                    
            except socket.timeout:
                timeout_count += 1
                if timeout_count >= self._max_timeouts:
                    print("\n心跳超时，连接可能已断开")
                    self.connection_lost = True
                    break
            except Exception as e:
                print(f"\n心跳检测异常: {e}")
                self.connection_lost = True
                break
            
            # 心跳间隔等待
            for _ in range(self._heartbeat_interval):
                if self._heartbeat_stop_event.is_set():
                    break
                time.sleep(1)
    
    def reconnect_with_backoff(self, config_manager, max_retries=5):
        """
        带退避策略的重连
        
        Args:
            config_manager: 配置管理器
            max_retries: 最大重试次数
        
        Returns:
            socket: 重新连接的socket，失败返回None
        """
        server_host = config_manager.get("server.host", "127.0.0.1")
        server_port = config_manager.get("server.port", 2983)
        
        backoff = 1
        for attempt in range(max_retries):
            try:
                print(f"\n尝试重新连接 ({attempt + 1}/{max_retries})...")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((server_host, server_port))
                print("重连成功！")
                self.connection_lost = False
                return client_socket
            except ConnectionRefusedError:
                print(f"连接失败，等待 {backoff} 秒后重试...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
        
        print("重连失败，已达最大重试次数")
        return None
    
    def check_server_shutdown(self, client_socket, frame_handler):
        """
        检查服务器是否发送了关闭通知或连接是否已断开
        
        Args:
            client_socket: 客户端socket连接
            frame_handler: 帧处理器
        
        Returns:
            bool: 是否检测到关闭
        """
        if self.is_transferring:
            return False
        
        try:
            client_socket.setblocking(False)
            try:
                read_list, _, _ = select.select([client_socket], [], [], 0.01)
                if read_list:
                    try:
                        frame_type, data = frame_handler.receive_frame(client_socket)
                        if frame_type is not None:
                            if isinstance(data, dict) and data.get("type") == "server_shutdown":
                                message = data.get("message", "服务器即将关闭")
                                print('服务器通知: {0}'.format(message))
                                return True
                        else:
                            print("\n检测到服务器连接已断开")
                            return True
                    except (ConnectionResetError, BrokenPipeError, OSError):
                        print("\n检测到服务器连接已断开")
                        return True
                    except Exception:
                        print("\n检测到连接异常")
                        return True
            finally:
                client_socket.setblocking(True)
        except Exception:
            pass
        return False