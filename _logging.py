# -*- coding: utf-8 -*-
"""项目统一日志配置模块。

该模块为 neogenesis_inner 项目提供统一的日志配置，
确保所有子模块都能正确导入和使用 logger。
"""

import logging
import sys
from typing import Optional

# 配置根logger的基本设置
def setup_logging(level: int = logging.INFO, 
                 format_string: Optional[str] = None) -> logging.Logger:
    """设置项目的日志配置。
    
    Args:
        level: 日志级别，默认为 INFO
        format_string: 自定义日志格式，如果为 None 则使用默认格式
        
    Returns:
        配置好的 logger 实例
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 创建项目专用logger
    project_logger = logging.getLogger('neogenesis_inner')
    
    # 避免重复添加handler
    if not project_logger.handlers:
        project_logger.setLevel(level)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        # 创建格式器
        formatter = logging.Formatter(format_string)
        console_handler.setFormatter(formatter)
        
        # 添加处理器到logger
        project_logger.addHandler(console_handler)
        
        # 防止日志消息传播到根logger（避免重复输出）
        project_logger.propagate = False
    
    return project_logger

# 创建默认的logger实例，供其他模块导入使用
logger = setup_logging()

# 为了向后兼容，也提供一些常用的日志级别函数
def set_log_level(level: int) -> None:
    """设置日志级别。
    
    Args:
        level: 日志级别 (logging.DEBUG, logging.INFO, etc.)
    """
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

def debug(msg: str, *args, **kwargs) -> None:
    """记录 DEBUG 级别日志。"""
    logger.debug(msg, *args, **kwargs)

def info(msg: str, *args, **kwargs) -> None:
    """记录 INFO 级别日志。"""
    logger.info(msg, *args, **kwargs)

def warning(msg: str, *args, **kwargs) -> None:
    """记录 WARNING 级别日志。"""
    logger.warning(msg, *args, **kwargs)

def error(msg: str, *args, **kwargs) -> None:
    """记录 ERROR 级别日志。"""
    logger.error(msg, *args, **kwargs)

def critical(msg: str, *args, **kwargs) -> None:
    """记录 CRITICAL 级别日志。"""
    logger.critical(msg, *args, **kwargs)
