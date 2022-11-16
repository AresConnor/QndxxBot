import asyncio
import datetime
import os.path
import pathlib
import random

from nonebot import on_keyword, on_command, on_request, on_startswith, on_regex
from nonebot.adapters.onebot.v11 import Event, MessageSegment
from nonebot.internal.matcher import matchers, Matcher

from .txt2im import txt2im
from .utils import _check

HELP_IM_FN = 'help.png'

zhiyin = on_keyword(keywords={'鸡', '只因', 'ikun', '两年半'}, priority=2, state={'help': '只因你太美~'})
jrrp = on_command(cmd='jrrp', state={'help': '今日人品,满分100分,越高越好~'})
group_request = on_request(rule=_check, state={
    'help': '加群自动审批,来源:https://github.com/MRSlouzk/Nonebot-plugintutorials/blob/main/%E5%85%B7%E4%BD%93%E6%A1%88%E4%BE%8B/requestapp.md'})
print_help = on_command(cmd='HELP', state={'help': '帮助~'})
print_6 = on_startswith(msg='6', priority=2, state={'help': '发送1个6'})
print_multi_6 = on_regex(pattern="\d个+", block=True, state={'help': '发送多个_(复读机行为)'})


@zhiyin.handle()
async def _():
    await zhiyin.finish('你干嘛~哈哈,哎哟~~~')


@jrrp.handle()
async def _(event: Event):
    date = datetime.date.today()
    uid = event.get_user_id()

    rand = random.Random()
    rand.seed(str(date) + uid)

    await jrrp.finish(f'今天的人品值是{rand.randint(0, 100)}哟~', at_sender=True)


@print_6.handle()
async def _():
    await print_6.finish('6')


@print_multi_6.handle()
async def _(event: Event):
    N = 3
    msg = event.get_message().extract_plain_text()
    try:
        n = int(msg[:msg.index('个')])
    except ValueError:
        await print_multi_6.finish()
        return
    if n > N:
        await print_multi_6.finish(f'最大只支持{N}以内的复读哟~')
    _str = msg[msg.index('个') + 1:]
    await asyncio.wait([asyncio.create_task(print_multi_6.send(_str)) for i in range(n)])


@print_help.handle()
async def print_help_func(this_matcher: Matcher):
    # ======================生成文本======================
    i = 0
    help_text = '帮助:\n'

    priority_list = [p for p in matchers.keys()]
    priority_list.sort()

    for priority in priority_list:
        for matcher in matchers[priority]:
            if matcher.module_name != this_matcher.module_name:
                continue
            for matcher_dependent in matcher.rule.checkers:
                i += 1
                matcher_dependent_call = matcher_dependent.call
                help_text += f'{i}:{type(matcher_dependent_call)}:\n\tpriority:{priority}\n'
                try:
                    help_text += f'\t{getattr(matcher, "_default_state")["help"]}\n'
                except KeyError:
                    continue
                if hasattr(matcher_dependent_call, "__slots__"):
                    for slot in matcher_dependent_call.__slots__:
                        attr = getattr(matcher_dependent_call, slot)
                        help_text += f'\t\t{slot}:{attr}\n'
    # ======================生成文本======================
    # ======================生成图片======================
    txt2im(help_text, HELP_IM_FN)
    # ======================生成图片======================
    await print_help.finish(MessageSegment.image(pathlib.Path(os.path.abspath(HELP_IM_FN)).as_uri()))
