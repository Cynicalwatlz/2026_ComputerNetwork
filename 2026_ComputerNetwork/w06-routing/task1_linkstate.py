#!/usr/bin/env python3
"""Week 6 · Task 1 — Link state: build the forwarding table yourself.

Textbook §5.2 (link state and distance vector) and §5.3 (OSPF).

Every OSPF router ends up holding the same map of the network, and then each one
computes, alone, where to send a packet for every destination. The computation is
Dijkstra; the output is a forwarding table with **one next hop per destination**,
not a path.

That last part is what makes routing work without anybody carrying a route around
in the packet. Build it.

    python3 task1_linkstate.py --verify
"""
import argparse
import heapq
from itertools import count

# Undirected weighted graph: node -> {neighbour: cost}
TOPOLOGY = {
    "u": {"v": 2, "w": 5, "x": 1},
    "v": {"u": 2, "w": 3, "x": 2},
    "w": {"u": 5, "v": 3, "x": 3, "y": 1, "z": 5},
    "x": {"u": 1, "v": 2, "w": 3, "y": 1},
    "y": {"w": 1, "x": 1, "z": 2},
    "z": {"w": 5, "y": 2},
}


def _shortest_routes(graph, source):
    """Compute costs and first hops, preferring the smallest hop on a tie."""
    distances = {source: 0}
    first_hops = {}
    serial = count()
    queue = [(0, "", next(serial), source)]

    while queue:
        cost, hop_name, _, node = heapq.heappop(queue)
        if cost != distances[node]:
            continue
        if node != source and hop_name != str(first_hops[node]):
            continue

        for neighbour, link_cost in graph[node].items():
            if neighbour == source:
                continue
            candidate_cost = cost + link_cost
            candidate_hop = neighbour if node == source else first_hops[node]
            old_cost = distances.get(neighbour)
            if (old_cost is None or candidate_cost < old_cost or
                    (candidate_cost == old_cost and
                     str(candidate_hop) < str(first_hops[neighbour]))):
                distances[neighbour] = candidate_cost
                first_hops[neighbour] = candidate_hop
                heapq.heappush(queue, (candidate_cost, str(candidate_hop),
                                       next(serial), neighbour))

    distances.pop(source)
    return distances, first_hops


def dijkstra(graph, source):
    """Shortest path cost from `source` to every node.

    Return {node: cost}. Unreachable nodes must not appear.

    You write the loop. `heapq` is allowed; `networkx` is not.
    """
    distances, _ = _shortest_routes(graph, source)
    return distances


def forwarding_table(graph, source):
    """What the router at `source` actually installs.

    Return {destination: first_hop}, where first_hop is a **direct neighbour**
    of `source` - the one interface a packet for that destination leaves by.

    The source itself is not in the table. Neither are unreachable nodes.

    The trap: it is easy to compute the full path and then take path[1]. That
    works, but think about what a router does when two shortest paths tie, and
    pick a rule. Say which in observation.md.
    """
    _, first_hops = _shortest_routes(graph, source)
    return first_hops


def link_down(graph, a, b):
    """A copy of `graph` with the link a-b removed, in both directions."""
    g = {n: dict(e) for n, e in graph.items()}
    g[a].pop(b, None)
    g[b].pop(a, None)
    return g


# ------------------------------------------------------------------- harness
# Costs from the textbook's worked example, §5.2.1
EXPECTED_COST_U = {"v": 2, "w": 3, "x": 1, "y": 2, "z": 4}
EXPECTED_TABLE_U = {"v": "v", "w": "x", "x": "x", "y": "x", "z": "x"}


def verify():
    fails = 0
    try:
        cost = dijkstra(TOPOLOGY, "u")
    except NotImplementedError:
        print("  dijkstra is still a stub"); return 1
    ok = cost == EXPECTED_COST_U
    print(f"  {'ok  ' if ok else 'FAIL'}  costs from u: {cost}")
    if not ok:
        print(f"        expected {EXPECTED_COST_U}")
    fails += not ok

    try:
        table = forwarding_table(TOPOLOGY, "u")
    except NotImplementedError:
        print("  forwarding_table is still a stub"); return 1
    ok = table == EXPECTED_TABLE_U
    print(f"  {'ok  ' if ok else 'FAIL'}  table at u:  {table}")
    if not ok:
        print(f"        expected {EXPECTED_TABLE_U}")
    fails += not ok

    # every node should be able to reach every other
    for n in TOPOLOGY:
        t = forwarding_table(TOPOLOGY, n)
        missing = set(TOPOLOGY) - {n} - set(t)
        bad = [d for d, h in t.items() if h not in TOPOLOGY[n]]
        ok = not missing and not bad
        print(f"  {'ok  ' if ok else 'FAIL'}  table at {n} covers all, hops are neighbours"
              + (f"  missing={missing} bad={bad}" if not ok else ""))
        fails += not ok

    # cutting a link must change somebody's mind
    cut = link_down(TOPOLOGY, "u", "x")
    after = forwarding_table(cut, "u")
    ok = after != table
    print(f"  {'ok  ' if ok else 'FAIL'}  u reroutes when u-x goes down: {after}")
    fails += not ok

    print(f"\n  {'all ok' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    raise SystemExit(verify() if a.verify else p.print_help())
