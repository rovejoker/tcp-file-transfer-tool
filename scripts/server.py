# -*- coding: utf-8 -*-
"""
TCP 文件传输服务器

监听指定端口，接收客户端连接并处理文件传输请求。
支持文件上传、下载和列表功能，根据文件大小自动选择传输方式。
"""

import os
import sys
import socket
import threading
import time
import signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.network import FrameHandler
from src.business import ServerHandler
from src.common import ConfigManager, ConfigUI
from src.utils.logger import configure_logging, get_logger
from src.utils.file_utils import ensure_directory


def handle_client(client_socket, client_address, server_handler, frame_handler, shutdown_event):
    """
    处理单个客户端连接
    
    Args:
        client_socket: 客户端socket连接
        client_address: 客户端地址元组
        server_handler: 服务器业务处理器
        frame_handler: 帧处理器
        shutdown_event: 关闭事件标志
    """
    logger = get_logger(__name__)
    logger.info('新客户端连接: {0}'.format(client_address))
    
    try:
        client_socket.settimeout(300)
        
        while not shutdown_event.is_set():
            try:
                frame_type, decoded_data = frame_handler.receive_frame(client_socket)
                
                if frame_type is None:
                    logger.info('{0} 连接关闭'.format(client_address))
                    break
                
                response = server_handler.handle_request(frame_type, decoded_data, client_address)
                
                if response is not None:
                    if response.get("action") == "download":
                        logger.info('准备发送下载响应: {0}'.format(response.get("filename")))
                        frame_handler.send_json_frame(client_socket, response)
                        logger.info('下载响应发送成功')
                        
                        # 直接发送文件数据，不等待确认（简化流程）
                        filename = response.get("filename")
                        resume_from = response.get("resume_from", 0)
                        if response.get("is_large", False):
                            server_handler.download_file_chunked(client_socket, frame_handler, filename, resume_from)
                        else:
                            server_handler.download_file_single(client_socket, frame_handler, filename)
                    elif isinstance(response, dict):
                        frame_handler.send_json_frame(client_socket, response)
                    elif isinstance(response, bytes):
                        frame_handler.send_binary_frame(client_socket, response)
                
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError, OSError):
                logger.info('{0} 连接异常断开'.format(client_address))
                break
            except ValueError as e:
                if "无法接收完整头部数据" in str(e):
                    logger.info('{0} 连接关闭（数据不完整）'.format(client_address))
                else:
                    logger.error('处理客户端请求时发生错误: {0}'.format(e))
                break
            except Exception as e:
                logger.error('处理客户端请求时发生错误: {0}'.format(e))
                break
                
    finally:
        server_handler.decrement_connection_count(client_address)
        try:
            client_socket.close()
        except Exception:
            pass
        logger.info('{0} 连接已关闭'.format(client_address))


def main():
    """主函数"""
    configure_logging()
    logger = get_logger(__name__)
    
    config_manager = ConfigManager("config/server_config.json")
    
    print("=" * 60)
    print("    TCP 文件传输服务器")
    print("=" * 60)
    
    # 先打印当前配置
    server_port = config_manager.get("server.port", 2983)
    resource_dir = config_manager.get("server.resource_dir", "resource")
    max_file_size_mb = config_manager.get("server.max_file_size_mb", 1024)
    
    print("\n当前配置:")
    print("-" * 40)
    print("监听端口: {0}".format(server_port))
    print("资源目录: {0}".format(resource_dir))
    print("最大文件大小: {0} MB".format(max_file_size_mb))
    print("-" * 40)
    
    choice = input("\n是否修改配置? (y/n，默认n): ").strip().lower()
    if choice == 'y':
        ConfigUI.edit_server_config(config_manager)
    
    # 重新获取配置（可能已修改）
    server_port = config_manager.get("server.port", 2983)
    resource_dir = config_manager.get("server.resource_dir", "resource")
    max_file_size_mb = config_manager.get("server.max_file_size_mb", 1024)
    
    ensure_directory(resource_dir)
    
    # 初始化关闭事件
    shutdown_event = threading.Event()
    
    def signal_handler(signum, frame):
        """信号处理器：处理 SIGINT 和 SIGTERM"""
        logger.info('接收到停止信号，正在关闭服务器...')
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建并配置服务器socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind(('0.0.0.0', server_port))
        server_socket.listen(100)
        logger.info('服务器已启动，监听端口 {0}'.format(server_port))
        print('服务器已启动，监听端口 {0}'.format(server_port), flush=True)
        print('按 Ctrl+C 停止服务器', flush=True)
        
        server_handler = ServerHandler(resource_dir=resource_dir, max_file_size_mb=max_file_size_mb)
        frame_handler = FrameHandler()
        
        while not shutdown_event.is_set():
            try:
                server_socket.settimeout(1)
                client_socket, client_address = server_socket.accept()
                client_ip = client_address[0]
                
                # 检查单IP连接数限制
                if not server_handler.check_ip_connection_limit(client_address):
                    logger.warning('拒绝来自 {0} 的连接：超过单IP最大连接数限制'.format(client_ip))
                    try:
                        import json
                        response = {"status": "error", "message": "连接数超过限制"}
                        response_bytes = json.dumps(response).encode('utf-8')
                        client_socket.sendall(response_bytes)
                        time.sleep(0.1)
                    except Exception:
                        pass
                    try:
                        client_socket.shutdown(socket.SHUT_RDWR)
                        client_socket.close()
                    except Exception:
                        pass
                    continue
                
                # 增加连接计数
                server_handler.increment_connection_count(client_address)
                
                # 创建客户端处理线程
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, client_address, server_handler, frame_handler, shutdown_event)
                )
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if not shutdown_event.is_set():
                    logger.error('接受客户端连接时发生错误: {0}'.format(e))
        
    except Exception as e:
        logger.error('服务器启动失败: {0}'.format(e))
        print('服务器启动失败: {0}'.format(e))
        return
    finally:
        logger.info('正在关闭服务器...')
        print('正在关闭服务器...')
        
        server_socket.close()
        
        time.sleep(0.3)
        logger.info('服务器已关闭')
        print('服务器已关闭')


if __name__ == "__main__":
    main()