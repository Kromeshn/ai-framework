from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest
from lxml import etree as ET

SCRIPTS = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import route_tidy as rt
import geometry_audit


MODEL = 'http://www.omg.org/spec/BPMN/20100524/MODEL'


def model():
    root = ET.Element('{%s}definitions' % MODEL, nsmap={'bpmn': MODEL, 'bpmndi': rt.BPMNDI, 'dc': rt.DC, 'di': rt.DI}, id='Definitions', targetNamespace='urn:route-test')
    process = ET.SubElement(root, '{%s}process' % MODEL, id='Process', isExecutable='false')
    diagram = ET.SubElement(root, '{%s}BPMNDiagram' % rt.BPMNDI, id='Diagram')
    plane = ET.SubElement(diagram, '{%s}BPMNPlane' % rt.BPMNDI, id='Plane', bpmnElement='Process')
    return root, process, plane


def node(process, plane, identifier, kind, x, y, width, height, **attrs):
    semantic = ET.SubElement(process, '{%s}%s' % (MODEL, kind), id=identifier, **attrs)
    shape = ET.SubElement(plane, '{%s}BPMNShape' % rt.BPMNDI, id=identifier+'_di', bpmnElement=identifier)
    ET.SubElement(shape, '{%s}Bounds' % rt.DC, x=str(x), y=str(y), width=str(width), height=str(height))
    return semantic, shape


def edge(process, plane, identifier, source, target, points):
    semantic = ET.SubElement(process, '{%s}sequenceFlow' % MODEL, id=identifier, sourceRef=source, targetRef=target)
    di = ET.SubElement(plane, '{%s}BPMNEdge' % rt.BPMNDI, id=identifier+'_di', bpmnElement=identifier)
    for x,y in points:
        ET.SubElement(di, '{%s}waypoint' % rt.DI, x=str(x), y=str(y))
    return semantic, di


def fingerprint(process):
    return ET.tostring(process, method='c14n')


class RouteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='bpmn-route-tests-')
        self.addCleanup(temporary.cleanup)
        self.output_dir = Path(temporary.name)

    def verify(self, name, root, process):
        before = fingerprint(process)
        shape_bounds = [ET.tostring(shape) for shape in root.findall('.//{%s}BPMNShape' % rt.BPMNDI)]
        input_path = self.output_dir / (name+'.before.bpmn')
        input_path.write_bytes(ET.tostring(root, xml_declaration=True, encoding='UTF-8'))
        report = rt.tidy_routes(root)
        output_path = self.output_dir / (name+'.after.bpmn')
        output_path.write_bytes(ET.tostring(root, xml_declaration=True, encoding='UTF-8'))
        (self.output_dir / (name+'.json')).write_text(__import__('json').dumps(report, indent=2), encoding='utf-8')
        self.assertEqual(before, fingerprint(process))
        self.assertEqual(shape_bounds, [ET.tostring(shape) for shape in root.findall('.//{%s}BPMNShape' % rt.BPMNDI)])
        self.assertTrue(report['routes_clear'], report)
        audit = geometry_audit.audit(output_path)
        self.assertFalse([i for i in audit['issues'] if i['severity'] == 'error'], audit['issues'])
        unchanged = ET.tostring(root)
        repeated = rt.tidy_routes(root)
        self.assertTrue(repeated['routes_clear'])
        self.assertEqual(unchanged, ET.tostring(root))

    def test_four_inclusive_branches(self):
        root, process, plane = model()
        node(process, plane, 'Split', 'inclusiveGateway', 100, 240, 50, 50)
        node(process, plane, 'Join', 'inclusiveGateway', 640, 240, 50, 50)
        for i, y in enumerate((30, 190, 350, 510)):
            node(process, plane, 'Task'+str(i), 'task', 330, y, 100, 80)
            edge(process, plane, 'Out'+str(i), 'Split', 'Task'+str(i), [(150,265),(240,265),(240,y+40),(330,y+40)])
            edge(process, plane, 'In'+str(i), 'Task'+str(i), 'Join', [(430,y+40),(540,y+40),(540,265),(640,265)])
        self.verify('four_branches', root, process)

    def test_boundary_timer_and_loop(self):
        root, process, plane = model()
        node(process, plane, 'A', 'task', 100, 200, 100, 80)
        node(process, plane, 'B', 'task', 340, 200, 100, 80)
        node(process, plane, 'C', 'task', 580, 200, 100, 80)
        timer, _ = node(process, plane, 'Timer', 'boundaryEvent', 162, 262, 36, 36, attachedToRef='A')
        ET.SubElement(timer, '{%s}timerEventDefinition' % MODEL)
        edge(process, plane, 'AB', 'A', 'B', [(200,240),(340,240)])
        edge(process, plane, 'BC', 'B', 'C', [(440,240),(580,240)])
        edge(process, plane, 'Loop', 'B', 'A', [(390,280),(390,340),(150,340),(150,280)])
        edge(process, plane, 'Timeout', 'Timer', 'C', [(180,298),(180,360),(630,360),(630,280)])
        self.verify('timer_loop', root, process)

    def test_edge_label_is_obstacle(self):
        root, process, plane = model()
        node(process, plane, 'Start', 'startEvent', 80, 120, 36, 36)
        node(process, plane, 'End', 'endEvent', 500, 120, 36, 36)
        semantic, di = edge(process, plane, 'Flow', 'Start', 'End', [(116,138),(500,138)])
        semantic.set('name', 'A sufficiently long condition')
        label = ET.SubElement(di, '{%s}BPMNLabel' % rt.BPMNDI)
        ET.SubElement(label, '{%s}Bounds' % rt.DC, x='240', y='120', width='120', height='30')
        self.verify('label_obstacle', root, process)

    def test_moved_document_association(self):
        root, process, plane = model()
        task, _ = node(process, plane, 'Task', 'task', 100, 300, 100, 80)
        node(process, plane, 'Document', 'dataObjectReference', 250, 30, 36, 50)
        association = ET.SubElement(task, '{%s}dataOutputAssociation' % MODEL, id='Output')
        ET.SubElement(association, '{%s}sourceRef' % MODEL).text = 'DataOutput'
        ET.SubElement(association, '{%s}targetRef' % MODEL).text = 'Document'
        io = ET.SubElement(task, '{%s}ioSpecification' % MODEL, id='IO')
        ET.SubElement(io, '{%s}dataOutput' % MODEL, id='DataOutput')
        di = ET.SubElement(plane, '{%s}BPMNEdge' % rt.BPMNDI, id='Output_di', bpmnElement='Output')
        for x,y in [(150,300),(150,200),(250,200)]:
            ET.SubElement(di, '{%s}waypoint' % rt.DI, x=str(x), y=str(y))
        self.verify('document_moved', root, process)

    def test_narrow_free_corridor_and_budget(self):
        root, process, plane = model()
        node(process, plane, 'Source', 'task', 80, 95, 40, 40)
        node(process, plane, 'Target', 'task', 300, 95, 40, 40)
        for identifier, x, y, width, height in [
            ('UpperLeft', 200, 20, 40, 90), ('LowerLeft', 200, 120, 40, 100),
            ('Top', 200, 0, 220, 20), ('Bottom', 200, 220, 220, 20),
            ('Right', 380, 20, 40, 200),
        ]:
            node(process, plane, identifier, 'task', x, y, width, height)
        edge(process, plane, 'Flow', 'Source', 'Target', [(120,115),(300,115)])
        nodes, labels, edges = rt.read_plane(root, plane)
        self.assertIsNone(rt.search_route(edges[0], nodes, labels, [], clearance=8))
        route = rt.search_route(edges[0], nodes, labels, [], clearance=4)
        self.assertIsNotNone(route)
        edges[0].points = route
        self.assertFalse(rt.conflicts(edges, nodes, labels))
        budget = rt.SearchBudget(2)
        self.assertIsNone(rt.search_route(edges[0], nodes, labels, [], budget=budget))
        self.assertEqual(budget.used, 2)
        self.assertEqual(budget.remaining, 0)

    def test_lane_header_is_obstacle(self):
        root, process, plane = model()
        node(process, plane, 'Lane', 'lane', 100, 200, 600, 200)
        node(process, plane, 'A', 'task', 200, 250, 100, 80)
        node(process, plane, 'B', 'task', 500, 250, 100, 80)
        edge(process, plane, 'Flow', 'A', 'B', [(250,330),(110,330),(110,180),(550,180),(550,250)])
        self.verify('lane_header', root, process)

    def test_unresolved_reports_failure_without_semantic_changes(self):
        root, process, plane = model()
        node(process, plane, 'A', 'task', 100, 100, 100, 80)
        node(process, plane, 'B', 'task', 90, 90, 120, 100)
        edge(process, plane, 'Impossible', 'A', 'B', [(500,500),(600,500)])
        before = fingerprint(process)
        report = rt.tidy_routes(root)
        self.assertFalse(report['routes_clear'])
        self.assertFalse(report['pass'])
        self.assertEqual(before, fingerprint(process))
        nodes, _, edges = rt.read_plane(root, plane)
        self.assertTrue(rt.on_outline(edges[0].points[0], nodes['A']))
        self.assertTrue(rt.on_outline(edges[0].points[-1], nodes['B']))
        self.assertNotIn('detached_endpoint', {issue['category'] for item in report['planes'] for issue in item['remaining_conflicts']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
