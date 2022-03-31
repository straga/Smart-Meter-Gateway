# Copyright (c) 2021 Viktor Vorobjov

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class DataClassArg:
    def __init__(self, *args, **kwargs):
        for key in args:
            setattr(self, key, None)
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def a_dict(self):
        return self.__dict__


async def _g():
    pass
type_coro = type(_g())


def is_coro(func):
    if isinstance(func, type_coro):
        return True
    return False


def launch(func, *args, loop=None, **kwargs):

    try:
        res = func(*args, **kwargs)
        if isinstance(res, type_coro):
            if not loop:
                loop = asyncio.get_event_loop()
            return loop.create_task(res)
        else:
            return res
    except Exception as e:
        print(e)
        pass





