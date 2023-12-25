import os
import dill
import asyncio
import logging
import aiofiles

import copy
import typing

from aiogram.dispatcher.storage       import BaseStorage
from aiogram.dispatcher.filters.state import State


class DillStorage(BaseStorage):
    async def wait_closed(self):
        ...

    async def close(self):
        await self.save_data_async()
        self.data.clear()


    def __init__(self, 
        file_path: str = os.path.abspath(__file__).replace(os.path.basename(__file__), f"storage_data.dill"),
        defult_state: State = None,
    ):
        self.file_path = file_path
        self.data = self.load_data()
        self.lock = asyncio.Lock()

        self.defult_state = defult_state


    def load_data(self):
        if not os.path.exists(self.file_path):
            return {}

        try:
            with open(self.file_path, 'rb') as file:
                return dill.load(file)
        except Exception as ex:
            logging.error(f"{ex.__class__.__name__}: {ex}")
        
        return {}

    async def save_data_async(self):
        async with self.lock:
            try:
                async with aiofiles.open(self.file_path, 'wb') as file:
                    await file.write(dill.dumps(self.data))
            except Exception as ex:
                logging.error(f"{ex.__class__.__name__}: {ex}")


    def resolve_address(self, chat, user):
        chat_id, user_id = map(str, self.check_address(chat = chat, user = user))

        if chat_id not in self.data:
            self.data[chat_id] = {}

        if user_id not in self.data[chat_id]:
            self.data[chat_id][user_id] = {
                'state': self.defult_state, 
                'data': {}, 
                'bucket': {}
            }

        return chat_id, user_id

    async def get_state(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[str] = None
    ) -> typing.Optional[str]:
        chat, user = self.resolve_address(chat = chat, user = user)

        return self.data[chat][user].get("state", self.resolve_state(default))

    async def get_data(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[str] = None
    ) -> typing.Dict:
        chat, user = self.resolve_address(chat = chat, user = user)
        
        return copy.deepcopy(self.data[chat][user]['data'])

    async def update_data(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        data: typing.Dict = None, 
        **kwargs
    ):
        if data is None:
            data = {}

        chat, user = self.resolve_address(chat = chat, user = user)
        self.data[chat][user]['data'].update(data, **kwargs)

        await self.save_data_async()

    async def set_state(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        state: typing.AnyStr = None
    ):
        chat, user = self.resolve_address(chat = chat, user = user)
        self.data[chat][user]['state'] = self.resolve_state(state)

        await self.save_data_async()

    async def set_data(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        data: typing.Dict = None
    ):
        chat, user = self.resolve_address(chat = chat, user = user)
        self.data[chat][user]['data'] = copy.deepcopy(data)
        self._cleanup(chat, user)

        await self.save_data_async()

    async def reset_state(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        with_data: typing.Optional[bool] = True
    ):
        await self.set_state(chat = chat, user = user, state = None)
        if with_data:
            await self.set_data(chat = chat, user = user, data = {})
        self._cleanup(chat, user)

        await self.save_data_async()

    def has_bucket(self):
        return True

    async def get_bucket(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        default: typing.Optional[dict] = None
    ) -> typing.Dict:
        chat, user = self.resolve_address(chat = chat, user = user)
        
        return copy.deepcopy(self.data[chat][user]['bucket'])

    async def set_bucket(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        bucket: typing.Dict = None
    ):
        chat, user = self.resolve_address(chat = chat, user = user)
        self.data[chat][user]['bucket'] = copy.deepcopy(bucket)
        self._cleanup(chat, user)
        
        await self.save_data_async()

    async def update_bucket(self, *,
        chat: typing.Union[str, int, None] = None,
        user: typing.Union[str, int, None] = None,
        bucket: typing.Dict = None, 
        **kwargs
    ):
        if bucket is None:
            bucket = {}

        chat, user = self.resolve_address(chat = chat, user = user)
        self.data[chat][user]['bucket'].update(bucket, **kwargs)

        await self.save_data_async()

    def _cleanup(self, chat, user):
        chat, user = self.resolve_address(chat = chat, user = user)
        if self.data[chat][user] == {
            'state': None, 
            'data': {}, 
            'bucket': {}
        }:
            del self.data[chat][user]
        if not self.data[chat]:
            del self.data[chat]
