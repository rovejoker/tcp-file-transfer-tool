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
import select
import time
import threading

# Windows 虚拟终端支持
if sys.platform == 'win32':
    def _enable_virtual_terminal():
        """启用Windows虚拟终端支持（用于ANSI转义序列）"""
        try:
            import ctypes
            STD_OUTPUT_HANDLE = -11
            hConsole = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            mode = ctypes.wintypes.DWORD()
            ctypes.windll.kernel32.GetConsoleMode(hConsole, ctypes.byref(mode))
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            mode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
            ctypes.windll.kernel32.SetConsoleMode(hConsole, mode)
        except Exception:
            pass
    _enable_virtual_terminal()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.network import FrameHandler
from src.business import ClientHandler
from src.common import ConfigManager, ConfigUI
from src.utils.logger import configure_logging, get_logger
from src.utils.file_utils import (
    ensure_directory, SMALL_FILE_THRESHOLD, 
    is_filename_length_valid, get_max_filename_length, 
    is_filename_safe
)
from src.utils.progress_bar import ProgressBar


def is_socket_connected(client_socket):
    """检查socket连接是否仍然有效"""
    try:
        error_code = client_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        return error_code == 0
    except Exception:
        return False


def check_server_shutdown(client_socket, frame_handler):
    """检查服务器是否发送了关闭通知或连接是否已断开"""
    global is_transferring
    
    # 如果正在传输文件，跳过检查以避免干扰
    if is_transferring:
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


def get_windows_input_non_blocking(hConsoleInput):
    """非阻塞方式读取单个按键输入（Windows专用）"""
    import ctypes
    import ctypes.wintypes
    
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    
    class KEY_EVENT_RECORD(ctypes.Structure):
        _fields_ = [
            ("bKeyDown", ctypes.wintypes.BOOL),
            ("wRepeatCount", ctypes.wintypes.WORD),
            ("wVirtualKeyCode", ctypes.wintypes.WORD),
            ("wVirtualScanCode", ctypes.wintypes.WORD),
            ("uChar", ctypes.wintypes.WCHAR),
            ("dwControlKeyState", ctypes.wintypes.DWORD)
        ]
    
    class INPUT_RECORD(ctypes.Structure):
        _fields_ = [
            ("EventType", ctypes.wintypes.WORD),
            ("KeyEvent", KEY_EVENT_RECORD)
        ]
    
    KEY_EVENT = 0x0001
    ir = INPUT_RECORD()
    num_read = ctypes.wintypes.DWORD()
    
    success = kernel32.PeekConsoleInputW(hConsoleInput, ctypes.byref(ir), 1, ctypes.byref(num_read))
    if not success or num_read.value == 0:
        return None
    
    kernel32.ReadConsoleInputW(hConsoleInput, ctypes.byref(ir), 1, ctypes.byref(num_read))
    
    if ir.EventType == KEY_EVENT:
        key_event = ir.KeyEvent
        if key_event.bKeyDown:
            if key_event.wVirtualKeyCode == 13:
                return '\n'
            elif key_event.wVirtualKeyCode == 8:
                return '\b'
            elif key_event.uChar != '\x00':
                return key_event.uChar
    return None


def get_windows_input_with_check(prompt, client_socket, frame_handler):
    """使用 Windows Unicode API 读取中文输入（带连接检查）"""
    import ctypes
    
    global connection_lost
    
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    STD_INPUT_HANDLE = -10
    hConsoleInput = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    
    if hConsoleInput == 0:
        return input(prompt)
    
    buffer = []
    print(prompt, end='', flush=True)
    
    while True:
        if connection_lost:
            print('\n心跳检测到连接已断开')
            return None
        
        try:
            error_code = client_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if error_code != 0:
                print('\n检测到socket错误，连接已断开')
                return None
        except Exception as e:
            print('\n检查连接状态失败: {0}'.format(e))
            return None
        
        char = get_windows_input_non_blocking(hConsoleInput)
        
        if char == '\n':
            print()
            return ''.join(buffer)
        elif char == '\b':
            if buffer:
                buffer.pop()
                sys.stdout.write('\b \b')
                sys.stdout.flush()
        elif char is not None:
            buffer.append(char)
            sys.stdout.write(char)
            sys.stdout.flush()
        
        time.sleep(0.01)


def get_input_with_server_check(client_socket, frame_handler, prompt):
    """在等待用户输入时检测服务器关闭通知"""
    if sys.platform == 'win32':
        return get_windows_input_with_check(prompt, client_socket, frame_handler)
    else:
        print(prompt, end='', flush=True)
        buffer = []
        
        while True:
            if check_server_shutdown(client_socket, frame_handler):
                print()
                return None
            
            if not is_socket_connected(client_socket):
                print('\n检测到与服务器的连接已断开')
                return None
            
            read_list, _, _ = select.select([sys.stdin], [], [], 0.1)
            if read_list:
                line = sys.stdin.readline()
                return line.strip()
            
            time.sleep(0.05)


# 全局连接状态
connection_lost = False
is_transferring = False
heartbeat_thread = None
heartbeat_stop_event = None


def heartbeat_monitor(client_socket, frame_handler):
    """心跳监控线程"""
    global connection_lost, is_transferring
    heartbeat_interval = 3
    max_timeouts = 2
    timeout_count = 0
    
    while not heartbeat_stop_event.is_set():
        if is_transferring:
            time.sleep(0.5)
            continue
            
        try:
            heartbeat_request = {"action": "heartbeat", "timestamp": int(time.time())}
            frame_handler.send_json_frame(client_socket, heartbeat_request)
            
            frame_type, response = frame_handler.receive_frame(client_socket, timeout=5)
            
            if response is None or response.get("status") != "success":
                timeout_count += 1
                if timeout_count >= max_timeouts:
                    print("\n连接超时，心跳检测失败")
                    connection_lost = True
                    break
            else:
                timeout_count = 0
                
        except socket.timeout:
            timeout_count += 1
            if timeout_count >= max_timeouts:
                print("\n心跳超时，连接可能已断开")
                connection_lost = True
                break
        except Exception as e:
            print(f"\n心跳检测异常: {e}")
            connection_lost = True
            break
            
        for _ in range(heartbeat_interval):
            if heartbeat_stop_event.is_set():
                break
            time.sleep(1)


def reconnect_with_backoff(config_manager, max_retries=5):
    """带退避策略的重连"""
    server_host = config_manager.get("server.host", "127.0.0.1")
    server_port = config_manager.get("server.port", 2983)
    
    backoff = 1
    for attempt in range(max_retries):
        try:
            print(f"\n尝试重新连接 ({attempt + 1}/{max_retries})...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((server_host, server_port))
            print("重连成功！")
            return client_socket
        except ConnectionRefusedError:
            print(f"连接失败，等待 {backoff} 秒后重试...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
    
    print("重连失败，已达最大重试次数")
    return None


def upload_file(client_socket, frame_handler, client_handler):
    """上传文件到服务器"""
    global is_transferring
    
    display_name = get_input_with_server_check(client_socket, frame_handler, "请输入文件名称: ")
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
    
    filepath = get_input_with_server_check(client_socket, frame_handler, "请输入文件路径: ")
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
        is_transferring = True
        success = client_handler.upload_file_with_name(client_socket, frame_handler, filepath, display_name, progress_callback)
        progress_bar.finish()
        print("文件上传成功" if success else "文件上传失败")
        return success
    except Exception as e:
        progress_bar.finish()
        print("上传文件时发生错误: {0}".format(e))
        return None
    finally:
        is_transferring = False


def download_file(client_socket, frame_handler, client_handler):
    """从服务器下载文件"""
    global is_transferring
    
    filename = get_input_with_server_check(client_socket, frame_handler, "请输入要下载的文件名: ")
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
        # 提前设置 is_transferring，防止心跳线程干扰
        is_transferring = True
        
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
        is_transferring = False


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
    
    print("连接到 {0}:{1}...".format(server_host, server_port))
    
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_host, server_port))
        print("连接成功")
        return client_socket
    except Exception as e:
        print("连接失败: {0}".format(e))
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


def handle_menu_choice(choice, client_socket, frame_handler, client_handler):
    """处理菜单选择"""
    if choice == '1':
        return upload_file(client_socket, frame_handler, client_handler)
    elif choice == '2':
        return download_file(client_socket, frame_handler, client_handler)
    elif choice == '3':
        return list_files(client_socket, frame_handler, client_handler)
    elif choice == '4':
        return 'back'
    elif choice == '5':
        return 'exit'
    else:
        print("无效选择，请输入 1-5")
        return True


def main():
    """主函数"""
    global connection_lost, heartbeat_thread, heartbeat_stop_event
    
    configure_logging()
    logger = get_logger(__name__)
    
    config_manager = ConfigManager("config/client_config.json")
    
    while True:
        print("=" * 60)
        print("    TCP 文件传输客户端")
        print("=" * 60)
        
        choice = input("是否修改配置? (y/n，默认n): ").strip().lower()
        if choice == 'y':
            ConfigUI.edit_client_config(config_manager)
        
        download_dir = config_manager.get("client.download_dir", "downloads")
        ensure_directory(download_dir)
        
        client_handler = ClientHandler(download_dir=download_dir)
        frame_handler = FrameHandler()
        
        client_socket = connect_to_server(config_manager)
        if not client_socket:
            print("\n连接失败，是否重新配置服务器地址?")
            retry_choice = input("输入 'y' 重新配置，其他键退出: ").strip().lower()
            if retry_choice != 'y':
                print("退出客户端...")
                break
            continue
        
        # 启动心跳监控线程
        heartbeat_stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=heartbeat_monitor, 
            args=(client_socket, frame_handler),
            daemon=True
        )
        heartbeat_thread.start()
        
        connected = True
        result = None
        while connected:
            if connection_lost:
                print("\n检测到连接断开，尝试重新连接...")
                client_socket.close()
                client_socket = reconnect_with_backoff(config_manager)
                
                if client_socket:
                    connection_lost = False
                    heartbeat_stop_event.set()
                    heartbeat_stop_event = threading.Event()
                    heartbeat_thread = threading.Thread(
                        target=heartbeat_monitor, 
                        args=(client_socket, frame_handler),
                        daemon=True
                    )
                    heartbeat_thread.start()
                    print("重新连接成功，可以继续操作")
                else:
                    print("无法重新连接")
                    connected = False
                    break
            
            show_menu()
            user_choice = get_input_with_server_check(client_socket, frame_handler, "\n请输入选择 (1-5): ")
            
            if user_choice is None:
                print("连接已断开或服务器关闭")
                connected = False
                break
            
            result = handle_menu_choice(user_choice, client_socket, frame_handler, client_handler)
            
            if result is None:
                print("连接已断开")
                connected = False
                break
            elif result == 'back':
                connected = False
                print("返回配置界面...")
            elif result == 'exit':
                connected = False
                print("退出客户端...")
        
        if heartbeat_stop_event:
            heartbeat_stop_event.set()
        
        if connected == False and result != 'exit':
            print("\n是否重新配置服务器地址并重新连接?")
            retry_choice = input("输入 'y' 重新配置，其他键退出: ").strip().lower()
            if retry_choice != 'y':
                print("退出客户端...")
                break
        
        try:
            client_socket.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()