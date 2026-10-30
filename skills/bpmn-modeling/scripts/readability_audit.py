#!/usr/bin/env python3
"""Read-only readability audit of BPMN XML + DI; stdlib only.

Complements geometry_audit.py: that script finds overlaps and crossings, this one
finds style defects that are geometrically clean but hard to read.

Exit 0: no blocking issues. Exit 1: blocking issues. Exit 2: input error.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

BPMN = 'http://www.omg.org/spec/BPMN/20100524/MODEL'
BACK_TOL = 10.0
CONTAINERS = ('process', 'subProcess', 'transaction', 'adHocSubProcess')
FLOW_NODE_SUFFIXES = ('Task', 'task', 'Event', 'Gateway', 'subProcess', 'transaction', 'callActivity', 'adHocSubProcess')
ACTIVITY_SUFFIXES = ('Task', 'task', 'subProcess', 'transaction', 'callActivity', 'adHocSubProcess')
FILL_ATTRS = ('fill', 'background-color')


def local(element):
    return element.tag.rsplit('}', 1)[-1]


def ref(value):
    return (value or '').split(':')[-1]


def norm(text):
    return re.sub(r'\s+', ' ', (text or '').strip().lower().replace('ё', 'е'))


def is_flow_node(element):
    name = local(element)
    return name != 'sequenceFlow' and name.endswith(FLOW_NODE_SUFFIXES)


def is_activity(element):
    return local(element).endswith(ACTIVITY_SUFFIXES)


def parse_color(value):
    value = (value or '').strip().lower()
    match = re.fullmatch(r'#([0-9a-f]{6})', value) or re.fullmatch(r'#([0-9a-f]{3})', value)
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = ''.join(c * 2 for c in digits)
        return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))
    match = re.fullmatch(r'rgba?\((\d+),\s*(\d+),\s*(\d+).*\)', value)
    return tuple(int(match.group(i)) for i in (1, 2, 3)) if match else None


def hue_family(rgb):
    r, g, b = rgb
    if g > r + 15 and g > b + 5:
        return 'green'
    if r > g + 15 and r > b + 15:
        return 'red'
    return 'other'


def shape_fill(shape):
    for key, value in shape.attrib.items():
        if key.rsplit('}', 1)[-1] in FILL_ATTRS:
            return value
    return None


def audit(path):
    root = ET.parse(path).getroot()
    by_id = {e.get('id'): e for e in root.iter() if e.get('id')}
    parent = {child: element for element in root.iter() for child in element}
    issues = []

    def issue(category, ids, message, severity='error', **detail):
        issues.append({'category': category, 'severity': severity, 'ids': ids, 'message': message, **detail})

    shapes, edges = {}, {}
    for element in root.iter():
        if local(element) == 'BPMNShape':
            shapes[ref(element.get('bpmnElement'))] = element
        elif local(element) == 'BPMNEdge':
            points = [(float(w.get('x')), float(w.get('y'))) for w in element if local(w) == 'waypoint']
            edges[ref(element.get('bpmnElement'))] = points

    containers = [e for e in root.iter() if local(e) in CONTAINERS]
    any_lanes = any(local(c) == 'laneSet' for container in containers for c in container)

    for container in containers:
        cid = container.get('id')
        children = list(container)
        nodes = {c.get('id'): c for c in children if is_flow_node(c)}
        flows = [c for c in children if local(c) == 'sequenceFlow']
        incoming, outgoing = {}, {}
        for flow in flows:
            incoming.setdefault(flow.get('targetRef'), []).append(flow)
            outgoing.setdefault(flow.get('sourceRef'), []).append(flow)

        # Implicit merge: several arrows into one non-gateway element.
        for node_id, node in nodes.items():
            arrows = incoming.get(node_id, [])
            if len(arrows) > 1 and not local(node).endswith('Gateway'):
                issue('implicit_merge', [node_id] + [f.get('id') for f in arrows],
                      f'{len(arrows)} sequence flows enter {local(node)} "{node.get("name") or node_id}"; join them with a merge gateway and lead one arrow in')

        # Reachability for loop detection.
        graph = {}
        for flow in flows:
            graph.setdefault(flow.get('sourceRef'), set()).add(flow.get('targetRef'))

        def reaches(start, goal):
            seen, stack = set(), [start]
            while stack:
                current = stack.pop()
                if current == goal:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                stack.extend(graph.get(current, ()))
            return False

        for flow in flows:
            fid, points = flow.get('id'), edges.get(flow.get('id'))
            if not points or len(points) < 2:
                continue
            loop_back = reaches(flow.get('targetRef'), flow.get('sourceRef'))
            if loop_back:
                continue
            left = [(a, b) for a, b in zip(points, points[1:]) if b[0] - a[0] < -BACK_TOL]
            if left:
                issue('backward_flow', [fid, flow.get('sourceRef'), flow.get('targetRef')],
                      f'Flow "{flow.get("name") or fid}" runs right-to-left although it is not a loop back; place the target to the right of the source',
                      segments=[[list(a), list(b)] for a, b in left])

        # Identical exits.
        ends = {}
        for node_id, node in nodes.items():
            if local(node) == 'endEvent' and node.get('name'):
                ends.setdefault(norm(node.get('name')), []).append(node_id)
        for name, ids in ends.items():
            if len(ids) > 1:
                issue('duplicate_end_name', ids, f'{len(ids)} end events in one container share the name "{by_id[ids[0]].get("name")}"; keep one end and merge the branches before it')

        # Duplicated data stores.
        stores = [c for c in children if local(c) == 'dataStoreReference']
        for key_name, key in (('name', lambda s: norm(s.get('name'))), ('dataStoreRef', lambda s: s.get('dataStoreRef'))):
            groups = {}
            for store in stores:
                if key(store):
                    groups.setdefault(key(store), []).append(store.get('id'))
            for value, ids in groups.items():
                if len(ids) > 1:
                    issue('duplicate_data_store', ids, f'{len(ids)} data store shapes with the same {key_name} "{value}" in one container; draw the source once and connect it')

        # Lanes.
        lane_sets = [c for c in children if local(c) == 'laneSet']
        lane_refs = {}
        for lane_set in lane_sets:
            for lane in lane_set.iter():
                if local(lane) != 'lane':
                    continue
                for node_ref in lane:
                    if local(node_ref) != 'flowNodeRef':
                        continue
                    target = (node_ref.text or '').strip()
                    lane_refs.setdefault(target, []).append(lane.get('id'))
                    if target not in by_id:
                        issue('dangling_lane_ref', [lane.get('id'), target], f'Lane "{lane.get("name")}" references missing element {target}')
                    elif target not in nodes and local(by_id[target]) not in ('dataObjectReference', 'dataStoreReference'):
                        issue('foreign_lane_ref', [lane.get('id'), target], f'Lane "{lane.get("name")}" references {target}, which is not a direct flow node of {cid}')
        if lane_sets:
            for node_id, node in nodes.items():
                if node_id not in lane_refs and local(node) != 'boundaryEvent':
                    issue('node_outside_lanes', [node_id], f'"{node.get("name") or node_id}" is not assigned to any lane', 'warning')
        elif local(container) != 'process' and len(nodes) >= 3 and any_lanes:
            issue('subprocess_without_lane', [cid], f'Subprocess "{container.get("name") or cid}" has inner steps but no lane; show who performs them', 'warning')

        # Child outcomes versus parent branches.
        for node_id, node in nodes.items():
            if local(node) not in ('subProcess', 'transaction', 'adHocSubProcess'):
                continue
            child_ends = {norm(c.get('name')) or c.get('id') for c in node if local(c) == 'endEvent'}
            nexts = [by_id.get(f.get('targetRef')) for f in outgoing.get(node_id, [])]
            branches = len(nexts)
            if len(nexts) == 1 and nexts[0] is not None and local(nexts[0]).endswith('Gateway'):
                branches = max(1, len([f for f in flows if f.get('sourceRef') == nexts[0].get('id')]))
            if len(child_ends) > max(branches, 1):
                issue('child_outcomes_exceed_parent', [node_id],
                      f'Subprocess "{node.get("name")}" has {len(child_ends)} distinct end events, the parent continues in {branches} way(s); check that every inner outcome is used above', 'info')

    # Event colours: start green, end red.
    for node_id, shape in shapes.items():
        element = by_id.get(node_id)
        if element is None or local(element) not in ('startEvent', 'endEvent'):
            continue
        rgb = parse_color(shape_fill(shape))
        if rgb is None:
            continue
        family = hue_family(rgb)
        if local(element) == 'endEvent' and family == 'green':
            issue('event_color', [node_id], f'End event "{element.get("name")}" has a green fill; end events are red by convention')
        if local(element) == 'startEvent' and family == 'red':
            issue('event_color', [node_id], f'Start event "{element.get("name")}" has a red fill; start events are green by convention')

    blocking = sum(i['severity'] == 'error' for i in issues)
    warnings = sum(i['severity'] == 'warning' for i in issues)
    categories = sorted({i['category'] for i in issues})
    return {
        'input': str(Path(path).resolve()),
        'status': 'fail' if blocking else 'pass',
        'pass': not blocking,
        'issues': issues,
        'summary': {'blocking_issues': blocking, 'warnings': warnings, 'info': len(issues) - blocking - warnings,
                    'categories': {c: sum(i['category'] == c for i in issues) for c in categories}},
        'limitations': ['Checks style rules on XML and waypoints; it does not judge business meaning or replace looking at the PNG.'],
    }


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bpmn')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        report = audit(args.bpmn)
    except (OSError, ET.ParseError, ValueError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}, ensure_ascii=False))
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
        print(json.dumps({'status': report['status'], 'summary': report['summary'], 'output': args.output}, ensure_ascii=False))
    else:
        print(text)
    return 1 if report['summary']['blocking_issues'] else 0


if __name__ == '__main__':
    sys.exit(main())
