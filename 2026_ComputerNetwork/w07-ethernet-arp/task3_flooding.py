#!/usr/bin/env python3
"""Week 7 · Task 3 — A switch that runs out of room.

Textbook §6.4.3.

A switch does not have room for every station on the network. Its forwarding
table sits in a fixed amount of fast memory, and when that fills, something has
to go. Whatever goes gets **flooded** the next time anyone sends to it - out of
every port, to every station that did not ask for it.

`NaiveSwitch` handles a full table the simplest way: throw out whichever entry
has been there longest. That is a perfectly reasonable first idea and it is
close to the worst thing you can do with this traffic.

    python3 bench.py
    python3 bench.py --yours

Correctness first: every frame whose destination is reachable must still reach
it. A switch that floods less because it delivers less is not a switch.
"""
from collections import OrderedDict


class NaiveSwitch:
    """Correct. Evicts the oldest entry, which is not the least useful one."""

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    def __init__(self, ports, capacity):
        self.ports = ports
        self.capacity = capacity
        self.table = OrderedDict()                 # mac -> port, insertion order

    def handle(self, frame, in_port):
        src, dst, now = frame
        if src not in self.table and len(self.table) >= self.capacity:
            self.table.popitem(last=False)         # throw out the oldest arrival
        self.table[src] = in_port

        if dst == self.BROADCAST or dst not in self.table:
            return [p for p in range(self.ports) if p != in_port]
        out = self.table[dst]
        return [] if out == in_port else [out]


class YourSwitch:
    """Your switch. Same interface, same deliveries, far less flooding.

        __init__(ports, capacity)
        handle((src, dst, time), in_port) -> ports to forward out of

    `self.table` must exist and must never hold more than `capacity` entries.
    The harness checks this after every frame.

    What the baseline gets wrong: it decides what to keep by **when the entry
    arrived**, and that has nothing to do with whether it is about to be needed.
    On this trace a handful of stations carry most of the traffic, and the
    baseline keeps throwing them out to make room for stations that spoke once.

    Two questions worth separating:

      * which entry should leave when the table is full?
      * should learning a new source ever be *declined*?

    The second one is less obvious and is worth thinking about before you
    dismiss it.

    Note what you are NOT allowed to do: you cannot look at `where`, you cannot
    see the future, and you cannot hold more than `capacity` entries. Everything
    you know comes from the frames you have already handled.
    """

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    def __init__(self, ports, capacity):
        from zlib import crc32

        self.ports = ports
        self.capacity = capacity
        self.table = OrderedDict()  # mac -> port; order breaks frequency ties by recency
        # Fixed-size counters estimate how often an address has appeared so far.
        # They store neither MAC addresses nor ports, so the forwarding table
        # remains the only collection of learned station locations.
        self._mask = 2047
        self._counts_a = [0] * (self._mask + 1)
        self._counts_b = [0] * (self._mask + 1)
        self._crc32 = crc32

    def _slots(self, mac):
        encoded = mac.encode("ascii")
        return (self._crc32(encoded) & self._mask,
                self._crc32(encoded, 0x9e3779b9) & self._mask)

    def _observe(self, mac):
        a, b = self._slots(mac)
        self._counts_a[a] += 1
        self._counts_b[b] += 1

    def _frequency(self, mac):
        a, b = self._slots(mac)
        return min(self._counts_a[a], self._counts_b[b])

    def handle(self, frame, in_port):
        src, dst, now = frame
        self._observe(src)
        if dst != self.BROADCAST:
            self._observe(dst)

        if src in self.table:
            self.table[src] = in_port
            self.table.move_to_end(src)
        elif self.capacity > 0:
            if len(self.table) < self.capacity:
                self.table[src] = in_port
            else:
                victim = min(self.table, key=self._frequency)
                if self._frequency(src) > self._frequency(victim):
                    del self.table[victim]
                    self.table[src] = in_port

        if dst == self.BROADCAST or dst not in self.table:
            return [p for p in range(self.ports) if p != in_port]
        out = self.table[dst]
        self.table.move_to_end(dst)
        return [] if out == in_port else [out]
