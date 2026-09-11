#!/usr/bin/env python3
"""Repair BPMN DI routes locally; business XML and shape bounds remain unchanged.

The bounded search is deterministic, not a planar-layout guarantee. Reported
conflicts require further layout work. Only existing DI label bounds are known;
measured text and the saved diagram still require an independent visual audit.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import heapq
import itertools
import json
import math
from pathlib import Path
from typing import Any, Literal

BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"
DI = "http://www.omg.org/spec/DD/20100524/DI"
EPS = 0.001
GAP = 8.0
Point = tuple[float, float]
Box = tuple[float, float, float, float]


@dataclass
class Node:
    identifier: str
    box: Box
    kind: Literal["rect", "diamond", "ellipse"]
    container: bool


@dataclass
class SearchBudget:
    remaining: int
    used: int = 0


@dataclass
class Edge:
    identifier: str
    source: str
    target: str
    points: list[Point]
    element: Any


def local(element: Any) -> str:
    return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""


def ref(value: str | None) -> str:
    return (value or "").strip().split(":")[-1]


def number(value: str | None) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite BPMN DI coordinate")
    return result


def bounds(element: Any) -> Box:
    if element is None:
        raise ValueError("Missing BPMN DI Bounds")
    x, y, width, height = (number(element.get(k)) for k in ("x", "y", "width", "height"))
    if width <= 0 or height <= 0:
        raise ValueError("BPMN DI Bounds must have positive dimensions")
    return x, y, x + width, y + height


def equal(a: Point, b: Point) -> bool:
    return math.dist(a, b) < EPS


def orientation(a: Point, b: Point) -> int:
    return 0 if abs(a[1] - b[1]) < EPS else 1


def simplify(points: list[Point]) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if result and equal(result[-1], point):
            continue
        if len(result) > 1:
            a, b = result[-2:]
            if orientation(a, b) == orientation(b, point):
                # Remove only a forward collinear bend, never a retraced interval.
                if ((b[0] - a[0]) * (point[0] - b[0]) >= 0 and
                        (b[1] - a[1]) * (point[1] - b[1]) >= 0):
                    result.pop()
        result.append(point)
    return result


def segment_hit(a: Point, b: Point, c: Point, d: Point) -> tuple[str, Any] | None:
    """Intersection of arbitrary segments, including positive shared intervals."""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    length = math.hypot(rx, ry)
    if length < EPS or math.hypot(sx, sy) < EPS:
        return None
    dx, dy = c[0] - a[0], c[1] - a[1]
    determinant = rx * sy - ry * sx
    if abs(determinant) > EPS:
        t = (dx * sy - dy * sx) / determinant
        u = (dx * ry - dy * rx) / determinant
        if -EPS <= t <= 1 + EPS and -EPS <= u <= 1 + EPS:
            return "point", (a[0] + t * rx, a[1] + t * ry)
        return None
    if abs(dx * ry - dy * rx) > EPS * length:
        return None
    rr = length * length
    t0 = (dx * rx + dy * ry) / rr
    t1 = t0 + (sx * rx + sy * ry) / rr
    lo, hi = max(0.0, min(t0, t1)), min(1.0, max(t0, t1))
    if lo > hi + EPS / length:
        return None
    first = (a[0] + lo * rx, a[1] + lo * ry)
    last = (a[0] + hi * rx, a[1] + hi * ry)
    return ("overlap", (first, last)) if math.dist(first, last) > EPS else ("point", first)


def inside(point: Point, node: Node) -> bool:
    x1, y1, x2, y2 = node.box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    rx, ry = (x2 - x1) / 2, (y2 - y1) / 2
    dx, dy = abs(point[0] - cx), abs(point[1] - cy)
    if node.kind == "ellipse":
        return (dx / rx) ** 2 + (dy / ry) ** 2 < 1 - EPS / min(rx, ry)
    if node.kind == "diamond":
        return dx / rx + dy / ry < 1 - EPS / min(rx, ry)
    return x1 + EPS < point[0] < x2 - EPS and y1 + EPS < point[1] < y2 - EPS


def on_outline(point: Point, node: Node) -> bool:
    x1, y1, x2, y2 = node.box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    rx, ry = (x2 - x1) / 2, (y2 - y1) / 2
    dx, dy = abs(point[0] - cx), abs(point[1] - cy)
    if node.kind == "ellipse":
        return abs((dx / rx) ** 2 + (dy / ry) ** 2 - 1) < EPS
    if node.kind == "diamond":
        return abs(dx / rx + dy / ry - 1) < EPS
    return (x1 - EPS <= point[0] <= x2 + EPS and
            y1 - EPS <= point[1] <= y2 + EPS and
            min(abs(point[0] - x1), abs(point[0] - x2),
                abs(point[1] - y1), abs(point[1] - y2)) < EPS)


def enters(a: Point, b: Point, node: Node) -> bool:
    """Analytic interior test for an orthogonal segment and the real outline."""
    if abs(a[0] - b[0]) > EPS and abs(a[1] - b[1]) > EPS:
        # Invalid diagonals are rerouted regardless of obstacle intersections.
        return True
    x1, y1, x2, y2 = node.box
    axis = orientation(a, b)
    along1, along2 = sorted((a[axis], b[axis]))
    cross_value = a[1 - axis]
    low, high = (x1, x2) if axis == 0 else (y1, y2)
    cross_low, cross_high = (y1, y2) if axis == 0 else (x1, x2)
    if cross_value <= cross_low + EPS or cross_value >= cross_high - EPS:
        return False
    center, radius = (low + high) / 2, (high - low) / 2
    offset = abs(cross_value - (cross_low + cross_high) / 2) / ((cross_high - cross_low) / 2)
    if node.kind == "ellipse":
        extent = radius * math.sqrt(max(0, 1 - offset * offset))
        low, high = center - extent, center + extent
    elif node.kind == "diamond":
        extent = radius * (1 - offset)
        low, high = center - extent, center + extent
    return min(along2, high) - max(along1, low) > EPS


def shared_endpoint(edge: Edge, other: Edge, point: Point) -> bool:
    first = {identifier for identifier, end in ((edge.source, edge.points[0]), (edge.target, edge.points[-1])) if equal(point, end)}
    second = {identifier for identifier, end in ((other.source, other.points[0]), (other.target, other.points[-1])) if equal(point, end)}
    return bool(first & second)


def conflicts(edges: list[Edge], nodes: dict[str, Node], labels: list[Node]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for edge in edges:
        if edge.source not in nodes or edge.target not in nodes:
            issues.append({"category": "endpoint_unavailable", "edges": [edge.identifier]})
            continue
        if len(edge.points) < 2:
            issues.append({"category": "invalid_waypoints", "edges": [edge.identifier]})
            continue
        for end, identifier in ((edge.points[0], edge.source), (edge.points[-1], edge.target)):
            if not on_outline(end, nodes[identifier]):
                issues.append({"category": "detached_endpoint", "edges": [edge.identifier], "node": identifier})
        segments = list(zip(edge.points, edge.points[1:]))
        for index, (a, b) in enumerate(segments):
            if equal(a, b) or (abs(a[0] - b[0]) > EPS and abs(a[1] - b[1]) > EPS):
                issues.append({"category": "nonorthogonal_path", "edges": [edge.identifier], "segment": index})
                continue
            for node in itertools.chain(nodes.values(), labels):
                if not node.container and enters(a, b, node):
                    issues.append({"category": "edge_crosses_obstacle", "edges": [edge.identifier], "node": node.identifier})
            for earlier in range(index - 1):
                hit = segment_hit(a, b, *segments[earlier])
                closed = edge.source == edge.target and hit and hit[0] == "point" and equal(hit[1], edge.points[0]) and equal(hit[1], edge.points[-1])
                if hit and not closed:
                    issues.append({"category": "self_intersection", "edges": [edge.identifier]})
    for first, second in itertools.combinations(edges, 2):
        if len(first.points) < 2 or len(second.points) < 2:
            continue
        for a, b in zip(first.points, first.points[1:]):
            for c, d in zip(second.points, second.points[1:]):
                hit = segment_hit(a, b, c, d)
                if hit and not (hit[0] == "point" and shared_endpoint(first, second, hit[1])):
                    issues.append({"category": "edge_" + hit[0], "edges": [first.identifier, second.identifier]})
    # One issue per category/object pair keeps the diagnostic bounded.
    return list({json.dumps(issue, sort_keys=True): issue for issue in issues}.values())


def ports(node: Node, gap: float = GAP) -> list[tuple[Point, Point]]:
    """Three distinct orthogonal ports per side, on the true event/gateway outline."""
    x1, y1, x2, y2 = node.box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    rx, ry = (x2 - x1) / 2, (y2 - y1) / 2
    result = []
    for side in (1, -1):
        for fraction in (0.0, -0.5, 0.5):
            scale = math.sqrt(1 - fraction * fraction) if node.kind == "ellipse" else 1 - abs(fraction) if node.kind == "diamond" else 1
            result.append(((cx + side * rx * scale, cy + ry * fraction), (cx + side * (rx + gap), cy + ry * fraction)))
            result.append(((cx + rx * fraction, cy + side * ry * scale), (cx + rx * fraction, cy + side * (ry + gap))))
    return result


def segment_allowed(a: Point, b: Point, edge: Edge, fixed: list[Edge], obstacles: list[Node]) -> bool:
    if any(enters(a, b, node) for node in obstacles):
        return False
    for other in fixed:
        for c, d in zip(other.points, other.points[1:]):
            hit = segment_hit(a, b, c, d)
            if hit and not (hit[0] == "point" and shared_endpoint(edge, other, hit[1])):
                return False
    return True


def path_length(points: list[Point]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:])) + max(0, len(points) - 2) * 14


def search_route(edge: Edge, nodes: dict[str, Node], labels: list[Node], fixed: list[Edge], *, clearance: float = GAP, budget: SearchBudget | None = None) -> list[Point] | None:
    if budget is not None and budget.remaining <= 0:
        return None
    if edge.source not in nodes or edge.target not in nodes:
        return None
    real_obstacles = [node for node in nodes.values() if not node.container] + labels
    obstacles = [Node(n.identifier, (n.box[0] - clearance, n.box[1] - clearance, n.box[2] + clearance, n.box[3] + clearance), "rect", False) for n in real_obstacles]
    # Containers remain transparent except when they are this edge's endpoint.
    for identifier in (edge.source, edge.target):
        if nodes[identifier].container:
            obstacles.append(nodes[identifier])
    start_ports, end_ports = [], []
    for identifier, collection in ((edge.source, start_ports), (edge.target, end_ports)):
        for anchor, stub in ports(nodes[identifier], clearance):
            candidate = Edge(edge.identifier, edge.source, edge.target, [anchor, anchor], edge.element)
            if identifier == edge.source:
                candidate.points = [anchor, edge.points[-1] if edge.points else anchor]
            else:
                candidate.points = [edge.points[0] if edge.points else anchor, anchor]
            if segment_allowed(anchor, stub, candidate, fixed, real_obstacles):
                if not any(inside(stub, obstacle) for obstacle in obstacles):
                    collection.append((anchor, stub))
    if not start_ports or not end_ports:
        return None
    xs, ys = set(), set()
    for obstacle in obstacles:
        xs.update((obstacle.box[0], obstacle.box[2]))
        ys.update((obstacle.box[1], obstacle.box[3]))
    for route in fixed:
        for x, y in route.points:
            xs.update((x - clearance, x + clearance))
            ys.update((y - clearance, y + clearance))
    for anchor, stub in start_ports + end_ports:
        xs.add(stub[0]); ys.add(stub[1])
    xs.update((min(xs) - 3 * clearance, max(xs) + 3 * clearance))
    ys.update((min(ys) - 3 * clearance, max(ys) + 3 * clearance))
    xlist, ylist = sorted(xs), sorted(ys)
    xindex, yindex = {x: i for i, x in enumerate(xlist)}, {y: i for i, y in enumerate(ylist)}
    targets = {(xindex[stub[0]], yindex[stub[1]]): (anchor, stub) for anchor, stub in end_ports}
    target_stubs = [stub for _, stub in end_ports]
    obstacle_cache: dict[tuple[Point, Point], bool] = {}
    fixed_cache: dict[tuple[Point, Point], bool] = {}

    def allowed(a: Point, b: Point) -> bool:
        key = (a, b) if a < b else (b, a)
        if key not in obstacle_cache:
            obstacle_cache[key] = not any(enters(a, b, obstacle) for obstacle in obstacles)
        if not obstacle_cache[key]:
            return False
        if key not in fixed_cache:
            # Core grid points are outside nodes, so no shared-end exception applies.
            fixed_cache[key] = not any(segment_hit(a, b, c, d) for other in fixed for c, d in zip(other.points, other.points[1:]))
        return fixed_cache[key]

    def heuristic(point: Point) -> float:
        return min(abs(point[0] - end[0]) + abs(point[1] - end[1]) for end in target_stubs)

    queue: list[tuple[float, float, int, tuple[int, int, int]]] = []
    distances: dict[tuple[int, int, int], float] = {}
    previous: dict[tuple[int, int, int], tuple[int, int, int] | None] = {}
    origins: dict[tuple[int, int, int], Point] = {}
    serial = itertools.count()
    for anchor, stub in start_ports:
        state = (xindex[stub[0]], yindex[stub[1]], orientation(anchor, stub))
        cost = math.dist(anchor, stub)
        distances[state] = cost
        previous[state] = None
        origins[state] = anchor
        heapq.heappush(queue, (cost + heuristic(stub), cost, next(serial), state))
    expanded = 0
    # Bounded work prevents large diagrams from turning a local repair into a hang.
    while queue and expanded < 20000 and (budget is None or budget.remaining > 0):
        _, cost, _, state = heapq.heappop(queue)
        if cost > distances[state] + EPS:
            continue
        expanded += 1
        if budget is not None:
            budget.remaining -= 1
            budget.used += 1
        ix, iy, direction = state
        point = (xlist[ix], ylist[iy])
        if (ix, iy) in targets:
            anchor, stub = targets[(ix, iy)]
            trail = [point]
            cursor = state
            while previous[cursor] is not None:
                cursor = previous[cursor]
                trail.append((xlist[cursor[0]], ylist[cursor[1]]))
            trail.append(origins[cursor])
            result = simplify(list(reversed(trail)) + [anchor])
            candidate = Edge(edge.identifier, edge.source, edge.target, result, edge.element)
            # Check this candidate only; fixed routes were already validated.
            # Rechecking every fixed/fixed pair at each target is quadratic.
            if not conflicts([candidate], nodes, labels) and all(segment_allowed(a, b, candidate, fixed, []) for a, b in zip(result, result[1:])):
                return result
        for nx, ny in ((ix + 1, iy), (ix - 1, iy), (ix, iy + 1), (ix, iy - 1)):
            if not (0 <= nx < len(xlist) and 0 <= ny < len(ylist)):
                continue
            neighbor = (xlist[nx], ylist[ny])
            if not allowed(point, neighbor):
                continue
            next_direction = orientation(point, neighbor)
            next_state = (nx, ny, next_direction)
            new_cost = cost + math.dist(point, neighbor) + (14 if direction != next_direction else 0)
            if new_cost + EPS < distances.get(next_state, math.inf):
                distances[next_state] = new_cost
                previous[next_state] = state
                origins[next_state] = origins[state]
                heapq.heappush(queue, (new_cost + heuristic(neighbor), new_cost, next(serial), next_state))
    return None


def read_plane(root: Any, plane: Any) -> tuple[dict[str, Node], list[Node], list[Edge]]:
    index = {element.get("id"): element for element in root.iter() if element.get("id")}
    parents = {child: parent for parent in root.iter() for child in parent}
    nodes, labels, edges = {}, [], []
    for shape in plane.findall("{%s}BPMNShape" % BPMNDI):
        identifier = ref(shape.get("bpmnElement"))
        if identifier not in index:
            raise ValueError("Shape references missing BPMN element: " + identifier)
        semantic = index[identifier]
        kind = local(semantic)
        container = kind in ("lane", "participant", "group") or (kind in ("subProcess", "adHocSubProcess", "transaction") and shape.get("isExpanded") == "true")
        outline = "diamond" if kind.endswith("Gateway") else "ellipse" if kind.endswith("Event") else "rect"
        nodes[identifier] = Node(identifier, bounds(shape.find("{%s}Bounds" % DC)), outline, container)
        if kind in ("participant", "lane"):
            x1, y1, x2, y2 = nodes[identifier].box
            header = (x1, y1, min(x1 + 30, x2), y2)
            if shape.get("isHorizontal") == "false":
                header = (x1, y1, x2, min(y1 + 30, y2))
            labels.append(Node(identifier + ":header", header, "rect", False))
    for owner in list(plane):
        label = owner.find("{%s}BPMNLabel/{%s}Bounds" % (BPMNDI, DC))
        if label is not None:
            labels.append(Node(ref(owner.get("bpmnElement")) + ":label", bounds(label), "rect", False))

    def visible(identifier: str) -> str:
        element = index.get(identifier)
        while element is not None:
            if element.get("id") in nodes:
                return element.get("id")
            element = parents.get(element)
        return identifier

    for element in plane.findall("{%s}BPMNEdge" % BPMNDI):
        identifier = ref(element.get("bpmnElement"))
        if identifier not in index:
            raise ValueError("Edge references missing BPMN element: " + identifier)
        semantic = index[identifier]
        source, target = ref(semantic.get("sourceRef")), ref(semantic.get("targetRef"))
        if local(semantic) in ("dataInputAssociation", "dataOutputAssociation"):
            sources = [ref(child.text) for child in semantic if local(child) == "sourceRef"]
            targets = [ref(child.text) for child in semantic if local(child) == "targetRef"]
            source = sources[0] if sources else ""
            target = targets[0] if targets else ""
            parent = parents.get(semantic)
            if parent is not None:
                if local(semantic) == "dataInputAssociation":
                    target = parent.get("id", "")
                else:
                    source = parent.get("id", "")
        for attribute in ("sourceElement", "targetElement"):
            linked = index.get(ref(element.get(attribute)))
            if linked is not None:
                if attribute == "sourceElement":
                    source = ref(linked.get("bpmnElement"))
                else:
                    target = ref(linked.get("bpmnElement"))
        points = [(number(p.get("x")), number(p.get("y"))) for p in element.findall("{%s}waypoint" % DI)]
        edges.append(Edge(identifier, visible(source), visible(target), points, element))
    return nodes, labels, edges


def tidy_routes(root: Any, plane: Any = None) -> dict[str, Any]:
    """Mutate only edge waypoints; return unresolved conflicts for each DI plane.

    Args:
        root: Parsed BPMN definitions element (lxml or ElementTree).
        plane: Optional BPMNPlane element. Omission processes every plane.
    """
    planes = [plane] if plane is not None else root.findall(".//{%s}BPMNPlane" % BPMNDI)
    report: dict[str, Any] = {"status": "routed", "pass": False, "planes": [], "limitations": ["Routing checks existing DI label bounds only. Rendered-text audit and visual review remain required.", "Search is bounded and does not guarantee a crossing-free embedding with fixed nodes."]}
    if not planes:
        raise ValueError("No BPMNPlane found")
    for current in planes:
        nodes, labels, edges = read_plane(root, current)
        initial = conflicts(edges, nodes, labels)
        budget = SearchBudget(200000)
        originals = {edge.identifier: list(edge.points) for edge in edges}
        # A moved document invalidates its old anchors. Re-dock before search so
        # a failed insertion can never restore a route at the document's old site.
        for edge in edges:
            if edge.source not in nodes or edge.target not in nodes:
                continue
            detached = (len(edge.points) < 2 or
                        not on_outline(edge.points[0], nodes[edge.source]) or
                        not on_outline(edge.points[-1], nodes[edge.target]))
            if detached:
                route = search_route(edge, nodes, labels, [], budget=budget)
                if route is None:
                    candidates = []
                    for source, start in ports(nodes[edge.source]):
                        for target, end in ports(nodes[edge.target]):
                            for bend in ((start[0], end[1]), (end[0], start[1])):
                                points = simplify([source, start, bend, end, target])
                                trial = Edge(edge.identifier, edge.source, edge.target, points, edge.element)
                                candidates.append((len(conflicts([trial], nodes, labels)), path_length(points), points))
                    # Even an obstructed path has correct anchors and explicit
                    # conflicts; it must not be mistaken for a valid layout.
                    route = min(candidates, key=lambda candidate: candidate[:2])[2]
                edge.points = route
        baseline = {edge.identifier: list(edge.points) for edge in edges}
        best = baseline.copy()
        best_issues = conflicts(edges, nodes, labels)
        attempts = 0
        if best_issues:
            dirty = {identifier for issue in best_issues for identifier in issue["edges"]}
            stable = [edge for edge in edges if edge.identifier not in dirty]
            pending = [edge for edge in edges if edge.identifier in dirty]
            # Different deterministic insertion orders provide a small rip-up budget.
            association_ids = {element.get("id") for element in root.iter()
                               if local(element).endswith("Association") or local(element) == "association"}
            def quality(issues: list[dict[str, Any]]) -> tuple[int, int]:
                core = sum(all(identifier not in association_ids for identifier in issue["edges"]) for issue in issues)
                return core, len(issues)

            boundary_ids = {element.get("id") for element in root.iter() if local(element) == "boundaryEvent"}
            boundary_first = sorted(edges, key=lambda e: (e.source not in boundary_ids, e.identifier in association_ids, e.identifier))
            schedules = [(stable, pending, GAP), (stable, list(reversed(pending)), GAP),
                         (stable, sorted(pending, key=lambda e: (-path_length(e.points), e.identifier)), 4.0),
                         ([], boundary_first, 4.0), ([], edges, GAP),
                         ([], list(reversed(edges)), 4.0),
                         ([], sorted(edges, key=lambda e: (e.identifier not in association_ids, e.identifier)), 4.0)]
            for retained, schedule, clearance in schedules:
                if budget.remaining <= 0:
                    break
                attempts += 1
                for edge in edges:
                    edge.points = list(baseline[edge.identifier])
                fixed = list(retained)
                for edge in schedule:
                    route = search_route(edge, nodes, labels, fixed, clearance=clearance, budget=budget)
                    if route is not None:
                        edge.points = route
                        fixed.append(edge)
                found = conflicts(edges, nodes, labels)
                if quality(found) < quality(best_issues):
                    best = {edge.identifier: list(edge.points) for edge in edges}
                    best_issues = found
                if not found:
                    break
            # A global insertion order may improve the layout enough to unlock a
            # final local repair. Recompute the dirty set from that best result.
            for reverse in (False, True):
                if not best_issues or budget.remaining <= 0:
                    break
                attempts += 1
                for edge in edges:
                    edge.points = list(best[edge.identifier])
                dirty = {identifier for issue in best_issues for identifier in issue["edges"]}
                fixed = [edge for edge in edges if edge.identifier not in dirty]
                pending = sorted((edge for edge in edges if edge.identifier in dirty), key=lambda e: e.identifier, reverse=reverse)
                for edge in pending:
                    route = search_route(edge, nodes, labels, fixed, clearance=4.0, budget=budget)
                    if route is not None:
                        edge.points = route
                        fixed.append(edge)
                found = conflicts(edges, nodes, labels)
                if quality(found) < quality(best_issues):
                    best = {edge.identifier: list(edge.points) for edge in edges}
                    best_issues = found
        changed = []
        for edge in edges:
            edge.points = best[edge.identifier]
            if edge.points != originals[edge.identifier]:
                changed.append(edge.identifier)
                old = edge.element.findall("{%s}waypoint" % DI)
                position = list(edge.element).index(old[0]) if old else 0
                for waypoint in old:
                    edge.element.remove(waypoint)
                for offset, (x, y) in enumerate(edge.points):
                    waypoint = edge.element.makeelement("{%s}waypoint" % DI, {"x": format(x, ".10g"), "y": format(y, ".10g")})
                    edge.element.insert(position + offset, waypoint)
        report["planes"].append({"planeId": current.get("id"), "edges": len(edges), "attempts": attempts, "changed": changed, "initial_conflicts": len(initial), "search_expansions": budget.used, "budget_exhausted": budget.remaining <= 0, "remaining_conflicts": best_issues})
    unresolved = sum(len(item["remaining_conflicts"]) for item in report["planes"])
    report["remaining_conflicts"] = unresolved
    report["routes_clear"] = unresolved == 0
    report["status"] = "needs_layout" if unresolved else "routed"
    return report


def main() -> int:
    from lxml import etree

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    tree = etree.parse(str(args.input), etree.XMLParser(remove_blank_text=False, resolve_entities=False, no_network=True))
    report = tidy_routes(tree.getroot())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(args.output), encoding="UTF-8", xml_declaration=True)
    content = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(content + "\n", encoding="utf-8")
    print(content)
    return 1 if report["remaining_conflicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
