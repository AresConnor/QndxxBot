from typing import List

from nonebot.adapters.onebot.v11 import Bot, Message, GroupMessageEvent

api_key = "b9063313091ff86df306f7b24feceebfd9b61d62"
EnableRename = False
minsim = '80!'

# enable or disable indexes
index_hmags = '0'
index_reserved = '0'
index_hcg = '0'
index_ddbobjects = '0'
index_ddbsamples = '0'
index_pixiv = '1'
index_pixivhistorical = '1'
index_reserved = '0'
index_seigaillust = '1'
index_danbooru = '0'
index_drawr = '1'
index_nijie = '1'
index_yandere = '0'
index_animeop = '0'
index_reserved = '0'
index_shutterstock = '0'
index_fakku = '0'
index_hmisc = '0'
index_2dmarket = '0'
index_medibang = '0'
index_anime = '0'
index_hanime = '0'
index_movies = '0'
index_shows = '0'
index_gelbooru = '0'
index_konachan = '0'
index_sankaku = '0'
index_animepictures = '0'
index_e621 = '0'
index_idolcomplex = '0'
index_bcyillust = '0'
index_bcycosplay = '0'
index_portalgraphics = '0'
index_da = '1'
index_pawoo = '0'
index_madokami = '0'
index_mangadex = '0'

extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
thumbSize = (250, 250)

# generate appropriate bitmask
db_bitmask = int(
    index_mangadex + index_madokami + index_pawoo + index_da + index_portalgraphics + index_bcycosplay + index_bcyillust
    + index_idolcomplex + index_e621 + index_animepictures + index_sankaku + index_konachan + index_gelbooru
    + index_shows + index_movies + index_hanime + index_anime + index_medibang + index_2dmarket + index_hmisc
    + index_fakku + index_shutterstock + index_reserved + index_animeop + index_yandere + index_nijie + index_drawr
    + index_danbooru + index_seigaillust + index_anime + index_pixivhistorical + index_pixiv + index_ddbsamples
    + index_ddbobjects + index_hcg + index_hanime + index_hmags,
    2)


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
