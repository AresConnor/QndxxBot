import asyncio
import json
import os.path
import pathlib
import threading
from typing import Union
from PIL import Image, ImageDraw, ImageFont

import apscheduler.events
import nonebot
from apscheduler.events import *
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.job import Job
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from nonebot import on_command, Driver
from nonebot import require
from nonebot.adapters.onebot.v11 import Message, Bot, MessageSegment, GroupMessageEvent, Event
from nonebot.exception import NetworkError, ActionFailed
from nonebot.internal.matcher import Matcher, matchers
from nonebot.internal.params import Depends
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State

from . import JobEventLocker
from .main import test_user_token, refresh
from .qndxxHelperChecker import helper_checker_run
from .txt2im import txt2im
from .userdata.userdb import UserDB, get_all_tables
from .utils import *
from .xlsx import NullSqlWarning
from .xlsx.ErrorExcel import ErrorExcel
from .xlsx.UserDbExcel import UserDbExcel
from .xlsx.UnavailableEntryExcel import UnavailableEntryExcel

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

init_logger()
gid = gid_default

add_entry = on_command('add',
                       state={'help': '添加青年大学习自动学习条目:\n\t/add <班级> <姓名> <学号> <laravel session>'})
remove_entry = on_command('remove', state={'help': '删除青年大学习自动学习条目:\n\t/remove <学号>'})
manual_refresh = on_command('manual_refresh', state={'help': '手动执行青年大学习刷新:\n\t/manual_refresh'})
show_db_in_execl = on_command('database', state={'help': '显示数据库中所有的条目(转化为excel):\n\t/database'})
show_all_tables = on_command('classes', state={'help': '显示所有班级(青年大学习自动学习)'})
show_error_db_in_excel = on_command('unavailable',
                                    state={'help': '显示数据库中所有已失效的条目(转化为excel):\n\t/unavailable'})
update_laravel_session = on_command('update', state={
    'help': '更新某条目的laravel session:\n\t/update <学号> <新laravel session>'})
job_status = on_command('job_status', state={'help': '查看定时任务(自动刷新)的任务状态\n\t/job_status'})
echo_help = on_command('help', state={'help': '帮助'})
run_helper_checker = on_command('helper_check', state={'help': '导出每周青年大学习帮扶检查表\n\t/helper_check'})
_switch_group = on_command('sw', state={'help': '管理员:切换上传文件的群号/sw <序号>||this'})
# superuser
_sql = on_command('sql', state={'help': '管理员:执行sql指令'})
_change_db_data = on_command('change', state={'help': '管理员:更改数据库数据'})
_exec = on_command('exec', state={'help': ''}, permission=SUPERUSER)
_eval = on_command('eval', state={'help': ''}, permission=SUPERUSER)

EVENT_JOB_SUBMITTED_locker = JobEventLocker.JobEventLocker(lockedEvent='EVENT_JOB_SUBMITTED')
EVENT_JOB_EXECUTED_locker = JobEventLocker.JobEventLocker(lockedEvent='EVENT_JOB_EXECUTED')

bot: Bot
driver: Driver = nonebot.get_driver()
global_setting = {}
userDB: UserDB


async def is_admin(event: Event):
    return event.get_user_id() in admin_list


async def check_allow_issue_command(event: GroupMessageEvent):
    if is_admin(event):
        return True
    return event.group_id in gid_allowed


@add_entry.handle()
async def add_entry_func(matcher: Matcher, args: Message = CommandArg()):
    """

    :param matcher:
    :param args: 样例: add <班级> <姓名> <学号> <laravel session>
    :return:
    """
    await whenScheduledJobRunning(matcher)
    entry_info = args.extract_plain_text().split(' ')
    if len(entry_info) != 4:
        await add_entry.finish('输入的参数格式不正确')
    try:
        entry_class = entry_info[0]
        entry_name = entry_info[1]
        entry_stu_id = int(entry_info[2])
        entry_session = entry_info[3]
    except ValueError as e:
        await add_entry.finish(f'学号不是纯数字:{e.args[0]}')
        await add_entry.finish()
        # 防止ide误判
        return
    passed = await test_user_token(add_entry, entry_name, entry_session)
    if passed:
        r = await userDB.add_user(tableName=entry_class, name=entry_name, stu_id=entry_stu_id, token=entry_session,
                                  matcher=add_entry, setting=global_setting)
        if r:
            await add_entry.finish('添加成功')
        else:
            await add_entry.finish('数据库添加数据失败!,请检查数据类型或是否启用了班级白名单!')
    await add_entry.finish()


@remove_entry.handle()
async def _(matcher: Matcher, args: Message = CommandArg()):
    """
    :param args: 样例:/remove <学号>
    :return:
    """
    try:
        stuid = int(args.extract_plain_text())
    except KeyError:
        stuid = None
        await remove_entry.finish(f'请输入正确格式的学号!')
    await whenScheduledJobRunning(matcher)
    r = await userDB.remove_user(stu_id=stuid, matcher=remove_entry)
    await remove_entry.finish()


@manual_refresh.handle()
async def _(event: GroupMessageEvent):
    retval = await refresh(global_setting=global_setting, gid=event.group_id, userDB=userDB, bot=bot)
    await dump_error_xlsx(retval=retval)
    await manual_refresh.finish()


@show_db_in_execl.handle()
async def _(event: GroupMessageEvent, matcher: Matcher):
    userDbExcel = UserDbExcel(userDB.dbCursor)
    await userDbExcelBased_handler(userDbExcel, event.group_id, matcher)
    await show_db_in_execl.finish()


@show_all_tables.handle()
async def _():
    await show_all_tables.finish(get_all_tables(userDB.dbCursor))


@show_error_db_in_excel.handle()
async def _(event: GroupMessageEvent, matcher: Matcher):
    unavailableEntryExcel = UnavailableEntryExcel(userDB.dbCursor)
    await userDbExcelBased_handler(unavailableEntryExcel, event.group_id, matcher)
    await show_error_db_in_excel.finish()


@update_laravel_session.handle()
async def _(args: Message = CommandArg()):
    """

    :param args: 样例:/update <学号> <new_laravel_session>
    :return:
    """
    arg = args.extract_plain_text().split(' ')
    if len(arg) != 2:
        await update_laravel_session.finish('输入格式不正确')
    try:
        stu_id, new_token = arg[0], arg[1]
    except KeyError:
        await update_laravel_session.finish('输入的学号格式不正确')
        return
    rlt = userDB.search_by_id('NAME', stu_id)
    if rlt is None:
        await update_laravel_session.finish('该条目不存在')
    if await test_user_token(update_laravel_session, rlt[0], new_token):
        userDB.update_user_token(rlt[1], stu_id, new_token)
        await update_laravel_session.send('更改成功')
    await update_laravel_session.finish()


@job_status.handle()
async def _():
    j: Job = scheduler.get_job(job_id=auto_fresh_job_name)
    await job_status.finish(f'名称:{j.id}\n'
                            f'目标函数:{j.func.__name__}\n'
                            f'定时任务触发器:{j.trigger}\n'
                            f'定时任务执行器:{j.executor}\n'
                            f'下次执行时间:{j.next_run_time}')


# async def get_group_list():
#     return await bot.get_group_list()
#

# class group:
#     def __init__(self, event: Event, group_list=Depends(get_group_list)):
#         # 获取群列表
#         self.group_message = False
#         self.event = event
#         self.group_list = group_list
#
#         self.group_dict = {self.group_list.index(d): {"群号": d['group_id'], "群名": d['group_name']} for d in
#                            self.group_list}
#         if isinstance(event, GroupMessageEvent):
#             self.group_message = True
#             event: GroupMessageEvent
#             self.group_dict.update({
#                 "this": {
#                     "群号": event.group_id,
#                     "群名": (await bot.get_group_info(group_id=event.group_id))['group_name']
#                 }
#             })
#
#     def __call__(self, *args, **kwargs):
#         # 构造参数
#         text = '请按照序号选择要切换到的群:\n'
#         for k, v in self.group_dict.items():
#             if self.group_message:
#                 self.event: GroupMessageEvent
#                 if v["群号"] == self.event.group_id:
#                     f' >> *{k}:{self.group_dict["群名"]}\n'
#                     continue
#             text += f'    *{k}:{self.group_dict["群名"]}\n'
#         text += f'\n是否为当前群:{self.event.group_id == gid}'
#         self.text = text
#         return text


@_switch_group.handle()
async def _(state: T_State, event: Event, arg: Message = CommandArg(),
            _admin: bool = Depends(is_admin)):
    global gid
    if not _admin:
        await _sql.finish('无权限!')
    arg = arg.extract_plain_text()

    text = '请按照序号选择要切换到的群:\n'
    # 获取群列表
    group_list = await bot.get_group_list()
    group_dict = {str(group_list.index(d) + 1): {"群号": d['group_id'], "群名": d['group_name']} for d in
                  group_list}
    group_msg = isinstance(event, GroupMessageEvent)
    if group_msg:
        event: GroupMessageEvent
        group_dict.update({
            "this": {
                "群号": event.group_id,
                "群名": (await bot.get_group_info(group_id=event.group_id))['group_name']
            }
        })
    state.update({
        'group_dict': group_dict
    })

    if arg != '':
        if arg in {k for k in state['group_dict'].keys()}:
            old_gid = gid
            gid = state['group_dict'][arg]["群号"]
            # 重载定时任务
            await _switch_group.send('正在重载定时任务...')
            scheduler.remove_all_jobs()
            logger.info('删除全部定时任务')
            await on_bot_connect_handler()
            await _switch_group.send('已重载全部定时任务')
            await _switch_group.finish(f"设置到'{state['group_dict'][arg]['群名']}'成功!")

    for k, v in group_dict.items():
        if k == 'this':
            continue
        if group_msg:
            event: GroupMessageEvent
            if v["群号"] == gid:
                text += f'> *{k}:{v["群名"]}\n'
                continue
        text += f'\t*{k}:{v["群名"]}\n'
    text += f'\n是否为当前群:{event.group_id == gid}'
    text_img_fn = DATA_DIR + 'sw_help.png'
    txt2im(txt=text, outfn=text_img_fn)
    await _switch_group.finish(MessageSegment.image(file=pathlib.Path(os.path.abspath(text_img_fn)).as_uri()))


@_sql.handle()
async def _(sql: Message = CommandArg(), _admin: bool = Depends(is_admin)):
    if not _admin:
        await _sql.finish('无权限!')
    sql_ = sql.extract_plain_text().strip()
    sql_ = sql_ + (';' if not sql_.endswith(';') else '')
    try:
        await _sql.send(str(userDB.dbCursor.execute(sql_).fetchall()))
    except Exception as e:
        await _sql.send(f'{e}')
    await _sql.finish()


@_change_db_data.handle()
async def _(arg: Message = CommandArg(), _admin: bool = Depends(is_admin)):
    if not _admin:
        await _sql.finish('无权限!')
    args = arg.extract_plain_text().split(' ')
    try:
        column, stuid, newValue = args
    except Exception as e:
        await _change_db_data.finish(f'{e}')
        return
    if column in userDB.column.values() and column != userDB.primary_key:
        try:
            formatted_value = userDB.column[column](newValue)
            stuid = int(stuid)
        except KeyError as e:
            await _change_db_data.finish(f'{e}')
            return
        if not userDB.set_value(column, stuid, formatted_value):
            if userDB.exception is None:
                await _change_db_data.finish(f'学号:{stuid}的条目不存在')
            else:
                await _change_db_data.finish(f'设置新值时发生错误:\n{userDB.exception}')
    else:
        await _change_db_data.finish(f'{column}不在表头中,或为primary key')
    await _change_db_data.finish('设置成功')


@_exec.handle()
async def _exec_func(arg: Message = CommandArg()):
    arg = arg.extract_plain_text()
    try:
        exec(arg)
    except Exception as e:
        logger.exception(e)
        txt2im(txt='错误\n' + e.__str__(), outfn='exception.png')
        await _exec.finish(MessageSegment.image(file=pathlib.Path(os.path.abspath('exception.png')).as_uri()))


@_eval.handle()
async def _exec_func(arg: Message = CommandArg()):
    arg = arg.extract_plain_text()
    try:
        r = eval(arg)
        await _eval.send(str(r))
    except Exception as e:
        logger.exception(e)
        txt2im(txt='Exception\n' + e.__str__(), outfn='exception.png')
        await _eval.send(MessageSegment.image(file=pathlib.Path(os.path.abspath('exception.png')).as_uri()))


@run_helper_checker.handle()
async def _():
    rlt = helper_checker_run()
    await helper_checker_run_target(rlt)


@echo_help.handle()
async def _(this_matcher: Matcher, arg: Message = CommandArg()):
    arg = arg.extract_plain_text()
    if arg == "detailed":
        # ======================生成文本======================
        i = 0
        help_text = '帮助:\n'
        help_text += '===================================\n'
        priority_list = [p for p in matchers.keys()]
        priority_list.sort()

        for priority in priority_list:
            for matcher in matchers[priority]:
                if matcher.module_name != this_matcher.module_name:
                    continue
                for matcher_dependent in matcher.rule.checkers:
                    i += 1
                    matcher_dependent_call = matcher_dependent.call

                    try:
                        help_text += f'{i}:{getattr(matcher, "_default_state")["help"]}\n\n'
                    except KeyError:
                        help_text += f'{i}:\n'
                    help_text += f'\t类型:{type(matcher_dependent_call)}:\n\t优先级:{priority}\n\t属性:\n'
                    if hasattr(matcher_dependent_call, "__slots__"):
                        for slot in matcher_dependent_call.__slots__:
                            attr = getattr(matcher_dependent_call, slot)
                            help_text += f'\t\t{slot}:{attr}\n'
                    help_text += '===================================\n'
        # ======================生成文本======================
        # ======================生成图片======================
        txt2im(help_text, DATA_DIR + HELP_IMAGE_FN)
        # ======================生成图片======================
        await echo_help.finish(MessageSegment.image(pathlib.Path(os.path.abspath(DATA_DIR + HELP_IMAGE_FN)).as_uri()))

    msg = f"""
        ================国教院团务bot================

            指令:
                1.添加青年大学习自动学习条目:
                    /add <班级> <姓名> <学号> <laravel session>

                2.删除青年大学习自动学习条目:
                    /remove <学号>

                3.显示数据库中所有的条目(转化为excel):
                    /database
                    
                4.显示数据库中所有已失效的条目(转化为excel):
                    /unavailable

                5.更新某条目的laravel session:
                    /update <学号> <新laravel session>

                6.手动执行青年大学习刷新:
                    /manual_refresh

                7.查看定时任务(自动刷新)的任务状态
                    /job_status
                    
                8.导出每周青年大学习帮扶检查表
                    /helper_check
                    
                9.显示帮助
                    /help

        ===========================================
        """
    im = Image.new('RGBA', (1400, 1400), 'white')
    draw = ImageDraw.Draw(im)
    draw.text((75, 50),
              msg,
              fill='black',
              font=ImageFont.truetype(font=os.path.join(os.path.split(os.path.relpath(__file__))[0], 'fonts/Deng.ttf'),
                                      size=40
                                      )
              )
    with open(DATA_DIR + HELP_IMAGE_FN, 'wb') as f:
        im.save(f, format=HELP_IMAGE_FN[HELP_IMAGE_FN.index('.') + 1:])
    await echo_help.finish(MessageSegment.image(file=pathlib.Path(os.path.abspath(DATA_DIR + HELP_IMAGE_FN)).as_uri()))


@driver.on_startup
async def on_startup_handler():
    global global_setting
    global userDB

    # ====================加载配置文件====================
    if os.path.exists(os.path.join(DATA_DIR, CONFIG_FN)):
        with open(os.path.join(DATA_DIR, CONFIG_FN), 'r', encoding='utf-8') as f:
            global_setting = json.load(f)
        logger.info('正在检查配置文件')
        missing_key = set(DEFAULT_CONFIG.keys()) - set(global_setting.keys())
        if missing_key == set():
            logger.success('配置文件加载成功')
        else:
            for key in missing_key:
                global_setting.update({
                    key: DEFAULT_CONFIG[key]
                })
            logger.warning(f'配置文件缺失key:{missing_key},已追加默认值')
            save_config()
    else:
        # 生成配置文件
        logger.info('未检测到配置文件,生成默认配置文件')
        global_setting = DEFAULT_CONFIG.copy()
        save_config()
    # ====================加载配置文件====================

    # ====================初始化数据库====================
    userDB = UserDB()
    # ====================初始化数据库====================


@driver.on_bot_connect
async def on_bot_connect_handler():
    global EVENT_JOB_SUBMITTED_locker
    global EVENT_JOB_EXECUTED_locker
    global bot
    bot = nonebot.get_bot()
    # ====================启动定时任务====================
    await auto_fresh(on_submitted_callback=on_job_submitted_handler, on_executed_callback=on_job_executed_handler)
    await auto_check_helper()
    for job in scheduler.get_jobs():
        logger.info(f'定时任务:{job.id} 已启动')
    # ====================启动定时任务====================


# 定时刷新任务
async def auto_fresh(on_executed_callback=None, on_submitted_callback=None):
    trigger = CronTrigger(
        hour=12,
        day_of_week='mon,wed,sat',
        jitter=3600,
        timezone="Asia/Shanghai"
    )
    scheduler.add_job(
        func=refresh,
        trigger=trigger,
        args=(global_setting, gid, userDB, bot,),
        id=auto_fresh_job_name,
        misfire_grace_time=30,
        max_instances=1,
        default=ThreadPoolExecutor(64),
        processpool=ProcessPoolExecutor(8),
        coalesce=True,
        replace_existing=True
    )
    scheduler.add_listener(on_submitted_callback, EVENT_JOB_SUBMITTED)
    scheduler.add_listener(on_executed_callback, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    logger.info(f'定时任务:{auto_fresh_job_name} 已添加')


# 定时检查
async def auto_check_helper():
    trigger = CronTrigger(
        hour=20,
        day_of_week='sun',
        jitter=10,
        timezone="Asia/Shanghai"
    )
    # trigger = IntervalTrigger(minutes=1)
    scheduler.add_job(
        func=helper_checker_run,
        trigger=trigger,
        args=(),
        id=helper_checker_job_name,
        misfire_grace_time=30,
        max_instances=1,
        default=ThreadPoolExecutor(64),
        processpool=ProcessPoolExecutor(8),
        coalesce=True,
        replace_existing=True)
    logger.info(f'定时任务:{helper_checker_job_name} 已添加')


def on_job_executed_handler(event: apscheduler.events.JobExecutionEvent):
    global EVENT_JOB_EXECUTED_locker
    if EVENT_JOB_EXECUTED_locker.Locked:
        logger.info(f'{EVENT_JOB_EXECUTED_locker.LockedEvent}:回调锁已打开,回调失败')
        return
    EVENT_JOB_EXECUTED_locker.Locked = True
    if event.job_id == auto_fresh_job_name:
        # def run(retval, exception):
        #     asyncio.run(dump_error_xlsx(retval=retval, exception=exception))

        thread = threading.Thread(
            target=lambda retval, exception: asyncio.run(dump_error_xlsx(retval=retval, exception=exception)),
            args=(event.retval, event.exception,))
        thread.start()
        thread.join(timeout=3)
        EVENT_JOB_EXECUTED_locker.Locked = False
    if event.job_id == helper_checker_job_name:
        rlt = helper_checker_run()
        thread = threading.Thread(target=lambda _rlt: asyncio.run(helper_checker_run_target(_rlt)), args=(rlt,))
        thread.start()
        thread.join(timeout=3)
        EVENT_JOB_EXECUTED_locker.Locked = False


async def helper_checker_run_target(r: Union[str, BaseException]):
    global gid
    if isinstance(r, BaseException):
        await bot.send_group_msg(group_id=gid, message=str(r))
        await bot.send_group_msg(group_id=gid, message=f'生成失败')
    else:
        try:
            await bot.call_api('upload_group_file',
                               group_id=gid,
                               file=os.path.abspath(DATA_DIR + r),
                               name=r)
        except NetworkError:
            logger.warning(f'网络错误,上传<{r}>失败')
            await bot.send_group_msg(group_id=gid, message=f'网络错误,上传<{r}>失败')
        except ActionFailed as e:
            await bot.send_group_msg(group_id=gid,
                                     message=f'调用群文件上传api失败,上传<{r}>失败,{e}')


async def dump_error_xlsx(retval, exception=None):
    global gid
    if not exception:
        error_num = 0
        for v in retval.values():
            error_num += len(v)
        if error_num != 0:
            errorXlsx = ErrorExcel(retval)
            if errorXlsx.dump_excel(os.path.join(DATA_DIR, ERROR_XLSX_FN)):
                try:
                    await bot.call_api('upload_group_file',
                                       group_id=gid,
                                       file=os.path.abspath(DATA_DIR + ERROR_XLSX_FN),
                                       name=ERROR_XLSX_FN)
                except NetworkError:
                    logger.warning(f'网络错误,上传<{ERROR_XLSX_FN}>失败')
                    await bot.send_group_msg(group_id=gid, message=f'网络错误,上传<{ERROR_XLSX_FN}>失败')
                except ActionFailed as e:
                    await bot.send_group_msg(group_id=gid,
                                             message=f'调用群文件上传api失败,上传<{ERROR_XLSX_FN}>失败,{e}')
            else:
                await bot.send_group_msg(group_id=gid,
                                         message=f'生成<{ERROR_XLSX_FN}>失败\n错误跟踪:\n{errorXlsx.exception}')


def on_job_submitted_handler(event: JobSubmissionEvent):
    if EVENT_JOB_SUBMITTED_locker.Locked:
        logger.warning(f'{EVENT_JOB_SUBMITTED_locker.LockedEvent}:回调失败,回调锁未解锁')
        return
    EVENT_JOB_SUBMITTED_locker.Locked = True
    global gid

    async def inner_func():
        global gid
        msg = ''
        for _time in event.scheduled_run_times:
            msg += '\n' + str(_time)
        await bot.send_group_msg(group_id=gid,
                                 message=f'定时任务:{event.job_id} 开始运行' + f'\n\n计划运行时间:{msg}')

    def run():
        asyncio.run(inner_func())

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=3)
    EVENT_JOB_SUBMITTED_locker.Locked = False


def save_config():
    with open(os.path.join(DATA_DIR, CONFIG_FN), 'w', encoding='utf-8') as f:
        json.dump(global_setting, f, ensure_ascii=False, indent=4, sort_keys=True)


async def whenScheduledJobRunning(matcher: Matcher):
    if userDB.refreshing:
        await matcher.finish(f'操作失败:数据库被定时任务:{auto_fresh_job_name}锁定')


async def userDbExcelBased_handler(userDbExcel, group_id, matcher: Matcher):
    if isinstance(userDbExcel, UnavailableEntryExcel):
        fn = UNAVAILABLE_IN_DB_EXCEL_FN
    else:
        fn = USER_DB_EXCEL_FN
    if userDbExcel.dump_excel(DATA_DIR + fn):
        try:
            logger.info(f'正在发送群文件{fn}...')
            await bot.call_api('upload_group_file',
                               group_id=group_id,
                               file=os.path.abspath(DATA_DIR + fn),
                               name=fn)
            logger.success(f'{fn}发送成功!')
        except NetworkError:
            logger.warning(f'网络错误,上传<{fn}>失败')
            await matcher.send(f'网络错误,上传<{fn}>失败')
        except ActionFailed as e:
            await matcher.send(
                f'调用群文件上传api失败,上传<{fn}>失败,f{e}')
            logger.warning(f'api调用失败,{fn}发送失败')

    elif isinstance(userDbExcel.exception, NullSqlWarning):
        if isinstance(userDbExcel, UnavailableEntryExcel):
            await matcher.send('没有失效的条目')
        else:
            await matcher.send('数据库为空!')
    else:
        await matcher.send(f'写入excel文件失败:\n错误跟踪:\n{userDbExcel.exception}')
