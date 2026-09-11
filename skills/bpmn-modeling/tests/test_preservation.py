"""Regression checks for lossless DI replacement and geometry-only edits."""
import copy
import sys
import unittest
import tempfile
import subprocess
from pathlib import Path
from lxml import etree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from bpmn_layout import semantic_digest, transfer_di, prepare_engine_input, fit_measured_labels, NS

SOURCE = '''<b:definitions xmlns:b="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:d="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:custom="urn:custom" id="Definitions" custom:engine="kept"><b:process id="P" isExecutable="false"><b:documentation>Exact business document</b:documentation><b:extensionElements><custom:setting key="original"/></b:extensionElements><b:laneSet id="LS"><b:lane id="Lower"/><b:lane id="Upper"/></b:laneSet><b:task id="T" name="Original task"><b:extensionElements><custom:value>  Preserve whitespace  </custom:value></b:extensionElements></b:task><b:boundaryEvent id="Timer" attachedToRef="T" cancelActivity="false"><b:timerEventDefinition id="TD"><b:timeDuration>P2D</b:timeDuration></b:timerEventDefinition></b:boundaryEvent></b:process><d:BPMNDiagram id="OldDiagram"><d:BPMNPlane id="OldPlane" bpmnElement="P"><d:BPMNShape id="OldT" bpmnElement="T"><dc:Bounds x="10" y="20" width="220" height="104"/></d:BPMNShape><d:BPMNShape id="OldL" bpmnElement="Lower"><dc:Bounds x="0" y="300" width="600" height="200"/></d:BPMNShape><d:BPMNShape id="OldU" bpmnElement="Upper"><dc:Bounds x="0" y="100" width="600" height="200"/></d:BPMNShape></d:BPMNPlane></d:BPMNDiagram></b:definitions>'''

class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.root=ET.fromstring(SOURCE.encode())
    def test_replace_di_preserves_unknown_extensions_timer_and_text(self):
        before=semantic_digest(self.root)
        generated=copy.deepcopy(self.root)
        generated.find('.//dc:Bounds',NS).set('x','1234')
        # Simulate a moddle result that dropped an unknown extension.
        generated.find('b:process/b:extensionElements',NS).clear()
        transfer_di(self.root,generated)
        self.assertEqual(before,semantic_digest(self.root))
        self.assertEqual(self.root.find('.//{urn:custom}value').text,'  Preserve whitespace  ')
        self.assertEqual(self.root.find('.//b:boundaryEvent',NS).get('cancelActivity'),'false')
    def test_semantic_change_is_detected(self):
        before=semantic_digest(self.root)
        self.root.find('.//b:timeDuration',NS).text='P3D'
        self.assertNotEqual(before,semantic_digest(self.root))
    def test_engine_lane_sort_does_not_mutate_business_source(self):
        before=ET.tostring(self.root)
        engine=prepare_engine_input(self.root)
        self.assertEqual([x.get('id') for x in engine.findall('.//b:lane',NS)],['Upper','Lower'])
        self.assertEqual(before,ET.tostring(self.root))
    def test_report_directory_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            source=folder/'candidate.bpmn'
            source.write_text(SOURCE,encoding='utf-8')
            before=source.read_bytes()
            script=Path(__file__).resolve().parents[1]/'scripts'/'bpmn_layout.py'
            result=subprocess.run([sys.executable,str(script),str(source),'--report-dir',str(folder),'--reflow'],capture_output=True)
            self.assertEqual(result.returncode,2)
            self.assertIn(b'Report directory must not contain',result.stderr)
            self.assertEqual(before,source.read_bytes())
    def test_missing_generated_di_is_rejected(self):
        empty=ET.fromstring('<definitions/>')
        with self.assertRaises(ValueError): transfer_di(copy.deepcopy(self.root),empty)

if __name__=='__main__':unittest.main()