#!/usr/bin/python
# -*- coding: UTF-8 -*-
"""
@author:yuzai
@file:Qndxx.py
@time:2022/09/17
"""
import json
import re

import requests
from bs4 import BeautifulSoup

DEBUG = False


class Qndxx:
    def __init__(self, laravel_session):
        # 需要传入的laravel_session
        self.laravel_session = laravel_session
        # 请求头
        self.UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.18(0x18001234) NetType/WIFI Language/zh_CN"
        # 江苏省青年大学习接口
        self.loginurl = "https://service.jiangsugqt.org/youth/lesson"
        # 确认信息接口
        self.confirmurl = "https://service.jiangsugqt.org/youth/lesson/confirm"
        # 创建会话
        self.session = requests.session()  # 创建会话
        # 构建用户信息字典
        self.userinfo = {}

    def get_userinfo(self, userinfo):
        # print(userinfo)
        for i in userinfo:
            # print(i)
            # 解析课程姓名编号单位信息
            info_soup = BeautifulSoup(str(i), 'html.parser')
            # print(info_soup.text)
            item = info_soup.get_text()  # 用户信息
            # print(item[:4],item[5:])
            self.userinfo[item[:4]] = item[5:]
        # print(self.userinfo)

    def confirm(self):
        params = {
            "_token": self.userinfo.get('token'),
            "lesson_id": self.userinfo.get('lesson_id')
        }
        # print(params)
        confirm_res = self.session.post(url=self.confirmurl, params=params)
        res = json.loads(confirm_res.text)
        if DEBUG:
            print(f"返回结果:{res}")
        if res["status"] == 1 and res["message"] == "操作成功":
            if DEBUG:
                print("青年大学习已完成")
                print(f"您的信息:{self.userinfo}")
            return self.userinfo
        else:
            raise ConfirmSessionException(res)

    def login(self):
        # 参数
        params = {
            "s": "/youth/lesson",
            "form": "inglemessage",
            "isappinstalled": "0"
        }
        # 构造请求头
        headers = {
            'User-Agent': self.UA,
            'Cookie': "laravel_session=" + self.laravel_session  # 抓包获取
        }
        # 登录
        login_res = self.session.get(url=self.loginurl, headers=headers, params=params)

        if '抱歉，出错了' in login_res.text:
            if DEBUG:
                print("laravel_session错误")
            raise LaravelSessionException
        # 正则匹配token和lesson_id
        token = re.findall(r'var token ?= ?"(.*?)"', login_res.text)  # 获取js里的token
        lesson_id = re.findall(r"'lesson_id':(.*)", login_res.text)  # 获取js里的token

        self.userinfo['token'] = token[0]
        self.userinfo['lesson_id'] = lesson_id[0]
        # 解析信息确认页面
        login_soup = BeautifulSoup(login_res.text, 'html.parser')
        # print(soup.select(".confirm-user-info"))
        # 找到用户信息div 课程姓名编号单位
        userinfo = login_soup.select(".confirm-user-info p")
        # print(userinfo)
        self.get_userinfo(userinfo)


class LaravelSessionException(Exception): pass


class ConfirmSessionException(Exception):
    def __init__(self, result):
        self.result = result
        self.errorMsg = result['message']
        super.__init__(self.errorMsg)
