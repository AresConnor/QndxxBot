import io
import json
import os
import re
import time
import traceback
from collections import OrderedDict

from aiohttp.client_exceptions import ClientError
import requests
from PIL import Image
from .utils import *

from nonebot.exception import ActionFailed
from nonebot import on_command
from nonebot.params import Arg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message, MessageSegment, GroupMessageEvent

ReverseSearchImage = on_command('以图搜图')


@ReverseSearchImage.got("ReverseSearchImage", prompt="图捏？")
async def reverseSearchImage(bot: Bot,
                             event: MessageEvent,
                             msg: Message = Arg("ReverseSearchImage")):
    try:
        if msg[0].type == "image":

            url = msg[0].data["url"]
            im = Image.open(io.BytesIO(requests.get(url).content)).convert('RGB')
            im.thumbnail(thumbSize, resample=Image.ANTIALIAS)
            ImageToSearchData = io.BytesIO()
            im.save(ImageToSearchData, format='PNG')
            ImageBytes = ImageToSearchData.getvalue()
            ImageToSearchData.close()

            await bot.send(event=event, message="正在查找...")
            url = 'http://saucenao.com/search.php?output_type=2&numres=1&minsim=' + minsim + '&dbmask=' + str(
                db_bitmask) + '&api_key=' + api_key
            files = {'file': ("image.png", ImageBytes)}

            r = requests.post(url, files=files)

            processResults = True
            while True:
                r = requests.post(url, files=files)
                if r.status_code != 200:
                    if r.status_code == 403:
                        raise RioException('Incorrect or Invalid API Key!')
                    else:
                        # 通常情况下，非200状态是由于服务器过载或没有搜索
                        await ReverseSearchImage.finish(Message(
                            f'{str(r.status_code)} Error.'))
                        print("status code: " + str(r.status_code))
                        time.sleep(10)
                else:
                    results = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(r.text)
                    if int(results['header']['user_id']) > 0:
                        # api回应
                        print(
                            'Remaining Searches 30s|24h: ' + str(results['header']['short_remaining']) + '|' + str(
                                results['header']['long_remaining']))
                        if int(results['header']['status']) == 0:
                            # 所有索引返回成功！
                            break
                        else:
                            if int(results['header']['status']) > 0:
                                # 一个或多个索引出现问题。
                                # 即使所有索引都失败，此搜索也被视为部分成功，因此仍会根据限制进行计算。
                                # 错误可能是暂时的，但因为不浪费搜索时间，所以需要留出恢复时间。
                                print('API Error. Retrying in 120 seconds...')
                                await ReverseSearchImage.finish(f'API Error.')
                                time.sleep(120)
                            else:
                                # Problem with search as submitted, bad image, or impossible request.
                                # Issue is unclear, so don't flood requests.
                                await ReverseSearchImage.finish(f'Bad image or other request error.')
                                print('Bad image or other request error. Skipping in 10 seconds...')
                                processResults = False
                                time.sleep(10)
                                break
                    else:
                        # 一般问题，api没有回应。正常站点接管此错误状态。
                        # 这个问题我也不知道，所以停顿一下防止flood。
                        await ReverseSearchImage.finish(f'Bad image, or API failure!')
                        print('Bad image, or API failure. Skipping in 10 seconds...')
                        break
            if processResults:
                # print(results)

                if int(results['header']['results_returned']) > 0:
                    # 一个或多个结果被返回
                    if float(results['results'][0]['header']['similarity']) > float(
                            results['header']['minimum_similarity']):
                        print('hit! ' + str(results['results'][0]['header']['similarity']))
                        # get vars to use
                        service_name = ''
                        illust_id = 0
                        member_id = -1
                        index_id = results['results'][0]['header']['index_id']
                        page_string = ''
                        page_match = re.search('(_p[\d]+)\.', results['results'][0]['header']['thumbnail'])
                        if page_match:
                            page_string = page_match.group(1)

                        if index_id == 5 or index_id == 6:
                            # 5->pixiv 6->pixiv historical
                            service_name = 'pixiv'
                            member_id = results['results'][0]['data']['member_id']
                            illust_id = results['results'][0]['data']['pixiv_id']
                        elif index_id == 8:
                            # 8->nico nico seiga
                            service_name = 'seiga'
                            member_id = results['results'][0]['data']['member_id']
                            illust_id = results['results'][0]['data']['seiga_id']
                        elif index_id == 10:
                            # 10->drawr
                            service_name = 'drawr'
                            member_id = results['results'][0]['data']['member_id']
                            illust_id = results['results'][0]['data']['drawr_id']
                        elif index_id == 11:
                            # 11->nijie
                            service_name = 'nijie'
                            member_id = results['results'][0]['data']['member_id']
                            illust_id = results['results'][0]['data']['nijie_id']
                        elif index_id == 34:
                            # 34->da
                            service_name = 'da'
                            illust_id = results['results'][0]['data']['da_id']
                        else:
                            # unknown
                            raise RioException('Unhandled Index! Exiting...')

                        long_remaining = str(results['header']['long_remaining'])
                        similarity = str(results['results'][0]['header']['similarity'])
                        if member_id >= 0:
                            ImageResult = {
                                "剩余查找次数/天": long_remaining,
                                "相似度": similarity,
                                "图源": service_name,
                                "画师ID": str(member_id),
                                "插画ID": str(illust_id),
                                "页数": page_string,
                                "链接": str(results['results'][0]['data']['ext_urls'])
                            }
                        else:
                            ImageResult = {
                                "剩余查找次数/天": long_remaining,
                                "相似度": similarity,
                                "图源": service_name,
                                "插画ID": str(illust_id),
                                "页数": page_string,
                            }
                        message = ''
                        for entry in ImageResult.items():
                            message += f'{entry[0]} : {entry[1]}\n'
                        message += '\b'

                        # 如果是群聊消息
                        if isinstance(event, GroupMessageEvent):
                            event: GroupMessageEvent
                            try:
                                group_member_info = await bot.get_group_member_info(group_id=event.group_id,
                                                                                    user_id=int(event.get_user_id()))
                                print(group_member_info)
                                await send_forward_msg(bot, event, group_member_info['nickname'],
                                                       event.get_user_id(),
                                                       [Message(message), Message('合并转发,为防风控')])

                            except ActionFailed:
                                await ReverseSearchImage.finish('消息被风控!')
                        else:
                            await ReverseSearchImage.finish(message)
                    else:
                        await ReverseSearchImage.finish(
                            f'miss... \n查找到的最高相似度为:' + str(
                                results['results'][0]['header']['similarity']))
                else:
                    await ReverseSearchImage.finish(Message(f'没有搜到哦~'))
                if int(results['header']['long_remaining']) < 1:  # 可能是负数
                    raise RioException('响应过载,100次/天')
                if int(results['header']['short_remaining']) < 1:
                    raise RioException('响应过载,4次/30s')
    except ActionFailed:
        await ReverseSearchImage.finish('消息被风控!')
    except RioException as e:
        await ReverseSearchImage.finish(str(e))
    except (IndexError, ClientError):
        await bot.send(event, traceback.format_exc())
        await ReverseSearchImage.finish("参数错误")


class RioException(Exception):
    def __init__(self, msg):
        super(RioException, self).__init__(msg)
