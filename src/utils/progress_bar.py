# -*- coding: utf-8 -*-
"""
进度条工具模块

提供终端进度条显示功能。
"""

import sys
import time


class ProgressBar:
    """
    进度条类
    
    提供终端进度条显示功能，支持实时更新和格式化输出。
    """
    
    def __init__(self, total_size: int, bar_length: int = 50, show_percent: bool = True):
        """
        初始化进度条
        
        Args:
            total_size: 总大小（字节）
            bar_length: 进度条长度
            show_percent: 是否显示百分比
        """
        self.total_size = total_size
        self.bar_length = bar_length
        self.show_percent = show_percent
        self.start_time = time.time()
        self.last_update_time = self.start_time
    
    def update(self, current_size: int, min_update_interval: float = 0.1):
        """
        更新进度条（线程安全、支持速度和剩余时间显示）
        
        Args:
            current_size: 当前已处理大小（字节）
            min_update_interval: 最小更新间隔（秒）
        """
        current_time = time.time()
        
        if current_time - self.last_update_time < min_update_interval:
            return
        
        self.last_update_time = current_time
        
        if self.total_size == 0:
            percent = 0
        else:
            percent = (current_size / self.total_size) * 100
        
        elapsed_time = current_time - self.start_time
        if elapsed_time > 0 and current_size > 0:
            speed = current_size / elapsed_time
            remaining_size = self.total_size - current_size
            if speed > 0:
                remaining_time = remaining_size / speed
            else:
                remaining_time = 0
        else:
            speed = 0
            remaining_time = 0
        
        speed_str = self._format_size(speed) + '/s'
        
        remaining_time_str = self._format_time(remaining_time)
        
        filled_length = int(self.bar_length * percent // 100)
        bar = '█' * filled_length + '░' * (self.bar_length - filled_length)
        
        progress_str = "\r进度: [{0}] {1:.1f}% {2}/{3} | {4:>10} | 剩余: {5}".format(
            bar,
            percent,
            self._format_size(current_size),
            self._format_size(self.total_size),
            speed_str,
            remaining_time_str
        )
        
        sys.stdout.write(progress_str)
        sys.stdout.flush()
    
    def finish(self):
        """完成进度条显示"""
        self.update(self.total_size, min_update_interval=0)
        print()
    
    @staticmethod
    def _format_size(bytes_size: float) -> str:
        """格式化文件大小"""
        if bytes_size < 1024:
            return "{0:.0f} B".format(bytes_size)
        elif bytes_size < 1024 * 1024:
            return "{0:.2f} KB".format(bytes_size / 1024)
        elif bytes_size < 1024 * 1024 * 1024:
            return "{0:.2f} MB".format(bytes_size / (1024 * 1024))
        else:
            return "{0:.2f} GB".format(bytes_size / (1024 * 1024 * 1024))
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间"""
        if seconds < 60:
            return "{0:.1f}秒".format(seconds)
        elif seconds < 60 * 60:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return "{0}分{1}秒".format(minutes, secs)
        else:
            hours = int(seconds // (60 * 60))
            minutes = int((seconds % (60 * 60)) // 60)
            secs = int(seconds % 60)
            return "{0}时{1}分{2}秒".format(hours, minutes, secs)


def show_upload_progress(current_size: int, total_size: int):
    """显示上传进度（简单版本）"""
    if total_size == 0:
        return
    
    percent = (current_size / total_size) * 100
    bar_length = 40
    filled_length = int(bar_length * percent // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    sys.stdout.write("\r上传进度: [{0}] {1:.1f}% {2}/{3}".format(
        bar,
        percent,
        current_size,
        total_size
    ))
    sys.stdout.flush()
    
    if current_size >= total_size:
        print()


def show_download_progress(current_size: int, total_size: int):
    """显示下载进度（简单版本）"""
    if total_size == 0:
        return
    
    percent = (current_size / total_size) * 100
    bar_length = 40
    filled_length = int(bar_length * percent // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    sys.stdout.write("\r下载进度: [{0}] {1:.1f}% {2}/{3}".format(
        bar,
        percent,
        current_size,
        total_size
    ))
    sys.stdout.flush()
    
    if current_size >= total_size:
        print()
