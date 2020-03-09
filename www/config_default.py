#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
默认配置文件
"""

__author__ = 'labulaka6'


configs = {
    'db': {  # 定义数据库相关信息
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'web',
        'password': 'webdata',
        'database': 'webapp'
    },
    'session': {  # 定义会话cookies密钥
        'secret': 'AwEsOmE'
    }
}