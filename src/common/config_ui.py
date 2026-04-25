# -*- coding: utf-8 -*-
"""
统一配置UI模块

提供交互式配置修改功能，支持服务器和客户端配置。
"""

from typing import Dict, Any, Callable, Tuple


class ConfigUI:
    """统一配置UI管理器"""
    
    @staticmethod
    def edit_client_config(config_manager):
        """编辑客户端配置"""
        print("\n" + "=" * 60)
        print("                  客户端配置")
        print("=" * 60)
        
        while True:
            print("\n当前配置:")
            print("1. 服务器地址: {0}".format(config_manager.get("server.host")))
            print("2. 服务器端口: {0}".format(config_manager.get("server.port")))
            print("3. 下载目录: {0}".format(config_manager.get("client.download_dir")))
            print("4. 保存并返回")
            
            choice = input("\n请选择要修改的选项 (1-4): ").strip()
            
            if choice == '1':
                value = input("请输入服务器地址: ").strip()
                if value:
                    config_manager.set("server.host", value)
                    print("已更新服务器地址")
            elif choice == '2':
                try:
                    value = int(input("请输入服务器端口: ").strip())
                    if 1 <= value <= 65535:
                        config_manager.set("server.port", value)
                        print("已更新服务器端口")
                    else:
                        print("无效的端口号")
                except ValueError:
                    print("请输入有效的数字")
            elif choice == '3':
                value = input("请输入下载目录: ").strip()
                if value:
                    config_manager.set("client.download_dir", value)
                    print("已更新下载目录")
            elif choice == '4':
                if config_manager.save_config():
                    print("配置已保存")
                else:
                    print("保存失败")
                break
            else:
                print("无效选择，请输入 1-4")
    
    @staticmethod
    def edit_server_config(config_manager):
        """编辑服务器配置"""
        print("\n" + "=" * 60)
        print("                  服务器配置")
        print("=" * 60)
        
        while True:
            print("\n当前配置:")
            print("1. 监听端口: {0}".format(config_manager.get("server.port")))
            print("2. 资源目录: {0}".format(config_manager.get("server.resource_dir")))
            print("3. 最大文件大小(MB): {0}".format(config_manager.get("server.max_file_size_mb")))
            print("4. 保存并返回")
            
            choice = input("\n请选择要修改的选项 (1-4): ").strip()
            
            if choice == '1':
                try:
                    value = int(input("请输入监听端口: ").strip())
                    if 1 <= value <= 65535:
                        config_manager.set("server.port", value)
                        print("已更新监听端口")
                    else:
                        print("无效的端口号")
                except ValueError:
                    print("请输入有效的数字")
            elif choice == '2':
                value = input("请输入资源目录: ").strip()
                if value:
                    config_manager.set("server.resource_dir", value)
                    print("已更新资源目录")
            elif choice == '3':
                try:
                    value = int(input("请输入最大文件大小(MB): ").strip())
                    if 1 <= value <= 10240:
                        config_manager.set("server.max_file_size_mb", value)
                        print("已更新最大文件大小限制")
                    else:
                        print("无效的文件大小（范围: 1-10240 MB）")
                except ValueError:
                    print("请输入有效的数字")
            elif choice == '4':
                if config_manager.save_config():
                    print("配置已保存")
                else:
                    print("保存失败")
                break
            else:
                print("无效选择，请输入 1-4")
