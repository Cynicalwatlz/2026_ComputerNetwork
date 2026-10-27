#!/usr/bin/env python3
"""Capture all three FRR tables and time fully settled OSPF changes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
ROUTERS = ("r1", "r2", "r3")
IDS = {"r1": "1.1.1.1", "r2": "2.2.2.2", "r3": "3.3.3.3"}


def run(*args):
    result = subprocess.run([DOCKER, "compose", "--profile", "routing", *args],
                            cwd=ROOT, text=True, encoding="utf-8",
                            errors="replace", capture_output=True)
    if result.returncode:
        raise RuntimeError(f"docker compose {' '.join(args)} failed:\n"
                           f"{result.stdout}\n{result.stderr}")
    return result.stdout


def vty(router, command):
    return run("exec", "-T", router, "vtysh", "-c", command)


def state():
    tables = {r: json.loads(vty(r, "show ip route ospf json")) for r in ROUTERS}
    peers = {r: json.loads(vty(r, "show ip ospf neighbor json"))["neighbors"]
             for r in ROUTERS}
    signatures = {}
    for router, table in tables.items():
        routes = []
        for prefix, entries in sorted(table.items()):
            for entry in entries:
                hops = tuple(sorted((n.get("directlyConnected", False),
                                     n.get("ip", ""), n.get("interfaceName", ""),
                                     n.get("active", False))
                                    for n in entry.get("nexthops", [])))
                routes.append((prefix, entry.get("metric"), hops))
        signatures[router] = tuple(routes)
    return tables, peers, signatures


def full_peers(peers, cut=False):
    expected = {
        "r1": {IDS["r3"]} if cut else {IDS["r2"], IDS["r3"]},
        "r2": {IDS["r3"]} if cut else {IDS["r1"], IDS["r3"]},
        "r3": {IDS["r1"], IDS["r2"]},
    }
    return all(set(peers[r]) == expected[r] and
               all(any(n.get("converged") == "Full" for n in entries)
                   for entries in peers[r].values()) for r in ROUTERS)


def all_prefixes(tables, prefixes):
    return all(prefixes <= set(tables[r]) for r in ROUTERS)


def direct(table, prefix, interface):
    return any(n.get("directlyConnected") and n.get("interfaceName") == interface
               for entry in table.get(prefix, []) for n in entry.get("nexthops", []))


def direct_prefix(table, interface):
    found = [p for p in table if direct(table, p, interface)]
    if len(found) != 1:
        raise RuntimeError(f"Expected one direct OSPF prefix on {interface}: {found}")
    return found[0]


def capture(filename):
    OUT.mkdir(exist_ok=True)
    parts = [f"Captured {datetime.now(timezone.utc).isoformat()} UTC\n"]
    for router in ROUTERS:
        parts.append(f"===== {router} =====\n{vty(router, 'show ip route ospf').rstrip()}\n")
    (OUT / filename).write_text("\n".join(parts), encoding="utf-8")
    print(f"saved out/{filename} for r1, r2, r3", flush=True)


def wait_for(predicate, started, timeout=100):
    first, previous, repeats = None, None, 0
    while time.monotonic() - started < timeout:
        tables, peers, signatures = state()
        elapsed = time.monotonic() - started
        if predicate(tables, peers, signatures):
            if signatures == previous:
                repeats += 1
            else:
                first, repeats = elapsed, 1
            previous = signatures
            if repeats >= 3:
                return first, elapsed
        else:
            first, previous, repeats = None, None, 0
        time.sleep(0.5)
    raise TimeoutError(f"No fully settled OSPF state after {timeout}s")


def record(label, first, confirmed, mode="a"):
    with (OUT / "reconverge.txt").open(mode, encoding="utf-8") as stream:
        if mode == "w":
            stream.write("Actual Docker FRR measurement. Seconds from mutation request "
                         "to first complete state of all three routers, confirmed "
                         "in three consecutive polls.\n")
        stream.write(f"{label}: {first:.3f} s (stable confirmation {confirmed:.3f} s)\n")
    print(f"{label}: {first:.3f} s (stable at {confirmed:.3f} s)", flush=True)


def ready(cut=False):
    before = state()
    prefixes = set().union(*(set(before[0][r]) for r in ROUTERS))
    if len(prefixes) != 3 or not all_prefixes(before[0], prefixes):
        raise RuntimeError("All routers must have all three OSPF prefixes")
    if not full_peers(before[1], cut=cut):
        raise RuntimeError("Required OSPF neighbour state is not yet stable")
    return before, prefixes


def cut():
    before, prefixes = ready()
    net_a = direct_prefix(before[0]["r1"], "eth0")
    net_b = direct_prefix(before[0]["r1"], "eth1")
    capture("route-before.txt")
    started = time.monotonic()
    run("exec", "-T", "r1", "ip", "link", "set", "eth1", "down")

    def repaired(t, p, s):
        return (full_peers(p, cut=True) and all_prefixes(t, prefixes)
                and not direct(t["r1"], net_b, "eth1")
                and net_a in t["r2"]
                and s["r1"] != before[2]["r1"]
                and s["r2"] != before[2]["r2"])

    first, confirmed = wait_for(repaired, started)
    capture("route-after.txt")
    record("cut, all three tables repaired", first, confirmed, mode="w")


def restore():
    before, prefixes = ready(cut=True)
    net_b = direct_prefix(before[0]["r2"], "eth1")
    capture("route-prerestore.txt")
    started = time.monotonic()
    run("exec", "-T", "r1", "ip", "link", "set", "eth1", "up")

    def repaired(t, p, s):
        return (full_peers(p) and all_prefixes(t, prefixes)
                and direct(t["r1"], net_b, "eth1") and s != before[2])

    first, confirmed = wait_for(repaired, started)
    capture("route-restored.txt")
    record("restore, all three tables repaired", first, confirmed)


def cost():
    before, prefixes = ready()
    capture("cost-before.txt")
    started = time.monotonic()
    run("exec", "-T", "r1", "vtysh", "-c", "configure terminal",
        "-c", "interface eth0", "-c", "ip ospf cost 100")

    def moved(t, p, s):
        return (full_peers(p) and all_prefixes(t, prefixes)
                and any(s[r] != before[2][r] for r in ROUTERS))

    first, confirmed = wait_for(moved, started)
    capture("cost-after.txt")
    record("cost 10 to 100 on r1 eth0, path moved", first, confirmed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("up", "routes", "cut", "restore", "cost", "down"))
    parser.add_argument("--docker", default=os.environ.get("DOCKER_BIN") or shutil.which("docker"))
    args = parser.parse_args()
    global DOCKER
    DOCKER = args.docker
    if not DOCKER:
        parser.error("Docker CLI not found; pass --docker or set DOCKER_BIN")
    if args.action == "up":
        print(run("up", "-d", "--no-build", "r1", "r2", "r3"), end="")
    elif args.action == "routes":
        for router in ROUTERS:
            print(f"===== {router} =====\n{vty(router, 'show ip route ospf')}")
    elif args.action == "cut":
        cut()
    elif args.action == "restore":
        restore()
    elif args.action == "cost":
        cost()
    else:
        print(run("down"), end="")


if __name__ == "__main__":
    main()
