import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as E

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'readability_audit.py'
spec=importlib.util.spec_from_file_location('readability_audit',SCRIPT)
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
NS={'b':'http://www.omg.org/spec/BPMN/20100524/MODEL','bd':'http://www.omg.org/spec/BPMN/20100524/DI','dc':'http://www.omg.org/spec/DD/20100524/DC','di':'http://www.omg.org/spec/DD/20100524/DI','bioc':'http://bpmn.io/schema/bpmn/biocolor/1.0'}
for prefix,uri in NS.items(): E.register_namespace(prefix,uri)
def element(tag,parent=None,**attributes):
    prefix,name=tag.split(':');e=E.Element('{'+NS[prefix]+'}'+name,{(('{'+NS[k.split('__')[0]]+'}'+k.split('__')[1]) if '__' in k else k):str(v) for k,v in attributes.items()})
    if parent is not None: parent.append(e)
    return e

def model(nodes,edges,lanes=None,stores=()):
    root=element('b:definitions',id='Definitions',targetNamespace='urn:test')
    process=element('b:process',root,id='Process',isExecutable='false')
    diagram=element('bd:BPMNDiagram',root,id='Diagram'); plane=element('bd:BPMNPlane',diagram,id='Plane',bpmnElement='Process')
    if lanes is not None:
        lane_set=element('b:laneSet',process,id='LaneSet')
        for lane_id,refs in lanes.items():
            lane=element('b:lane',lane_set,id=lane_id,name=lane_id)
            for target in refs: element('b:flowNodeRef',lane).text=target
    for identifier,kind,x,*extra in nodes:
        attributes=extra[0] if extra else {}
        shape_attributes=attributes.pop('shape',{})
        element('b:'+kind,process,id=identifier,**attributes)
        shape=element('bd:BPMNShape',plane,id=identifier+'_di',bpmnElement=identifier,**shape_attributes)
        element('dc:Bounds',shape,x=x,y=0,width=36,height=36)
    for identifier,name in stores: element('b:dataStoreReference',process,id=identifier,name=name)
    for identifier,source,target,points in edges:
        element('b:sequenceFlow',process,id=identifier,sourceRef=source,targetRef=target)
        edge=element('bd:BPMNEdge',plane,id=identifier+'_di',bpmnElement=identifier)
        for x,y in points: element('di:waypoint',edge,x=x,y=y)
    return root

class ReadabilityTests(unittest.TestCase):
    def check(self,root):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.bpmn'; E.ElementTree(root).write(p,encoding='utf-8',xml_declaration=True)
            return r.audit(p)
    def categories(self,root): return {i['category'] for i in self.check(root)['issues'] if i['severity']=='error'}
    def chain(self): return [('S','startEvent',0),('A','task',100),('B','task',200),('E','endEvent',300,{'name':'Готово'})]
    def test_clean_chain_passes(self):
        root=model(self.chain(),[('F1','S','A',[(36,18),(100,18)]),('F2','A','B',[(136,18),(200,18)]),('F3','B','E',[(236,18),(300,18)])])
        self.assertTrue(self.check(root)['pass'])
    def test_two_arrows_into_end_is_implicit_merge(self):
        root=model(self.chain(),[('F1','S','A',[(36,18),(100,18)]),('F2','A','E',[(136,18),(300,18)]),('F3','B','E',[(236,18),(300,18)])])
        self.assertIn('implicit_merge',self.categories(root))
    def test_merge_gateway_may_have_several_inputs(self):
        nodes=[('S','startEvent',0),('A','task',100),('G','exclusiveGateway',200),('E','endEvent',300)]
        root=model(nodes,[('F1','S','A',[(36,18),(100,18)]),('F2','A','G',[(136,18),(200,18)]),('F3','S','G',[(18,36),(18,60),(218,60),(218,36)]),('F4','G','E',[(236,18),(300,18)])])
        self.assertNotIn('implicit_merge',self.categories(root))
    def test_arrow_to_the_left_outside_loop_is_backward(self):
        nodes=[('S','startEvent',300),('E','endEvent',0)]
        root=model(nodes,[('F1','S','E',[(300,18),(36,18)])])
        self.assertIn('backward_flow',self.categories(root))
    def test_loop_back_may_run_left(self):
        nodes=[('S','startEvent',0),('G','exclusiveGateway',100),('A','task',200),('H','exclusiveGateway',300),('E','endEvent',400)]
        edges=[('F1','S','G',[(36,18),(100,18)]),('F2','G','A',[(136,18),(200,18)]),('F3','A','H',[(236,18),(300,18)]),('F4','H','E',[(336,18),(400,18)]),('F5','H','G',[(318,36),(318,80),(118,80),(118,36)])]
        self.assertNotIn('backward_flow',self.categories(model(nodes,edges)))
    def test_identical_end_names(self):
        nodes=[('S','startEvent',0),('E1','endEvent',100,{'name':'ПТиУ привязано'}),('E2','endEvent',200,{'name':'ПТиУ  привязано '})]
        self.assertIn('duplicate_end_name',self.categories(model(nodes,[])))
    def test_duplicate_data_store(self):
        root=model([('S','startEvent',0)],[],stores=[('D1','УПП — отчёт ПТиУ'),('D2','УПП — отчёт ПТиУ')])
        self.assertIn('duplicate_data_store',self.categories(root))
    def test_lane_reference_to_deleted_element(self):
        root=model([('S','startEvent',0)],[],lanes={'Сервис':['S','Deleted_End']})
        self.assertIn('dangling_lane_ref',self.categories(root))
    def test_green_end_event(self):
        root=model([('E','endEvent',0,{'shape':{'bioc__fill':'#c8e6c9'}})],[])
        self.assertIn('event_color',self.categories(root))
    def test_red_end_event_passes(self):
        root=model([('E','endEvent',0,{'shape':{'bioc__fill':'#ffcdd2'}})],[])
        self.assertNotIn('event_color',self.categories(root))

if __name__=='__main__': unittest.main()
