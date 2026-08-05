from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

type RedisScalar = str | bytes
type RedisFields = dict[RedisScalar, RedisScalar]
type RedisMessage = tuple[RedisScalar, RedisFields]
type RedisStreamBatch = tuple[RedisScalar, list[RedisMessage]]


class RedisClient(Protocol):
    async def ping(self) -> bool: ...

    async def xadd(self, name: str, fields: Mapping[str, str]) -> RedisScalar: ...

    async def xgroup_create(
        self,
        name: str,
        groupname: str,
        id: str = "0-0",
        mkstream: bool = False,
    ) -> bool: ...

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Mapping[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[RedisStreamBatch]: ...

    async def xack(self, name: str, groupname: str, *ids: RedisScalar) -> int: ...

    async def aclose(self) -> None: ...
