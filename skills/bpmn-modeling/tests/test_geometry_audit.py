import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as E

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'geometry_audit.py'
spec=importlib.util.spec_from_file_location('geometry_audit',SCRIPT)
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
NS={'b':'http://www.omg.org/spec/BPMN/20100524/MODEL','bd':g.BPMNDI,'dc':g.DC,'di':g.DI}
for prefix,uri in NS.items(): E.register_namespace(prefix,uri)
def element(tag,parent=None,**attributes):
    prefix,name=tag.split(':');e=E.Element('{'+NS[prefix]+'}'+name,{k:str(v) for k,v in attributes.items()})
    if parent is not None: parent.append(e)
    return e

def model(nodes,edges):
    root=element('b:definitions',id='Definitions',targetNamespace='urn:test')
    process=element('b:process',root,id='Process',isExecutable='false')
    diagram=element('bd:BPMNDiagram',root,id='Diagram'); plane=element('bd:BPMNPlane',diagram,id='Plane',bpmnElement='Process')
    for identifier,kind,box,*extra in nodes:
        attributes=extra[0] if extra else {}
        element('b:'+kind,process,id=identifier,**attributes)
        shape=element('bd:BPMNShape',plane,id=identifier+'_di',bpmnElement=identifier)
        element('dc:Bounds',shape,**dict(zip(['x','y','width','height'],box)))
    for identifier,source,target,points in edges:
        element('b:sequenceFlow',process,id=identifier,sourceRef=source,targetRef=target)
        edge=element('bd:BPMNEdge',plane,id=identifier+'_di',bpmnElement=identifier)
        for x,y in points:element('di:waypoint',edge,x=x,y=y)
    return root

class GeometryTests(unittest.TestCase):
    def check(self,root,labels=None):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.bpmn'; E.ElementTree(root).write(p,encoding='utf-8',xml_declaration=True)
            render=None
            if labels is not None:
                render=Path(tmp)/'geometry.json';render.write_text(json.dumps({'sha256':g.hashlib.sha256(p.read_bytes()).hexdigest(),'diagrams':[{'planeId':'Plane','labels':labels}]}),encoding='utf-8')
            return g.audit(p,render)
    def categories(self,root):return {i['category'] for i in self.check(root)['issues']}
    def base(self): return model([('A','task',(0,0,100,80)),('B','task',(200,0,100,80))],[('F','A','B',[(100,40),(200,40)])])
    def test_clean_no_render_is_incomplete(self):
        report=self.check(self.base());self.assertEqual(report['status'],'incomplete');self.assertEqual(report['summary']['blocking_issues'],0)
    def test_clean_measured_render_passes(self):self.assertEqual(self.check(self.base(),[])['status'],'pass')
    def test_named_element_without_measurement_incomplete(self):
        root=self.base();root.find('.//b:task',NS).set('name','Action');self.assertEqual(self.check(root,[])['status'],'incomplete')
    def test_node_overlap(self):self.assertIn('node_overlap',self.categories(model([('A','task',(0,0,100,80)),('B','task',(99,30,100,80))],[])))
    def test_touching_nodes_do_not_overlap(self):self.assertNotIn('node_overlap',self.categories(model([('A','task',(0,0,100,80)),('B','task',(100,0,100,80))],[])))
    def test_diamond_empty_corner_is_not_collision(self):
        root=model([('A','exclusiveGateway',(0,0,100,100)),('B','task',(0,0,15,15))],[]);self.assertNotIn('node_overlap',self.categories(root))
    def test_line_at_diamond_corner_does_not_cross_node(self):
        root=model([('A','task',(-100,-35,30,80)),('B','task',(170,-35,30,80)),('G','exclusiveGateway',(0,0,100,100))],[('F','A','B',[(-70,5),(20,5),(20,-40),(170,-40),(170,5)])]);self.assertNotIn('edge_crosses_node',self.categories(root))
    def test_line_through_diamond_is_reported(self):
        root=model([('A','task',(-100,10,30,80)),('B','task',(170,10,30,80)),('G','exclusiveGateway',(0,0,100,100))],[('F','A','B',[(-70,50),(170,50)])]);self.assertIn('edge_crosses_node',self.categories(root))
    def test_circle_corner_endpoint_detached(self):
        root=model([('A','startEvent',(0,0,36,36)),('B','task',(100,-40,100,80))],[('F','A','B',[(36,0),(100,0)])]);self.assertIn('detached_endpoint',self.categories(root))
    def test_circle_cardinal_endpoint_attached(self):
        root=model([('A','startEvent',(0,0,36,36)),('B','task',(100,-22,100,80))],[('F','A','B',[(36,18),(100,18)])]);self.assertNotIn('detached_endpoint',self.categories(root))
    def test_boundary_attachment_allowed(self):
        root=model([('A','task',(0,0,100,80)),('E','boundaryEvent',(32,62,36,36),{'attachedToRef':'A'})],[]);self.assertNotIn('node_overlap',self.categories(root))
    def test_boundary_attachment_inside_task_reported(self):
        root=model([('A','task',(0,0,100,80)),('E','boundaryEvent',(32,22,36,36),{'attachedToRef':'A'})],[]);self.assertIn('invalid_boundary_attachment',self.categories(root))
    def test_diagonal_reported(self):
        root=model([('A','task',(0,0,100,80)),('B','task',(200,80,100,80))],[('F','A','B',[(100,40),(200,120)])]);self.assertIn('nonorthogonal_path',self.categories(root))
    def test_edge_crossing_reported(self):
        root=model([('A','task',(0,0,100,80)),('B','task',(300,0,100,80)),('C','task',(150,-200,100,80)),('D','task',(150,200,100,80))],[('F','A','B',[(100,40),(300,40)]),('G','C','D',[(200,-120),(200,200)])]);self.assertIn('edge_crossing',self.categories(root))
    def test_shared_segment_is_rejected(self):
        root=model([('A','task',(0,0,100,80)),('B','task',(200,0,100,80)),('C','task',(0,200,100,80))],[('F','A','B',[(100,40),(200,40)]),('G','A','C',[(100,40),(120,40),(120,240),(100,240)])]);self.assertIn('edge_overlap',self.categories(root))
    def test_shared_endpoint_only_clean(self):
        root=model([('A','exclusiveGateway',(0,0,50,50)),('B','task',(200,-15,100,80)),('C','task',(0,200,100,80))],[('F','A','B',[(50,25),(200,25)]),('G','A','C',[(50,25),(50,200)])]);self.assertNotIn('edge_crossing',self.categories(root))
    def test_actual_label_crossing_edge(self):
        labels=[{'id':'label','ownerId':'F','internal':False,'text':'Condition','bounds':{'x':140,'y':35,'width':40,'height':20}}]
        report=self.check(self.base(),labels);self.assertIn('label_overlaps_edge',{i['category'] for i in report['issues']})
    def test_internal_label_does_not_collide_with_owner(self):
        labels=[{'id':'A','ownerId':'A','internal':True,'text':'Task','bounds':{'x':20,'y':30,'width':50,'height':20}}]
        self.assertEqual(self.check(self.base(),labels)['status'],'pass')
    def test_label_label_overlap(self):
        labels=[{'id':str(i),'ownerId':'F','internal':False,'text':'Text','bounds':{'x':120+i*5,'y':100,'width':40,'height':20}} for i in range(2)]
        report=self.check(self.base(),labels);self.assertIn('label_overlap',{i['category'] for i in report['issues']})
    def test_zero_width_rejected(self):self.assertIn('invalid_bounds',self.categories(model([('A','task',(0,0,0,80))],[])))
    def test_nonfinite_waypoint_rejected(self):
        root=self.base();root.find('.//di:waypoint',NS).set('x','NaN');self.assertIn('invalid_waypoints',self.categories(root))
    def test_stale_render_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.bpmn';E.ElementTree(self.base()).write(p)
            r=Path(tmp)/'geometry.json';r.write_text(json.dumps({'sha256':'old','diagrams':[]}))
            with self.assertRaisesRegex(ValueError,'SHA-256'):g.audit(p,r)

if __name__=='__main__':unittest.main(verbosity=2)
