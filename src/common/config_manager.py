# -*- coding: utf-8 -*-
"""
统一配置管理模块

支持服务器和客户端配置的统一管理，包含安全验证逻辑。
配置文件采用 JSON 格式存储，支持默认配置和自定义配置。
"""

import os
import json
from typing import Dict, Any, Optional

from ..utils.file_utils import ensure_directory


class ConfigManager:
    """统一配置管理器"""
    
    # 服务器默认配置
    DEFAULT_SERVER_CONFIG = {
        "server": {
            "port": 2983,
            "resource_dir": "resource",
            "max_file_size_mb": 1024
        }
    }
    
    # 客户端默认配置
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
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        如果配置文件不存在或解析失败，返回默认配置。
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # 根据配置文件路径判断使用哪种默认配置
        if "server" in self.config_path.lower():
            return self.DEFAULT_SERVER_CONFIG.copy()
        else:
            return self.DEFAULT_CLIENT_CONFIG.copy()
    
    def save_config(self) -> bool:
        """
        保存配置到文件
        
        Returns:
            bool: 是否保存成功
        """
        try:
            ensure_directory(os.path.dirname(self.config_path))
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点分隔的嵌套键）
        
        Args:
            key: 配置键，支持嵌套如 "server.port"
            default: 默认值
        
        Returns:
            Any: 配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        设置配置值（支持点分隔的嵌套键）
        
        Args:
            key: 配置键，支持嵌套如 "server.port"
            value: 配置值
        """
        keys = key.split('.')
        config = self.config
        
        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def update(self, updates: Dict[str, Any]):
        """
        批量更新配置
        
        Args:
            updates: 配置更新字典
        """
        for key, value in updates.items():
            self.set(key, value)