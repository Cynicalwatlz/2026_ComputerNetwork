#!/usr/bin/env python3
"""Week 4 · Task 1 — Build reliable delivery on top of an unreliable channel.

Textbook §3.4 (reliable data transfer) and §3.5 (TCP's sequence numbers).

`UnreliableChannel` below loses packets, reorders them, duplicates them, and
delays them. It is the network as §3.4 models it. Your job is to move a file
across it and have the bytes arrive intact and in order.

That is the whole of TCP's reliability story with the congestion control taken
out, and it is worth building once by hand before you ever trust a socket again.

    python3 task1_rdt.py --verify
"""
import argparse, hashlib, random

PAYLOAD = 8            # bytes per packet - small, so you see the sequencing


class UnreliableChannel:
    """Loses 10%, duplicates 3%, reorders, and delays. Deterministic by seed.

    You may not make it nicer. You may not read its internals. It is the only
    way your sender can reach your receiver.
    """

    def __init__(self, seed=246, loss=0.10, dup=0.03, reorder=0.10):
        self.rng = random.Random(seed)
        self.loss, self.dup, self.reorder = loss, dup, reorder
        self.wire = []          # packets in flight, in no particular order
        self.stats = {"sent": 0, "lost": 0, "duplicated": 0, "delivered": 0}

    def send(self, packet):
        """Hand a packet to the network. It may never come out."""
        self.stats["sent"] += 1
        if self.rng.random() < self.loss:
            self.stats["lost"] += 1
            return
        copies = 2 if self.rng.random() < self.dup else 1
        self.stats["duplicated"] += copies - 1
        for _ in range(copies):
            if self.rng.random() < self.reorder and self.wire:
                self.wire.insert(self.rng.randrange(len(self.wire)), packet)
            else:
                self.wire.append(packet)

    def receive(self):
        """Take the next packet out, or None if the network has nothing."""
        if not self.wire:
            return None
        self.stats["delivered"] += 1
        return self.wire.pop(0)


class Sender:
    """Stop-and-wait sender: keep one numbered packet in flight at a time."""

    TIMEOUT = 4

    def __init__(self, data_channel, ack_channel, data):
        self.data_channel = data_channel
        self.ack_channel = ack_channel
        self.packets = [
            ("DATA", sequence, data[start:start + PAYLOAD])
            for sequence, start in enumerate(range(0, len(data), PAYLOAD))
        ]
        self.sequence = 0
        self.waited = self.TIMEOUT  # Send the first packet on the first step.

    def step(self):
        """Process one ACK and send/retransmit when needed."""
        ack = self.ack_channel.receive()
        if (
            ack is not None
            and len(ack) == 2
            and ack[0] == "ACK"
            and ack[1] == self.sequence
        ):
            self.sequence += 1
            self.waited = self.TIMEOUT

        if self.sequence >= len(self.packets):
            return False

        if self.waited >= self.TIMEOUT:
            self.data_channel.send(self.packets[self.sequence])
            self.waited = 0
        else:
            self.waited += 1

        return True


class Receiver:
    """Accept each expected packet once and acknowledge every valid arrival."""

    def __init__(self, data_channel, ack_channel):
        self.data_channel = data_channel
        self.ack_channel = ack_channel
        self.expected = 0
        self.output = bytearray()

    def step(self):
        packet = self.data_channel.receive()
        if packet is None or len(packet) != 3 or packet[0] != "DATA":
            return

        _, sequence, payload = packet
        if sequence == self.expected:
            self.output.extend(payload)
            self.expected += 1

        # ACK duplicates too: the original ACK may have been lost. The sender
        # ignores this ACK unless it matches the one packet currently awaited.
        if sequence < self.expected:
            self.ack_channel.send(("ACK", sequence))

    def data(self):
        """The bytes reassembled so far."""
        return bytes(self.output)


def verify(seed=246, size=2000, max_steps=200_000):
    original = bytes(random.Random(seed).getrandbits(8) for _ in range(size))
    up, down = UnreliableChannel(seed), UnreliableChannel(seed + 1)

    sender = Sender(up, down, original)
    receiver = Receiver(up, down)

    for _ in range(max_steps):
        alive = sender.step()
        receiver.step()
        if not alive and len(receiver.data() or b"") >= size:
            break

    got = receiver.data() or b""
    ok = hashlib.sha256(got).hexdigest() == hashlib.sha256(original).hexdigest()
    print(f"  bytes    sent {size}   received {len(got)}")
    print(f"  channel  {up.stats}")
    print(f"  result   {'IDENTICAL' if ok else 'CORRUPTED OR INCOMPLETE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    p.add_argument("--seed", type=int, default=246)
    a = p.parse_args()
    raise SystemExit(verify(a.seed) if a.verify else p.print_help())
