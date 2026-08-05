from __future__ import annotations

from collections.abc import Mapping

from redis.exceptions import RedisError

from app.core.protocols import RedisFields, RedisScalar, RedisStreamBatch


class FakeRedis:
    def __init__(self, *, fail_ping: bool = False, fail_xadd: bool = False) -> None:
        self.fail_ping = fail_ping
        self.fail_xadd = fail_xadd
        self.added: list[tuple[str, Mapping[str, str]]] = []
        self.acknowledged: list[tuple[str, str, tuple[RedisScalar, ...]]] = []
        self.groups: list[tuple[str, str, str, bool]] = []
        self.read_batches: list[list[RedisStreamBatch]] = []

    async def ping(self) -> bool:
        if self.fail_ping:
            raise RedisError("test Redis failure")
        return True

    async def xadd(self, name: str, fields: Mapping[str, str]) -> RedisScalar:
        if self.fail_xadd:
            raise RedisError("test Redis publication failure")
        self.added.append((name, fields))
        return b"1700000000000-0"

    async def xgroup_create(
        self,
        name: str,
        groupname: str,
        id: str = "0-0",
        mkstream: bool = False,
    ) -> bool:
        self.groups.append((name, groupname, id, mkstream))
        return True

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Mapping[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[RedisStreamBatch]:
        del groupname, consumername, streams, count, block
        return self.read_batches.pop(0) if self.read_batches else []

    async def xack(self, name: str, groupname: str, *ids: RedisScalar) -> int:
        self.acknowledged.append((name, groupname, ids))
        return len(ids)

    async def aclose(self) -> None:
        return None


def stream_fields(json_payload: str) -> RedisFields:
    return {b"data": json_payload.encode("utf-8")}

