# -*- coding: utf-8 -*-
"""
TCP 文件传输客户端
连接到服务器并提供文件上传、下载和列表功能
根据文件大小自动选择传输方式
"""

import socket
import os
import sys
import select
import time
import threading

if sys.platform == 'win32':
    import ctypes
    import ctypes.wintypes
    
    def enable_virtual_terminal():
        """启用Windows虚拟终端支持（用于ANSI转义序列）"""
        try:
            import ctypes
            STD_OUTPUT_HANDLE = -11
            hConsole = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            
            # 获取当前模式
            mode = ctypes.wintypes.DWORD()
            ctypes.windll.kernel32.GetConsoleMode(hConsole, ctypes.byref(mode))
            
            # 启用虚拟终端处理
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            mode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
            
            ctypes.windll.kernel32.SetConsoleMode(hConsole, mode)
        except:
            pass
    
    # 在程序启动时启用虚拟终端支持
    enable_virtual_terminal()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.network import SocketManager, FrameHandler
from src.business import ClientHandler
from src.common import ConfigManager, ConfigUI
from src.utils.logger import configure_logging, get_logger
from src.utils.file_utils import ensure_directory, SMALL_FILE_THRESHOLD, is_filename_length_valid, get_max_filename_length, sanitize_filename, is_filename_safe


def is_socket_connected(client_socket):
    """检查socket连接是否仍然有效"""
    try:
        # 使用 getsockopt 检查错误状态（最可靠的方法）
        error_code = client_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if error_code != 0:
            return False
        
        return True
    except Exception:
        return False


def check_server_shutdown(client_socket, frame_handler):
    """检查服务器是否发送了关闭通知或连接是否已断开"""
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
                        # 如果收到空数据或无法解析，可能是连接断开
                        print("\n检测到服务器连接已断开")
                        return True
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    # 连接被重置或断开
                    print("\n检测到服务器连接已断开: {0}".format(e))
                    return True
                except Exception:
                    # 其他异常可能表示连接问题
                    print("\n检测到连接异常")
                    return True
        finally:
            client_socket.setblocking(True)
    except Exception:
        pass
    return False


def get_windows_input_non_blocking(hConsoleInput):
    """非阻塞方式读取单个按键输入"""
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
    
    # 使用 PeekConsoleInputW 检查是否有输入（非阻塞）
    ir = INPUT_RECORD()
    num_read = ctypes.wintypes.DWORD()
    
    # 先窥视输入队列，不移除
    success = kernel32.PeekConsoleInputW(hConsoleInput, ctypes.byref(ir), 1, ctypes.byref(num_read))
    if not success or num_read.value == 0:
        return None  # 没有输入
    
    # 有输入，读取并移除
    kernel32.ReadConsoleInputW(hConsoleInput, ctypes.byref(ir), 1, ctypes.byref(num_read))
    
    if ir.EventType == KEY_EVENT:
        key_event = ir.KeyEvent
        if key_event.bKeyDown:
            if key_event.wVirtualKeyCode == 13:  # Enter
                return '\n'
            elif key_event.wVirtualKeyCode == 8:  # Backspace
                return '\b'
            elif key_event.uChar != '\x00':
                return key_event.uChar
    
    return None


def get_windows_input_with_check(prompt, client_socket, frame_handler):
    """使用 Windows Unicode API 读取中文输入（带连接检查）"""
    import ctypes
    import ctypes.wintypes
    import time
    
    global connection_lost
    
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    
    STD_INPUT_HANDLE = -10
    hConsoleInput = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    
    if hConsoleInput == 0:
        return input(prompt)
    
    buffer = []
    print(prompt, end='', flush=True)
    
    while True:
        # 检查全局连接状态标志（由心跳线程更新）
        if connection_lost:
            print('\n心跳检测到连接已断开')
            return None
        
        # 检查socket错误状态
        try:
            error_code = client_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if error_code != 0:
                print('\n检测到socket错误，连接已断开')
                return None
        except Exception as e:
            print('\n检查连接状态失败: {0}'.format(e))
            return None
        
        # 非阻塞方式读取输入
        char = get_windows_input_non_blocking(hConsoleInput)
        
        if char == '\n':  # Enter
            print()
            return ''.join(buffer)
        elif char == '\b':  # Backspace
            if buffer:
                buffer.pop()
                sys.stdout.write('\b \b')
                sys.stdout.flush()
        elif char is not None:
            buffer.append(char)
            sys.stdout.write(char)
            sys.stdout.flush()
        
        # 短暂延迟，让出CPU时间
        time.sleep(0.01)


def get_input_with_server_check(client_socket, frame_handler, prompt):
    """在等待用户输入时检测服务器关闭通知"""
    import sys
    
    if sys.platform == 'win32':
        return get_windows_input_with_check(prompt, client_socket, frame_handler)
    else:
        # 非Windows系统使用select实现非阻塞输入
        print(prompt, end='', flush=True)
        buffer = []
        
        while True:
            # 检查连接状态
            if check_server_shutdown(client_socket, frame_handler):
                print()
                return None
            
            if not is_socket_connected(client_socket):
                print('\n检测到与服务器的连接已断开')
                return None
            
            # 非阻塞读取输入
            read_list, _, _ = select.select([sys.stdin], [], [], 0.1)
            if read_list:
                line = sys.stdin.readline()
                return line.strip()
            
            # 短暂等待后继续检查
            time.sleep(0.05)


class ProgressTracker:
    """进度跟踪器，支持速度计算"""
    
    def __init__(self):
        self.start_time = time.time()
        self.last_time = self.start_time
        self.last_bytes = 0
        self.current_speed = 0.0
    
    def update(self, current_bytes):
        """更新进度，返回当前速度(MB/s)"""
        current_time = time.time()
        elapsed = current_time - self.last_time
        
        if elapsed > 0.1:  # 至少0.1秒才计算速度
            bytes_diff = current_bytes - self.last_bytes
            self.current_speed = (bytes_diff / (1024 * 1024)) / elapsed
            self.last_time = current_time
            self.last_bytes = current_bytes
        
        return self.current_speed
    
    def reset(self):
        """重置跟踪器"""
        self.start_time = time.time()
        self.last_time = self.start_time
        self.last_bytes = 0
        self.current_speed = 0.0


def print_progress(current, total, prefix="", speed=0.0):
    """打印进度条（覆盖式）"""
    bar_length = 40
    
    if total == 0:
        percent = 100.0
    else:
        percent = (current / total) * 100
    
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    current_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    
    speed_str = "{0:.2f} MB/s".format(speed) if speed > 0 else "--- MB/s"
    
    # 构建进度条字符串（固定长度120字符）
    progress_str = '{0}[{1}] {2:.1f}% ({3:.2f} MB / {4:.2f} MB) {5}'.format(
        prefix, bar, percent, current_mb, total_mb, speed_str)
    
    # 使用 ANSI 转义序列：\r 回到行首，\033[0K 清除到行尾
    # 这是最可靠的终端覆盖方式
    output = '\r\033[0K' + progress_str
    sys.stdout.write(output)
    sys.stdout.flush()


# 全局连接状态
connection_lost = False
is_transferring = False  # 是否正在进行文件传输
heartbeat_thread = None
heartbeat_stop_event = None


def heartbeat_monitor(client_socket, frame_handler):
    """心跳监控线程"""
    global connection_lost, is_transferring
    heartbeat_interval = 3  # 心跳间隔（秒）- 缩短以更快检测断开
    timeout_count = 0
    max_timeouts = 2  # 最大超时次数 - 减少以更快触发重连
    
    while not heartbeat_stop_event.is_set():
        # 如果正在进行文件传输，跳过心跳检测
        if is_transferring:
            time.sleep(0.5)
            continue
            
        try:
            # 发送心跳包
            heartbeat_request = {"action": "heartbeat", "timestamp": int(time.time())}
            frame_handler.send_json_frame(client_socket, heartbeat_request)
            
            # 接收响应（设置较短超时）
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
            
        # 等待下一次心跳
        for _ in range(heartbeat_interval):
            if heartbeat_stop_event.is_set():
                break
            time.sleep(1)


def reconnect_with_backoff(config_manager, max_retries=5):
    """带退避策略的重连"""
    server_host = config_manager.get("server.host", "127.0.0.1")
    server_port = config_manager.get("server.port", 2983)
    
    backoff = 1  # 初始退避时间（秒）
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
            backoff = min(backoff * 2, 30)  # 指数退避，最大30秒
    
    print("重连失败，已达最大重试次数")
    return None


def upload_file(client_socket, frame_handler, client_handler):
    """上传文件到服务器"""
    global is_transferring
    
    display_name = get_input_with_server_check(client_socket, frame_handler, "请输入文件显示名称: ")
    if display_name is None:
        return None
    
    if not display_name.strip():
        print("文件显示名称不能为空")
        return True
    
    # 检查文件名长度（限制为120字符）
    max_length = get_max_filename_length()
    if not is_filename_length_valid(display_name, max_length):
        print("文件名过长，最大允许 {0} 个字符".format(max_length))
        print("当前文件名长度: {0} 个字符".format(len(display_name)))
        return True
    
    # 检查文件名是否安全（防止路径穿越攻击）
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
    
    tracker = ProgressTracker()
    
    def progress_callback(current, total):
        speed = tracker.update(current)
        print_progress(current, total, "上传中 ", speed)
    
    try:
        # 设置传输标志，暂停心跳检测
        is_transferring = True
        
        success = client_handler.upload_file_with_name(client_socket, frame_handler, filepath, display_name, progress_callback)
        print()
        if success:
            print("文件上传成功")
        else:
            print("文件上传失败")
        return success
    except Exception as e:
        print()
        print("上传文件时发生错误: {0}".format(e))
        return None
    finally:
        # 清除传输标志，恢复心跳检测
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
    
    tracker = ProgressTracker()
    
    def progress_callback(current, total):
        speed = tracker.update(current)
        print_progress(current, total, "下载中 ", speed)
    
    try:
        # 设置传输标志，暂停心跳检测
        is_transferring = True
        
        success = client_handler.download_file(client_socket, frame_handler, filename, progress_callback)
        print()
        if success:
            print("文件下载成功")
        else:
            print("文件下载失败")
        return success
    except Exception as e:
        print()
        print("下载文件时发生错误: {0}".format(e))
        return None
    finally:
        # 清除传输标志，恢复心跳检测
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
        result = None  # 初始化 result 变量
        while connected:
            # 检查连接状态
            if connection_lost:
                print("\n检测到连接断开，尝试重新连接...")
                client_socket.close()
                client_socket = reconnect_with_backoff(config_manager)
                
                if client_socket:
                    # 重置连接状态并重启心跳线程
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
        
        # 停止心跳线程
        if heartbeat_stop_event:
            heartbeat_stop_event.set()
        
        # 如果不是主动退出，询问是否重新配置
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
