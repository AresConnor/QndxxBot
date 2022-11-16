import json
from typing import List

from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, Bot
from nonebot.internal.params import Arg, Depends
from nonebot.typing import T_State

friend_say = on_command('朋友说')


async def admin(event: GroupMessageEvent):
    su = [2837434884]
    return int(event.user_id) in su


@friend_say.got(key='friendSay', prompt='说什么')
async def _(state: T_State, gotArg: Message = Arg('friendSay'), _admin=Depends(admin)):
    if not _admin:
        await friend_say.finish()
    logger.info(gotArg)
    if 'say' not in {key for key in state.keys()}:
        state['say'] = []
    state['say'].append(gotArg.extract_plain_text())
    await friend_say.send('已录入')
    await friend_say.pause()


@friend_say.handle()
async def _(event: GroupMessageEvent, state: T_State, bot: Bot, _admin=Depends(admin)):
    if not _admin:
        await friend_say.finish()
    msg_dict = json.loads(event.json())
    msgs = msg_dict['message']
    at_uid = [msg for msg in msgs if msg['type'] == 'at'][0]['data']['qq']
    member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=at_uid)
    at_name = member_info['nickname']
    await send_forward_msg(
        bot,
        event,
        at_name,
        at_uid,
        [Message(m) for m in state['say']]
    )


async def send_forward_msg(
        bot: Bot,
        event: GroupMessageEvent,
        name: str,
        uin: str,
        msgs: List[Message],
):
    """
    :说明: `send_forward_msg`
    > 发送合并转发消息
    :参数:
      * `bot: Bot`: bot 实例
      * `event: GroupMessageEvent`: 群聊事件
      * `name: str`: 名字
      * `uin: str`: qq号
      * `msgs: List[Message]`: 消息列表
    """

    def to_json(msg: Message):
        return {"type": "node", "data": {"name": name, "uin": uin, "content": msg}}

    messages = [to_json(msg) for msg in msgs]
    await bot.call_api(
        "send_group_forward_msg", group_id=event.group_id, messages=messages
    )
