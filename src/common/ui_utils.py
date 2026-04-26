# -*- coding: utf-8 -*-
"""
UI工具模块

提供跨平台的用户输入处理功能，支持中文输入和连接状态检测。
"""

import sys
import time
import select
import socket

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


def _get_windows_input_non_blocking(hConsoleInput):
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


def get_input_with_connection_check(prompt, client_socket=None, connection_lost_flag=None):
    """
    获取用户输入并检查连接状态
    
    Args:
        prompt: 提示信息
        client_socket: 客户端socket（可选）
        connection_lost_flag: 连接丢失标志（可选，用于Windows输入循环检查）
    
    Returns:
        str: 用户输入内容，连接断开时返回None
    """
    if sys.platform == 'win32':
        return _windows_input_with_check(prompt, client_socket, connection_lost_flag)
    else:
        return _unix_input_with_check(prompt, client_socket)


def _windows_input_with_check(prompt, client_socket, connection_lost_flag):
    """Windows平台：带连接检查的输入"""
    import ctypes

    
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    STD_INPUT_HANDLE = -10
    hConsoleInput = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    
    if hConsoleInput == 0:
        return input(prompt)
    
    buffer = []
    print(prompt, end='', flush=True)
    
    while True:
        # 检查连接丢失标志
        if connection_lost_flag and connection_lost_flag():
            print('\n心跳检测到连接已断开')
            return None
        
        # 检查socket状态
        if client_socket:
            try:
                error_code = client_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if error_code != 0:
                    print('\n检测到socket错误，连接已断开')
                    return None
            except Exception:
                print('\n检查连接状态失败')
                return None
        
        char = _get_windows_input_non_blocking(hConsoleInput)
        
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


def _unix_input_with_check(prompt, client_socket):
    """Unix平台：带连接检查的输入"""
    print(prompt, end='', flush=True)
    buffer = []
    
    while True:
        # 检查socket连接状态
        if client_socket:
            if not _is_socket_connected(client_socket):
                print('\n检测到与服务器的连接已断开')
                return None
        
        read_list, _, _ = select.select([sys.stdin], [], [], 0.1)
        if read_list:
            line = sys.stdin.readline()
            return line.strip()
        
        time.sleep(0.05)


def _is_socket_connected(client_socket):
    """检查socket连接是否仍然有效"""
    try:
        error_code = client_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        return error_code == 0
    except Exception:
        return False