# -*- coding: utf-8 -*-
"""
TCP 文件传输客户端

连接到服务器并提供文件上传、下载和列表功能。
根据文件大小自动选择传输方式：
- 小文件（<=50MB）：一次性传输
- 大文件（>50MB）：分块传输

支持心跳检测和自动重连功能。
"""

import socket
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.network import FrameHandler
from src.business import ClientHandler
from src.common import ConfigManager, ConfigUI
from src.common.connection_manager import ConnectionManager
from src.common.ui_utils import get_input_with_connection_check
from src.utils.logger import configure_logging
from src.utils.file_utils import (
    ensure_directory, SMALL_FILE_THRESHOLD, 
    is_filename_length_valid, get_max_filename_length, 
    is_filename_safe
)
from src.utils.progress_bar import ProgressBar


def upload_file(client_socket, frame_handler, client_handler, connection_manager):
    """上传文件到服务器"""
    display_name = get_input_with_connection_check(
        "请输入文件显示名称: ", 
        client_socket,
        lambda: connection_manager.connection_lost
    )
    if display_name is None:
        return None
    
    if not display_name.strip():
        print("文件显示名称不能为空")
        return True
    
    max_length = get_max_filename_length()
    if not is_filename_length_valid(display_name, max_length):
        print("文件名过长，最大允许 {0} 个字符".format(max_length))
        print("当前文件名长度: {0} 个字符".format(len(display_name)))
        return True
    
    if not is_filename_safe(display_name):
        print("不安全的文件名，不允许包含路径字符（如 ../ 或 \\）")
        return True
    
    filepath = get_input_with_connection_check(
        "请输入文件路径: ",
        client_socket,
        lambda: connection_manager.connection_lost
    )
    if filepath is None:
        return None
    
    if not os.path.exists(filepath):
        print("文件不存在")
        return True
    
    if not os.path.isfile(filepath):
        print("路径不是文件")
        return True
    
    file_size = os.path.getsize(filepath)
    print("文件大小: {0:.2f} MB".format(file_size / (1024 * 1024)))
    
    if file_size > SMALL_FILE_THRESHOLD:
        print("检测到大文件，将使用分块上传方式")
    else:
        print("检测到小文件，将使用一次性上传方式")
    
    print("准备上传文件...")
    
    progress_bar = ProgressBar(file_size)
    
    def progress_callback(current, total):
        progress_bar.update(current)
    
    try:
        connection_manager.is_transferring = True
        success = client_handler.upload_file_with_name(client_socket, frame_handler, filepath, display_name, progress_callback)
        progress_bar.finish()
        print("文件上传成功" if success else "文件上传失败")
        return success
    except Exception as e:
        progress_bar.finish()
        print("上传文件时发生错误: {0}".format(e))
        return None
    finally:
        connection_manager.is_transferring = False


def download_file(client_socket, frame_handler, client_handler, connection_manager):
    """从服务器下载文件"""
    filename = get_input_with_connection_check(
        "请输入要下载的文件名: ",
        client_socket,
        lambda: connection_manager.connection_lost
    )
    if filename is None:
        return None
    
    if not filename.strip():
        print("文件名不能为空")
        return True
    
    print("准备下载文件...")
    
    # 先获取文件信息以初始化进度条
    file_path = os.path.join(client_handler.download_dir, filename)
    resume_from = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    
    progress_bar = None
    
    try:
        connection_manager.is_transferring = True
        
        request = client_handler.prepare_download_request(filename, resume_from)
        frame_handler.send_json_frame(client_socket, request)
        frame_type, response = frame_handler.receive_frame(client_socket)
        
        if response.get("status") != "ready":
            print("服务器拒绝下载: {0}".format(response.get("message")))
            return False
        
        file_size = response.get("size", 0)
        is_large = response.get("is_large", False)
        expected_hash = response.get("hash", "")
        
        progress_bar = ProgressBar(file_size)
        
        def progress_callback(current, total):
            progress_bar.update(current)
        
        # 根据文件大小选择下载方式
        if is_large:
            success = client_handler.download_file_chunked(client_socket, frame_handler, filename, 
                                                          file_size, expected_hash, 
                                                          progress_callback, resume_from)
        else:
            if resume_from > 0:
                progress_callback(resume_from, file_size)
            success = client_handler.download_file_single(client_socket, frame_handler, 
                                                         filename, expected_hash)
            progress_callback(file_size, file_size)
        
        progress_bar.finish()
        print("文件下载成功" if success else "文件下载失败")
        return success
    except Exception as e:
        if progress_bar:
            progress_bar.finish()
        print("下载文件时发生错误: {0}".format(e))
        return None
    finally:
        connection_manager.is_transferring = False


def list_files(client_socket, frame_handler, client_handler):
    """列出服务器文件"""
    print("获取服务器文件列表...")
    
    request = client_handler.prepare_list_files_request()
    
    try:
        frame_handler.send_json_frame(client_socket, request)
        frame_type, response = frame_handler.receive_frame(client_socket)
        files = client_handler.process_list_files_response(response)
        
        if not files:
            print("服务器上没有文件")
        else:
            print("\n服务器文件列表:")
            print("-" * 60)
            print("{0:<40} {1:>15} {2:>10}".format("文件名", "大小", "修改时间"))
            print("-" * 60)
            for f in files:
                size_str = "{0:.2f} MB".format(f["size"] / (1024 * 1024)) if f["size"] > 1024 else "{0} B".format(f["size"])
                print("{0:<40} {1:>15} {2:>10}".format(f["name"], size_str, f["mtime"]))
            print("-" * 60)
        
        return True
    except Exception as e:
        print("获取文件列表时发生错误: {0}".format(e))
        return None


def connect_to_server(config_manager):
    """连接到服务器"""
    server_host = config_manager.get("server.host")
    server_port = config_manager.get("server.port")
    
    print("连接到 {0}:{1}...".format(server_host, server_port), flush=True)
    
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_host, server_port))
        print("连接成功", flush=True)
        return client_socket
    except Exception as e:
        print("连接失败: {0}".format(e), flush=True)
        return None


def show_menu():
    """显示菜单"""
    print("\n" + "=" * 60)
    print("请选择操作:")
    print("=" * 60)
    print("1. 上传文件")
    print("2. 下载文件")
    print("3. 查看服务器文件列表")
    print("4. 返回配置界面")
    print("5. 退出")
    print("=" * 60)


def handle_menu_choice(choice, client_socket, frame_handler, client_handler, connection_manager):
    """处理菜单选择"""
    if choice == '1':
        return upload_file(client_socket, frame_handler, client_handler, connection_manager)
    elif choice == '2':
        return download_file(client_socket, frame_handler, client_handler, connection_manager)
    elif choice == '3':
        return list_files(client_socket, frame_handler, client_handler)
    elif choice == '4':
        return 'back'
    elif choice == '5':
        return 'exit'
    else:
        print("无效选择，请输入 1-5")
        return True


def print_current_config(config_manager):
    """打印当前配置"""
    print("\n当前配置:")
    print("-" * 40)
    print("服务器地址: {0}".format(config_manager.get("server.host", "未设置")))
    print("服务器端口: {0}".format(config_manager.get("server.port", "未设置")))
    print("下载目录: {0}".format(config_manager.get("client.download_dir", "未设置")))
    print("-" * 40)


def main():
    """主函数"""
    configure_logging()
    
    config_manager = ConfigManager("config/client_config.json")
    
    while True:
        print("=" * 60)
        print("    TCP 文件传输客户端")
        print("=" * 60)
        
        # 先打印当前配置
        print_current_config(config_manager)
        
        choice = input("\n是否修改配置? (y/n，默认n): ").strip().lower()
        if choice == 'y':
            ConfigUI.edit_client_config(config_manager)
        
        download_dir = config_manager.get("client.download_dir", "downloads")
        ensure_directory(download_dir)
        
        client_handler = ClientHandler(download_dir=download_dir)
        frame_handler = FrameHandler()
        connection_manager = ConnectionManager()
        
        client_socket = connect_to_server(config_manager)
        if not client_socket:
            print("\n连接失败，是否重新配置服务器地址?")
            retry_choice = input("输入 'y' 重新配置，其他键退出: ").strip().lower()
            if retry_choice != 'y':
                print("退出客户端...")
                break
            continue
        
        # 启动心跳监控
        connection_manager.start_heartbeat(client_socket, frame_handler)
        
        connected = True
        result = None
        while connected:
            if connection_manager.connection_lost:
                print("\n检测到连接断开，尝试重新连接...")
                client_socket.close()
                client_socket = connection_manager.reconnect_with_backoff(config_manager)
                
                if client_socket:
                    connection_manager.start_heartbeat(client_socket, frame_handler)
                    print("重新连接成功，可以继续操作")
                else:
                    print("无法重新连接")
                    connected = False
                    break
            
            show_menu()
            user_choice = get_input_with_connection_check(
                "\n请输入选择 (1-5): ",
                client_socket,
                lambda: connection_manager.connection_lost
            )
            
            if user_choice is None:
                print("连接已断开或服务器关闭")
                connected = False
                break
            
            result = handle_menu_choice(user_choice, client_socket, frame_handler, client_handler, connection_manager)
            
            if result is None:
                # print("连接已断开")
                connected = False
                break
            elif result == 'back':
                connected = False
                # print("返回配置界面...")
            elif result == 'exit':
                connected = False
        
        connection_manager.stop_heartbeat()
        
        if result == 'exit':
            print("退出客户端...")
            break
        
        try:
            client_socket.close()
        except Exception:
            pass
        
        # 连接断开或返回配置界面，直接回到配置界面（主循环开头）
        if connected == False:
            print("\n连接已断开，返回配置界面...")


if __name__ == "__main__":
    main()