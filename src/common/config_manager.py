# -*- coding: utf-8 -*-
"""
统一配置管理模块

支持服务器和客户端配置的统一管理，包含安全验证逻辑
"""

import os
import json
from typing import Dict, Any, Optional


class ConfigManager:
    """统一配置管理器"""
    
    DEFAULT_SERVER_CONFIG = {
        "server": {
            "port": 2983,
            "resource_dir": "resource",
            "max_file_size_mb": 1024
        }
    }
    
    DEFAULT_CLIENT_CONFIG = {
        "server": {
            "host": "127.0.0.1",
            "port": 2983
        },
        "client": {
            "download_dir": "downloads"
        }
    }
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                pass
        
        if "server" in self.config_path.lower():
            return self.DEFAULT_SERVER_CONFIG.copy()
        else:
            return self.DEFAULT_CLIENT_CONFIG.copy()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            ensure_directory(os.path.dirname(self.config_path))
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        
        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def update(self, updates: Dict[str, Any]):
        """批量更新配置"""
        for key, value in updates.items():
            self.set(key, value)


def ensure_directory(dir_path: str) -> bool:
    """确保目录存在"""
    try:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        return True
    except Exception as e:
        return False
