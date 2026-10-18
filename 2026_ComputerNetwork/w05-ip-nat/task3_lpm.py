#!/usr/bin/env python3
"""Week 5 · Task 3 — Make longest-prefix match fast.

Textbook §4.3.3.

`LinearTable` is correct and it is what you probably wrote in Task 1: keep the
prefixes in a list, check every one, remember the longest that matched. On six
entries that is fine. A real router holds close to a million, and it has to
answer while the packet is still in the buffer.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first: `bench.py` checks every one of your answers against the
linear table. A fast router that forwards to the wrong next hop is not a
router, it is an outage.
"""


class LinearTable:
    """Correct, and slow in the obvious way."""

    def __init__(self):
        self.entries = []                     # (prefix_len, network, next_hop)

    def add(self, network, prefix_len, next_hop):
        self.entries.append((prefix_len, network, next_hop))

    def lookup(self, address):
        best = None
        for plen, net, hop in self.entries:
            mask = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
            if address & mask == net and (best is None or plen > best[0]):
                best = (plen, hop)
        return best[1] if best else None


class YourTable:
    """접두사 길이별 해시 테이블을 사용하는 빠른 LPM 테이블."""

    def __init__(self):
        # tables[길이]는 {네트워크 주소: next_hop} 형태의 딕셔너리이다.
        self.tables = [{} for _ in range(33)]

        # lookup 때마다 마스크를 다시 만들지 않도록 한 번만 계산한다.
        self.masks = [
            (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF
            for prefix_len in range(33)
        ]
        # next_hop 자체가 None일 때도 "항목 없음"과 구분하기 위한 표식이다.
        self._missing = object()

    def add(self, network, prefix_len, next_hop):
        # LinearTable은 같은 길이와 네트워크가 중복되면 먼저 추가된 항목을
        # 선택한다. setdefault를 사용하면 기존 값을 덮어쓰지 않아 그 의미가
        # 그대로 보존된다.
        self.tables[prefix_len].setdefault(network, next_hop)

    def lookup(self, address):
        # 긴 접두사부터 확인하므로 처음 찾은 항목이 곧 longest-prefix match다.
        # IPv4 접두사 길이는 0~32뿐이라 테이블 크기와 무관하게 최대 33번 본다.
        tables = self.tables
        masks = self.masks
        missing = self._missing
        for prefix_len in range(32, -1, -1):
            next_hop = tables[prefix_len].get(
                address & masks[prefix_len], missing
            )
            if next_hop is not missing:
                return next_hop
        return None
