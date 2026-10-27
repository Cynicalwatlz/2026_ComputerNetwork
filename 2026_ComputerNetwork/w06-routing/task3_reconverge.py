#!/usr/bin/env python3
"""Week 6 · Task 3 — Reconverge without recomputing the world.

Textbook §5.2.1, §5.3.

A link flaps. Every router in the area has to decide what changed. `FullRecompute`
does the honest thing: throw the table away and run Dijkstra again, from scratch,
for every event. It is correct and it is what the first implementations did.

It is also why a single flapping link in a large area used to melt the CPU of
every router that could see it.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first. `bench.py` compares your table against a full recompute after
**every single event**. A router that is fast and wrong black-holes traffic.
"""
import heapq

# The harness counts how many times you run a full SPF. This is the score:
# wall-clock time in Python says more about dictionary overhead than about
# routing, but "how many times did the CPU have to recompute the world" is
# exactly what melted real routers.
SPF_RUNS = 0


def dijkstra_table(graph, source):
    """Reference shortest-path-first. Returns {destination: first_hop}.

    Use THIS function whenever you need a full recompute. Rolling your own to
    dodge the counter is not an optimisation, it is cheating the meter.
    """
    global SPF_RUNS
    SPF_RUNS += 1
    best = {source: (0, None)}
    pq, done = [(0, source, None)], set()
    while pq:
        cost, node, first_hop = heapq.heappop(pq)
        if node in done:
            continue
        done.add(node)
        best[node] = (cost, first_hop)
        for nbr, w in sorted(graph[node].items()):
            if nbr in done:
                continue
            hop = nbr if node == source else first_hop
            if cost + w < best.get(nbr, (float("inf"), None))[0]:
                best[nbr] = (cost + w, hop)
                heapq.heappush(pq, (cost + w, nbr, hop))
    return {d: h for d, (_, h) in best.items() if d != source and h}


class FullRecompute:
    """On every event, forget everything and run SPF again."""

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        self.table = dijkstra_table(self.graph, self.source)


class YourRouter:
    """Your router. Same two methods, same table, less work per event.

    What is actually true after one link changes:

      * most destinations are not affected at all
      * a link that is not on any of your shortest paths, going *up*, can only
        matter if it creates something shorter
      * a link going *down* only matters if you were using it

    Deciding which of those applies, cheaply, without getting it wrong, is the
    task. Getting it wrong is worse than being slow - the harness will catch it
    on the event where it happens.
    """

    def __init__(self, graph, source):
        self.graph = {node: dict(edges) for node, edges in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)
        self.distances, self.parents = self._shortest_tree()

    def _shortest_tree(self):
        """Cache the costs and chosen tree of a counted full table rebuild.

        The same heap order and strict improvement rule as dijkstra_table()
        identify its selected edges. This cache accompanies a counted rebuild;
        it never replaces dijkstra_table() when a full rebuild is needed.
        """
        best = {self.source: 0}
        parents = {}
        done = set()
        queue = [(0, self.source)]
        while queue:
            cost, node = heapq.heappop(queue)
            if node in done:
                continue
            done.add(node)
            for neighbour, weight in sorted(self.graph[node].items()):
                if neighbour in done:
                    continue
                candidate = cost + weight
                if candidate < best.get(neighbour, float("inf")):
                    best[neighbour] = candidate
                    parents[neighbour] = node
                    heapq.heappush(queue, (candidate, neighbour))
        return best, {node: parent for node, parent in parents.items()
                      if node in done}

    def _propagate_improvements(self, a, b):
        """Repair only paths that the cheaper/new link can improve.

        Positive weights mean a changed shortest path must start at one end of
        the link. A tied path follows the reference SPF's discovery order: its
        predecessor with the smaller (distance, name) is chosen first. Changes
        to a predecessor's first hop are also passed on to its descendants.
        """
        queue = [(self.distances[node], node) for node in (a, b)
                 if node in self.distances]
        heapq.heapify(queue)
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != self.distances.get(node):
                continue
            for neighbour, weight in self.graph[node].items():
                if neighbour == self.source:
                    continue
                hop = neighbour if node == self.source else self.table[node]
                candidate = distance + weight
                previous = self.distances.get(neighbour, float("inf"))
                parent = self.parents.get(neighbour)
                better = candidate < previous
                tied = (candidate == previous and parent is not None and
                        (distance, node) < (self.distances[parent], parent))
                inherited_hop = (candidate == previous and parent == node and
                                 self.table[neighbour] != hop)
                if better or tied:
                    self.distances[neighbour] = candidate
                    self.parents[neighbour] = node
                    self.table[neighbour] = hop
                    heapq.heappush(queue, (candidate, neighbour))
                elif inherited_hop:
                    self.table[neighbour] = hop
                    heapq.heappush(queue, (candidate, neighbour))

    def link_change(self, a, b, cost):
        old_cost = self.graph[a].get(b)
        if old_cost == cost:
            return

        inf = float("inf")
        da = self.distances.get(a, inf)
        db = self.distances.get(b, inf)

        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost

        if old_cost is None or (cost is not None and cost < old_cost):
            # An equal-cost alternative can change the reference's first hop.
            if ((da < inf and da + cost <= db) or
                    (db < inf and db + cost <= da)):
                self._propagate_improvements(a, b)
        elif self.parents.get(a) == b or self.parents.get(b) == a:
            # A used edge got dearer or disappeared. The old tree is no
            # longer a valid starting point, so count a full SPF rebuild.
            self.table = dijkstra_table(self.graph, self.source)
            self.distances, self.parents = self._shortest_tree()
