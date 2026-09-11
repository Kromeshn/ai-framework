"""Optional, read-only planarity diagnostic; never changes BPMN or claims geometric quality."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from lxml import etree as E

def inspect(root):
    try:
        import networkx as nx
    except ImportError:
        return {'status':'unavailable','reason':'Optional networkx is not installed in this Python'}
    ids={e.get('id'):e for e in root.iter() if e.get('id')}
    graph=nx.Graph()
    for elem in root.iter():
        if not isinstance(elem.tag,str):
            continue
        kind=E.QName(elem).localname
        if kind in ('sequenceFlow','messageFlow','association'):
            ends=(elem.get('sourceRef'),elem.get('targetRef'))
            if all(ends):graph.add_edge(*ends)
        elif kind in ('dataInputAssociation','dataOutputAssociation'):
            owner=elem.getparent().get('id')
            for child in elem:
                if not isinstance(child.tag,str):continue
                if E.QName(child).localname not in ('sourceRef','targetRef'):continue
                ref=ids.get((child.text or '').strip())
                if ref is not None and E.QName(ref).localname in ('dataObjectReference','dataStoreReference'):
                    graph.add_edge(owner,ref.get('id'))
        elif kind=='boundaryEvent' and elem.get('attachedToRef'):
            graph.add_edge(elem.get('id'),elem.get('attachedToRef'))
    planar,_=nx.check_planarity(graph)
    return {'status':'planar' if planar else 'nonplanar','nodes':len(graph),'edges':graph.number_of_edges(),
            'networkx':nx.__version__,
            'meaning':'Necessary topology check only. Planarity does not guarantee a crossing-free drawing with fixed lanes, containers, or positions.',
            'scope':'Undirected visual connectivity of flows/data associations; boundary events include attachment edges. A nonplanar result rules out a single plane without crossings; multiple separate planes may remove that constraint.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--no-fallback',action='store_true')
    args=ap.parse_args()
    result=inspect(E.parse(str(args.input),E.XMLParser(resolve_entities=False,no_network=True)).getroot())
    if result['status']=='unavailable' and not args.no_fallback:
        other=shutil.which('python')
        if other and Path(other).resolve()!=Path(sys.executable).resolve():
            proc=subprocess.run([other,'-X','utf8',str(Path(__file__).resolve()),str(args.input.resolve()),'--output',str(args.output.resolve()),'--no-fallback'],capture_output=True,text=True,encoding='utf-8')
            if proc.returncode==0:
                print(proc.stdout.strip())
                return 0
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())