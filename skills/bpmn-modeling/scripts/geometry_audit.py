#!/usr/bin/env python3
"""Independent, read-only audit of BPMN DI; stdlib only.

Exit 0: no blocking geometry issues (status may be incomplete without DOM text).
Exit 1: geometry issues. Exit 2: input/report error. No semantic repairs.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

EPS = 0.05
END_TOL = 2.0
BPMNDI = 'http://www.omg.org/spec/BPMN/20100524/DI'
DC = 'http://www.omg.org/spec/DD/20100524/DC'
DI = 'http://www.omg.org/spec/DD/20100524/DI'


def local(element):
    return element.tag.rsplit('}', 1)[-1]


def ref(value):
    return (value or '').split(':')[-1]


def finite_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('coordinate is not finite')
    return number


def bounds(element):
    if element is None:
        raise ValueError('Bounds is missing')
    value = {key: finite_number(element.get(key)) for key in ('x', 'y', 'width', 'height')}
    if value['width'] <= 0 or value['height'] <= 0:
        raise ValueError('width and height must be positive')
    return value


def point_equal(a, b, tol=EPS):
    return math.dist(a, b) <= tol


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def subtract(a, b):
    return a[0] - b[0], a[1] - b[1]


def segment_hit(a, b, c, d):
    """Return a point or positive collinear overlap; works for diagonal segments."""
    r, s = subtract(b, a), subtract(d, c)
    rr, ss = sum(v*v for v in r), sum(v*v for v in s)
    if rr <= EPS*EPS or ss <= EPS*EPS:
        return None
    denominator = cross(r, s)
    delta = subtract(c, a)
    if abs(denominator) > 1e-12 * math.sqrt(rr * ss):
        t, u = cross(delta, s) / denominator, cross(delta, r) / denominator
        tolerance = EPS / max(math.sqrt(rr), math.sqrt(ss))
        if -tolerance <= t <= 1+tolerance and -tolerance <= u <= 1+tolerance:
            return 'point', (a[0] + t*r[0], a[1] + t*r[1])
        return None
    if abs(cross(delta, r)) > EPS * math.sqrt(rr):
        return None
    t0 = sum(delta[i]*r[i] for i in range(2)) / rr
    t1 = t0 + sum(s[i]*r[i] for i in range(2)) / rr
    lo, hi = max(0, min(t0, t1)), min(1, max(t0, t1))
    if (lo-hi)*math.sqrt(rr) > EPS:
        return None
    p = (a[0]+lo*r[0], a[1]+lo*r[1])
    q = (a[0]+hi*r[0], a[1]+hi*r[1])
    return ('overlap', (p, q)) if math.dist(p, q) > EPS else ('point', p)


def polygon(node):
    b = node['bounds']; x, y, w, h = (b[k] for k in ('x', 'y', 'width', 'height'))
    if node['kind'] == 'diamond':
        return [(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)]
    if node['kind'] == 'ellipse':
        return [(x+w/2+w/2*math.cos(i*math.tau/96), y+h/2+h/2*math.sin(i*math.tau/96)) for i in range(96)]
    return [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]


def inside(point, node, margin=EPS):
    b = node['bounds']; x, y, w, h = (b[k] for k in ('x', 'y', 'width', 'height'))
    px, py = point; cx, cy = x+w/2, y+h/2
    if node['kind'] == 'ellipse':
        if min(w,h)/2 <= margin:
            return False
        return ((px-cx)/(w/2-margin))**2 + ((py-cy)/(h/2-margin))**2 < 1
    if node['kind'] == 'diamond':
        return abs(px-cx)/(w/2) + abs(py-cy)/(h/2) < 1-margin/min(w/2,h/2)
    return x+margin < px < x+w-margin and y+margin < py < y+h-margin


def boundary_distance(point, node):
    b = node['bounds']; x, y, w, h = (b[k] for k in ('x', 'y', 'width', 'height'))
    if node['kind'] == 'ellipse':
        # BPMN events are circles; radial distance also supports elliptical DI.
        dx, dy = point[0]-(x+w/2), point[1]-(y+h/2)
        radius = math.hypot(dx,dy)
        if radius == 0:
            return min(w,h)/2
        boundary_radius = radius/math.sqrt((dx/(w/2))**2+(dy/(h/2))**2)
        return abs(radius-boundary_radius)
    points = polygon(node)
    distances = []
    for a, z in zip(points, points[1:]+points[:1]):
        vector = subtract(z,a)
        t = max(0,min(1,sum((point[i]-a[i])*vector[i] for i in range(2))/sum(v*v for v in vector)))
        distances.append(math.dist(point,(a[0]+t*vector[0],a[1]+t*vector[1])))
    return min(distances)


def segment_inside(a, b, node):
    """Detect interior penetration, avoiding bounding-box false hits at diamonds."""
    if inside(a,node) or inside(b,node):
        return True
    cuts = [0.0,1.0]; delta = subtract(b,a); length2 = sum(v*v for v in delta)
    if length2 <= EPS*EPS:
        return False
    if node['kind'] == 'ellipse':
        box = node['bounds']; rx,ry = box['width']/2,box['height']/2
        ox,oy = a[0]-box['x']-rx,a[1]-box['y']-ry
        aa = (delta[0]/rx)**2+(delta[1]/ry)**2
        bb = 2*(ox*delta[0]/rx**2+oy*delta[1]/ry**2)
        cc = (ox/rx)**2+(oy/ry)**2-1
        discriminant = bb*bb-4*aa*cc
        if discriminant >= 0:
            cuts.extend(t for t in ((-bb-math.sqrt(discriminant))/(2*aa),(-bb+math.sqrt(discriminant))/(2*aa)) if 0<=t<=1)
    else:
        points = polygon(node)
        for c,d in zip(points,points[1:]+points[:1]):
            hit = segment_hit(a,b,c,d)
            if hit and hit[0] == 'point':
                cuts.append(sum((hit[1][i]-a[i])*delta[i] for i in range(2))/length2)
    cuts = sorted(set(cuts))
    for lo,hi in zip(cuts,cuts[1:]):
        t = (lo+hi)/2
        if inside((a[0]+t*delta[0],a[1]+t*delta[1]),node):
            return True
    return False


def shapes_overlap(a,b):
    aa,bb = a['bounds'],b['bounds']
    if min(aa['x']+aa['width'],bb['x']+bb['width'])-max(aa['x'],bb['x']) <= EPS or min(aa['y']+aa['height'],bb['y']+bb['height'])-max(aa['y'],bb['y']) <= EPS:
        return False
    # Convex polygon SAT. Events use 96 vertices; line/event checks are analytic.
    first,second = polygon(a),polygon(b)
    for points in (first,second):
        for p,q in zip(points,points[1:]+points[:1]):
            edge = subtract(q,p); axis=(-edge[1],edge[0]); norm=math.hypot(*axis)
            axis=(axis[0]/norm,axis[1]/norm)
            p1=[sum(p[i]*axis[i] for i in range(2)) for p in first]
            p2=[sum(p[i]*axis[i] for i in range(2)) for p in second]
            if min(max(p1),max(p2))-max(min(p1),min(p2)) <= EPS:
                return False
    return True


def load_render(location, sha256):
    if not location:
        return None
    path = Path(location)
    if path.is_dir(): path = path/'report.json'
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('status') and data['status'] != 'rendered':
        raise ValueError('render report does not describe a successful render')
    if data.get('sha256') != sha256:
        raise ValueError('render report SHA-256 does not match the current BPMN XML; render it again')
    if 'geometry' in data:
        geometry_path = Path(data['geometry'])
        if not geometry_path.is_absolute(): geometry_path = path.parent/geometry_path
        data = json.loads(geometry_path.read_text(encoding='utf-8-sig'))
        if data.get('sha256') != sha256:
            raise ValueError('DOM geometry SHA-256 does not match the current BPMN XML')
    if not isinstance(data.get('diagrams'),list):
        raise ValueError('render geometry has no diagrams list')
    return {d.get('planeId'):d for d in data['diagrams']}


def audit(input_path, render_path=None):
    raw=Path(input_path).read_bytes(); sha256=hashlib.sha256(raw).hexdigest()
    root=ET.fromstring(raw)
    idx={}; duplicate=[]
    for element in root.iter():
        identifier=element.get('id')
        if identifier:
            if identifier in idx: duplicate.append(identifier)
            idx[identifier]=element
    if duplicate: raise ValueError('duplicate XML ids: '+', '.join(duplicate))
    parents={child:parent for parent in root.iter() for child in parent}
    rendered=load_render(render_path,sha256)
    report={'input':str(Path(input_path).resolve()),'sha256':sha256,'status':'incomplete','pass':False,'label_check':'unavailable','diagrams':[],'issues':[],'limitations':['Event/node overlap uses convex polygons with 96 sides for ellipses; segment/event intersections and endpoint checks use the ellipse itself.','Geometric checks do not validate BPMN semantics; human review of the rendered diagrams remains required.']}
    def issue(plane,category,ids,message,severity='error',**detail):
        record={'planeId':plane,'category':category,'elements':ids,'severity':severity,'message':message,**detail}
        report['issues'].append(record)
    diagrams=root.findall('.//{%s}BPMNDiagram'%BPMNDI)
    if not diagrams: raise ValueError('no BPMNDiagram found')
    for diagram in diagrams:
        plane=diagram.find('{%s}BPMNPlane'%BPMNDI)
        if plane is None: raise ValueError('BPMNDiagram has no BPMNPlane')
        pid=plane.get('id'); nodes={}; edges=[]; estimated=[]
        plane_report={'id':diagram.get('id'),'planeId':pid,'bpmnElement':ref(plane.get('bpmnElement')),'label_check':'unavailable'}
        report['diagrams'].append(plane_report)
        for shape in plane.findall('{%s}BPMNShape'%BPMNDI):
            identifier=ref(shape.get('bpmnElement')); semantic=idx.get(identifier)
            if semantic is None:
                issue(pid,'missing_reference',[identifier],'Shape references a missing BPMN element'); continue
            try: box=bounds(shape.find('{%s}Bounds'%DC))
            except (TypeError,ValueError) as error:
                issue(pid,'invalid_bounds',[identifier],str(error)); continue
            typ=local(semantic)
            container=typ in ('participant','lane','group') or (typ in ('subProcess','transaction','adHocSubProcess') and shape.get('isExpanded') in ('true','1'))
            kind='diamond' if typ.endswith('Gateway') else 'ellipse' if typ.endswith('Event') else 'rect'
            nodes[identifier]={'id':identifier,'type':typ,'kind':kind,'bounds':box,'container':container,'attachedTo':ref(semantic.get('attachedToRef'))}
            label=shape.find('{%s}BPMNLabel/{%s}Bounds'%(BPMNDI,DC))
            if label is not None:
                try: estimated.append({'id':identifier+'_estimated_label','ownerId':identifier,'text':semantic.get('name',''),'internal':False,'bounds':bounds(label)})
                except (TypeError,ValueError) as error: issue(pid,'invalid_label_bounds',[identifier],str(error))
        def visible_owner(identifier):
            element=idx.get(ref(identifier))
            while element is not None:
                if element.get('id') in nodes: return element.get('id')
                element=parents.get(element)
            return ref(identifier)
        def endpoints(semantic,edge_di):
            source,target=ref(semantic.get('sourceRef')),ref(semantic.get('targetRef'))
            typ=local(semantic)
            if typ in ('dataInputAssociation','dataOutputAssociation'):
                sources=[ref(e.text) for e in semantic if local(e)=='sourceRef']
                targets=[ref(e.text) for e in semantic if local(e)=='targetRef']
                source=sources[0] if sources else ''
                target=targets[0] if targets else ''
                parent=parents.get(semantic)
                if typ=='dataInputAssociation' and parent is not None: target=parent.get('id','')
                if typ=='dataOutputAssociation' and parent is not None: source=parent.get('id','')
            for attribute in ('sourceElement','targetElement'):
                linked=idx.get(ref(edge_di.get(attribute)))
                if linked is not None:
                    if attribute=='sourceElement': source=ref(linked.get('bpmnElement'))
                    else: target=ref(linked.get('bpmnElement'))
            return visible_owner(source),visible_owner(target)
        for edge_di in plane.findall('{%s}BPMNEdge'%BPMNDI):
            identifier=ref(edge_di.get('bpmnElement')); semantic=idx.get(identifier)
            if semantic is None:
                issue(pid,'missing_reference',[identifier],'Edge references a missing BPMN element'); continue
            try: points=[(finite_number(p.get('x')),finite_number(p.get('y'))) for p in edge_di.findall('{%s}waypoint'%DI)]
            except (TypeError,ValueError) as error:
                issue(pid,'invalid_waypoints',[identifier],str(error)); continue
            if len(points)<2:
                issue(pid,'invalid_waypoints',[identifier],'At least two waypoints are required'); continue
            source,target=endpoints(semantic,edge_di)
            edge={'id':identifier,'points':points,'source':source,'target':target}
            edges.append(edge)
            for end,node_id,point in [('source',source,points[0]),('target',target,points[-1])]:
                if node_id not in nodes:
                    issue(pid,'endpoint_unavailable',[identifier,node_id],f'{end} shape is missing in this plane'); continue
                distance=boundary_distance(point,nodes[node_id])
                if distance>END_TOL:
                    issue(pid,'detached_endpoint',[identifier,node_id],f'{end} waypoint is not on the shape boundary',distance=round(distance,3),point=point)
            for segment,(a,b) in enumerate(zip(points,points[1:])):
                if point_equal(a,b): issue(pid,'zero_length_segment',[identifier],'Consecutive waypoints coincide',segment=segment)
                elif abs(a[0]-b[0])>EPS and abs(a[1]-b[1])>EPS:
                    issue(pid,'nonorthogonal_path',[identifier],'Segment is diagonal',segment=segment)
                for node_id,node in nodes.items():
                    if node['container']: continue
                    # Endpoint boundary contact is harmless; passing through its interior is not.
                    if segment_inside(a,b,node):
                        issue(pid,'edge_crosses_node',[identifier,node_id],'Edge enters a node interior',segment=segment)
            label=edge_di.find('{%s}BPMNLabel/{%s}Bounds'%(BPMNDI,DC))
            if label is not None:
                try: estimated.append({'id':identifier+'_estimated_label','ownerId':identifier,'text':semantic.get('name',''),'internal':False,'bounds':bounds(label)})
                except (TypeError,ValueError) as error: issue(pid,'invalid_label_bounds',[identifier],str(error))
        for a,b in itertools.combinations(nodes.values(),2):
            if a['container'] or b['container']: continue
            attachment=None
            if a['attachedTo']==b['id']: attachment=(a,b)
            elif b['attachedTo']==a['id']: attachment=(b,a)
            if attachment:
                event,host=attachment; box=event['bounds']; center=(box['x']+box['width']/2,box['y']+box['height']/2)
                if boundary_distance(center,host)<=END_TOL: continue
                issue(pid,'invalid_boundary_attachment',[event['id'],host['id']],'Boundary event center is not on the attached activity boundary')
            if shapes_overlap(a,b): issue(pid,'node_overlap',[a['id'],b['id']],'Node interiors overlap')
        for first,second in itertools.combinations(edges,2):
            found=set()
            for a,b in zip(first['points'],first['points'][1:]):
                for c,d in zip(second['points'],second['points'][1:]):
                    hit=segment_hit(a,b,c,d)
                    if not hit: continue
                    kind,location=hit
                    if kind=='point':
                        first_ends=[node for node,pt in [(first['source'],first['points'][0]),(first['target'],first['points'][-1])] if point_equal(location,pt)]
                        second_ends=[node for node,pt in [(second['source'],second['points'][0]),(second['target'],second['points'][-1])] if point_equal(location,pt)]
                        if set(first_ends)&set(second_ends): continue
                    key=(kind,str(location))
                    if key in found: continue
                    found.add(key)
                    issue(pid,'edge_overlap' if kind=='overlap' else 'edge_crossing',[first['id'],second['id']],'Edges overlap along a segment' if kind=='overlap' else 'Edges intersect outside a shared BPMN endpoint',location=location)
        # Also catch a path crossing its own earlier segment, excluding adjacent bends.
        for edge in edges:
            segments=list(zip(edge['points'],edge['points'][1:]))
            for (i,(a,b)),(j,(c,d)) in itertools.combinations(enumerate(segments),2):
                hit=segment_hit(a,b,c,d)
                if hit and (j>i+1 or hit[0]=='overlap'):
                    if hit[0]=='point' and point_equal(hit[1],edge['points'][0]) and point_equal(hit[1],edge['points'][-1]) and edge['source']==edge['target']: continue
                    issue(pid,'edge_self_intersection',[edge['id']],'Edge intersects or retraces itself',segments=[i,j],location=hit[1])
        dom=rendered.get(pid) if rendered is not None else None
        if dom is not None and isinstance(dom.get('labels'),list):
            labels=dom['labels']; plane_report['label_check']='rendered'
            label_owners={label.get('ownerId') for label in labels}
            expected={identifier for identifier in list(nodes)+[e['id'] for e in edges] if idx[identifier].get('name') and local(idx[identifier]) not in ('dataInputAssociation','dataOutputAssociation','association','group')}
            missing=sorted(expected-label_owners)
            if missing:
                plane_report['label_check']='incomplete'
                issue(pid,'label_bounds_missing',missing,'Named elements have no measured DOM label bounds','warning')
        else:
            labels=estimated
            plane_report['label_check']='estimated' if labels else 'unavailable'
        valid_labels=[]
        for label in labels:
            try:
                box={key:finite_number(label['bounds'][key]) for key in ('x','y','width','height')}
                if box['width']<=0 or box['height']<=0: raise ValueError('label dimensions are not positive')
                label={**label,'bounds':box,'kind':'rect'}
            except (TypeError,ValueError,KeyError) as error:
                issue(pid,'invalid_label_bounds',[label.get('id','unknown')],str(error)); continue
            valid_labels.append(label)
            for node_id,node in nodes.items():
                if node['container']: continue
                if label.get('internal') and label.get('ownerId')==node_id:
                    corners=polygon(label)
                    if not all(inside(corner,node,margin=-0.5) for corner in corners):
                        issue(pid,'label_outside_owner',[label['id'],node_id],'Internal text extends outside its node')
                    continue
                if shapes_overlap(label,node): issue(pid,'label_overlaps_node',[label['id'],node_id],'Text box overlaps a node interior')
            for edge in edges:
                if any(segment_inside(a,b,label) for a,b in zip(edge['points'],edge['points'][1:])):
                    issue(pid,'label_overlaps_edge',[label['id'],edge['id']],'Text box intersects an edge')
        for first,second in itertools.combinations(valid_labels,2):
            if shapes_overlap(first,second): issue(pid,'label_overlap',[first['id'],second['id']],'Rendered text boxes overlap' if plane_report['label_check']=='rendered' else 'Estimated label bounds overlap')
        plane_report['nodes']=len(nodes); plane_report['edges']=len(edges); plane_report['labels']=len(valid_labels)
    modes={d['label_check'] for d in report['diagrams']}
    report['label_check']='rendered' if modes=={'rendered'} else 'estimated' if modes=={'estimated'} else 'unavailable' if modes=={'unavailable'} else 'incomplete'
    blocking=sum(i['severity']=='error' for i in report['issues'])
    report['status']='fail' if blocking else 'pass' if report['label_check']=='rendered' else 'incomplete'
    report['pass']=report['status']=='pass'
    report['summary']={'blocking_issues':blocking,'warnings':len(report['issues'])-blocking,'categories':{category:sum(i['category']==category for i in report['issues']) for category in sorted({i['category'] for i in report['issues']})}}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',help='BPMN XML file')
    parser.add_argument('--render-report',help='Renderer output directory, report.json, or geometry.json for this exact XML')
    parser.add_argument('--output',help='JSON audit report (stdout when omitted)')
    args=parser.parse_args()
    try:
        report=audit(args.input,args.render_report)
        code=1 if report['summary']['blocking_issues'] else 0
    except (OSError,ValueError,TypeError,KeyError,ET.ParseError) as error:
        report={'status':'error','pass':False,'error':str(error),'input':str(Path(args.input).resolve())}; code=2
    content=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        destination=Path(args.output); destination.parent.mkdir(parents=True,exist_ok=True); destination.write_text(content+'\n',encoding='utf-8')
        print(json.dumps({'status':report['status'],'output':str(destination.resolve()),'summary':report.get('summary'),'error':report.get('error')},ensure_ascii=False))
    else: print(content)
    return code


if __name__=='__main__':
    sys.exit(main())
