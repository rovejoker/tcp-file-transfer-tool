# -*- coding: utf-8 -*-
"""
TCP 文件传输工具 - 启动脚本

提供统一的启动入口，支持服务器端和客户端的启动。
"""

import os
import sys
import subprocess
import signal


def check_python_version():
    """检查 Python 版本是否符合要求"""
    print("=" * 60)
    print("        Python 版本检查")
    print("=" * 60)
    
    current_version = sys.version_info
    current_version_str = f"{current_version.major}.{current_version.minor}.{current_version.micro}"
    
    min_version = (3, 8, 0)
    min_version_str = f"{min_version[0]}.{min_version[1]}.{min_version[2]}"
    
    print(f"当前 Python 版本: {current_version_str}")
    print(f"最低要求版本: {min_version_str}")
    
    if current_version >= min_version:
        print("\n[OK] Python 版本检查通过")
        return True
    else:
        print(f"\n[ERROR] Python 版本过低！")
        print(f"   当前版本: {current_version_str}")
        print(f"   最低要求: {min_version_str}")
        print(f"   请升级 Python 到 {min_version_str} 或更高版本")
        return False


def check_file_integrity():
    """检查文件完整性"""
    print("=" * 60)
    print("        文件完整性检查")
    print("=" * 60)
    
    required_files = [
        "scripts/server.py",
        "scripts/client.py",
        "src/__init__.py",
        "src/common/config_manager.py",
        "src/common/config_ui.py",
        "src/common/exceptions.py",
        "src/protocol/xprotocol.py",
        "src/protocol/__init__.py",
        "src/network/socket_manager.py",
        "src/network/frame_handler.py",
        "src/network/__init__.py",
        "src/business/server_handler.py",
        "src/business/client_handler.py",
        "src/business/__init__.py",
        "src/utils/logger.py",
        "src/utils/file_utils.py",
        "src/utils/progress_bar.py",
        "src/utils/__init__.py",
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("\n[ERROR] 缺失的文件:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("\n[ERROR] 文件完整性检查失败，请检查文件是否完整")
        return False
    else:
        print(f"\n[OK] 所有 {len(required_files)} 个必要文件都已存在")
        print("[OK] 文件完整性检查通过")
        return True


def check_environment():
    """检查运行环境是否满足要求"""
    if not check_python_version():
        return False
    
    print()
    
    if not check_file_integrity():
        return False
    
    print("\n" + "=" * 60)
    print("[OK] 所有检查通过，可以正常运行")
    print("=" * 60)
    
    return True


def start_server():
    """启动服务器"""
    print("\n正在启动服务器...")
    print("=" * 60)
    try:
        subprocess.run([sys.executable, "scripts/server.py"], cwd=os.getcwd())
    except KeyboardInterrupt:
        print("\n正在停止服务器...")


def start_client():
    """启动客户端"""
    print("\n正在启动客户端...")
    print("=" * 60)
    try:
        subprocess.run([sys.executable, "scripts/client.py"], cwd=os.getcwd())
    except KeyboardInterrupt:
        print("\n正在退出客户端...")


def main():
    """主函数"""
    print("=" * 60)
    print("    TCP 文件传输工具 - 启动器")
    print("=" * 60)
    print()
    
    if not check_environment():
        input("\n按 Enter 键退出...")
        return
    
    while True:
        print("\n" + "=" * 60)
        print("请选择要启动的程序:")
        print("=" * 60)
        print("1. 启动服务器")
        print("2. 启动客户端")
        print("0. 退出")
        
        choice = input("\n请输入选择 (0-2): ").strip()
        
        if choice == '0':
            print("\n退出启动器...")
            break
        elif choice == '1':
            start_server()
            break
        elif choice == '2':
            start_client()
            break
        else:
            print("无效选择，请输入 0、1 或 2")


if __name__ == "__main__":
    main()
