#!/usr/bin/python
# -*- coding: UTF-8 -*-
"""
@author:yuzai
@file:main.py
@time:2022/09/17
"""
from typing import Type

from nonebot.internal.matcher import Matcher
from nonebot.log import logger

from .Qndxx import Qndxx, LaravelSessionException, ConfirmSessionException, DEBUG
from .userdata.userdb import get_all_tables
from .userdata.userdbExceptions import DbTableMissing

'''{
    'token': '2tsvx0n7ifDRjKvWY437KxSd2w1HqyomAOGFiAQc',
    'lesson_id': '139',
    '当前课程': '2022年第21期',
    '您的姓名': '郑皓中',
    '用户编号': '011613114',
    '所在单位': '江苏理工学院-国际教育学院'
}'''


def do_qndxx(laravel_session: str):
    qndxx = Qndxx(laravel_session)
    qndxx.login()
    return qndxx.confirm()


async def refresh(global_setting, gid, userDB, bot):
    """
    :param bot:
    :param userDB: 目标数据库的游标
    :param gid: 要发送消息的目标群号
    :param global_setting: 设置，用于判断白名单
    :return:{
        <班级>:[
            {
                'stu_id': k,
                'name_in_db': v['name'],
                'name_returned': r['您的姓名'],
                'old_token': v['token'],
                'new_token': '',
                'reason': <错误原因>
            },
            ...
        ],
        ...
    }
    """
    error_dict = {}
    success_num = 0
    failed_num = 0
    if global_setting['是否启用班级白名单']:
        class_name_list = global_setting['白名单班级名称列表']
    else:
        class_name_list = get_all_tables(userDB.dbCursor)

    for class_name in class_name_list:

        try:
            classUserTokens = userDB.get_token(class_name)
        except DbTableMissing as e:
            logger.warning(f'缺失表名:{e.missingTableName}')
            await bot.send_group_msg(group_id=gid, message=f'缺失表名:{e.missingTableName}')
            continue
        failed = []

        for k, v in classUserTokens.items():
            try:
                r = do_qndxx(v['token'])
                if r is not None:
                    if r['您的姓名'] == v['name']:
                        #
                        logger.info(f'{k},{v["name"]} 已学习!')
                        success_num += 1
                    else:
                        logger.info(f'学习人"{r["您的姓名"]}与数据库中不匹配!')
                        await bot.send_group_msg(group_id=gid, message=f'学习人"{r["您的姓名"]}与数据库中不匹配!')
                        failed.append({
                            'stu_id': k,
                            'name_in_db': v['name'],
                            'name_returned': r['您的姓名'],
                            'old_token': v['token'],
                            'new_token': '',
                            'reason': '服务端返回的姓名与数据库中的不匹配'
                        })
                        failed_num += 1
            except LaravelSessionException as e:
                if DEBUG:
                    logger.warning(f'异常:\n{e}')
                logger.warning(f'{k}, {v["name"]}, 学习失败,laravel_session错误,请检查token!')
                await bot.send_group_msg(group_id=gid,
                                         message=f'{k}, {v["name"]}, 学习失败,laravel_session错误,请检查token!')
                failed.append({
                    'stu_id': k,
                    'name_in_db': v['name'],
                    'name_returned': None,
                    'old_token': v['token'],
                    'new_token': '',
                    'reason': 'laravel_session错误'
                })
                failed_num += 1
                userDB.change_token_availability(class_name, k, False)
            except ConfirmSessionException as e:
                if DEBUG:
                    logger.warning(f'返回数据:, {e.result}, \n错误信息:, {e.errorMsg}')
                else:
                    logger.warning(f'{v["name"]} 青年大学习情况确认错误\n错误信息:{e.errorMsg}')
                    await bot.send_group_msg(group_id=gid,
                                             message=f'{v["name"]} 青年大学习情况确认错误\n错误信息:{e.errorMsg}')
                failed.append({
                    'stu_id': k,
                    'name_in_db': v['name'],
                    'name_returned': None,
                    'old_token': v['token'],
                    'new_token': '',
                    'reason': '青年大学习自动学习后,学习情况反馈错误'
                })
                failed_num += 1
        error_dict.update({
            class_name: failed.copy()
        })
    await bot.send_group_msg(group_id=gid, message=f'全部刷新完毕,成功:{success_num},失败:{failed_num}')
    return error_dict


async def test_user_token(matcher: Type[Matcher], name, session):
    try:
        r = do_qndxx(session)
        if r is not None:
            if r['您的姓名'] == name:
                #
                logger.info('通过!')
                await matcher.send('laravel_session测试通过')
                return True
            else:
                logger.warning(f'学习人" {r["您的姓名"]} 与提供的姓名 {name} 不匹配!')
                await matcher.send(f'学习人" {r["您的姓名"]} 与提供的姓名 {name} 不匹配!')
    except LaravelSessionException as e:
        if DEBUG:
            logger.exception('异常:\n', e)
            await matcher.send('异常:\n' + str(e))
        logger.warning(f'{name}, {session}, laravel_session错误!')
        await matcher.send(f'{name}, {session}, laravel_session错误!')
    except ConfirmSessionException as e:
        if DEBUG:
            logger.exception(f'返回数据:, {e.result}, \n错误信息:, {e.errorMsg}')
            await matcher.send(f'返回数据:, {e.result}, \n错误信息:, {e.errorMsg}')
        else:
            logger.exception(f'错误信息:{e.errorMsg}')
            await matcher.send(f'错误信息:{e.errorMsg}')
    return False

# if __name__ == '__main__':
#     # do_qndxx('Shy2iGrwwhDRje4lm4kEoa5iDPKfeiFWQaKrhMYh')
#     r = test_user_token('林嘉诚', 'Shy2iGrwwhDRje4lm4kEoa5iDPKfeiFWQaKrhMYh')
#     print(r)
