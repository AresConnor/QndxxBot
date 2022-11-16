from nonebot.adapters.onebot.v11 import Event, GroupRequestEvent


def _check(event:Event):
    return isinstance(event,GroupRequestEvent)