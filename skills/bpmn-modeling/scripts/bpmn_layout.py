"""Offline BPMN layout: preserve semantics, arrange DI, render, and audit before writing."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from lxml import etree as ET

B = 'http://www.omg.org/spec/BPMN/20100524/MODEL'
D = 'http://www.omg.org/spec/BPMN/20100524/DI'
DC = 'http://www.omg.org/spec/DD/20100524/DC'
COLOR = 'http://bpmn.io/schema/bpmn/biocolor/1.0'
NS = {'b': B, 'd': D, 'dc': DC}
HERE = Path(__file__).resolve().parent

def semantic_digest(root):
    def item(e):
        if not isinstance(e.tag, str) or e.tag.startswith('{'+D+'}'):
            return None
        return [e.tag, sorted(e.attrib.items()), (e.text or '').strip(),
                [x for c in e if (x := item(c)) is not None]]
    return hashlib.sha256(json.dumps(item(root), ensure_ascii=False).encode()).hexdigest()

def parse(path):
    return ET.parse(str(path), ET.XMLParser(resolve_entities=False, no_network=True)).getroot()

def save(root, path):
    path.write_bytes(ET.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True))

def runtime(explicit, executable):
    if explicit:
        if not Path(explicit).is_file():
            raise ValueError(f'Runtime not found: {explicit}')
        return str(Path(explicit).resolve())
    found = shutil.which(executable)
    if found:
        return found
    home = Path.home()
    candidates = list((home/'.cache/codex-runtimes').glob('*/dependencies/node/bin/node.exe'))
    if executable == 'node' and candidates:
        return str(candidates[0])
    raise ValueError(f'{executable} is required; provide --node')

def run(command):
    result = subprocess.run([str(x) for x in command], cwd=HERE, text=True,
                            encoding='utf-8', errors='replace', capture_output=True)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}): {command[0]}\n{result.stderr}\n{result.stdout}')
    return result

def prepare_engine_input(root):
    work = copy.deepcopy(root)
    y = {s.get('bpmnElement'): float(s.find('dc:Bounds', NS).get('y'))
         for s in work.findall('.//d:BPMNShape', NS) if s.find('dc:Bounds', NS) is not None}
    # Preserve the displayed lane order when a complete existing model is reflowed.
    for lane_set in work.findall('.//b:laneSet', NS) + work.findall('.//b:childLaneSet', NS):
        lanes = lane_set.findall('b:lane', NS)
        if lanes and all(l.get('id') in y for l in lanes):
            for lane in lanes:
                lane_set.remove(lane)
            lane_set.extend(sorted(lanes, key=lambda l: y[l.get('id')]))
    return work

def transfer_di(original, generated):
    old = {s.get('bpmnElement'): s for s in original.findall('.//d:BPMNShape', NS)}
    for diagram in original.findall('d:BPMNDiagram', NS):
        original.remove(diagram)
    diagrams = generated.findall('d:BPMNDiagram', NS)
    if not diagrams:
        raise ValueError('Layout engine returned no diagrams')
    for diagram in diagrams:
        original.append(copy.deepcopy(diagram))
    elements = {e.get('id'): e for e in original.iter() if e.get('id')}
    for shape in original.findall('.//d:BPMNShape', NS):
        key = shape.get('bpmnElement')
        previous = old.get(key)
        for attr in ('{'+COLOR+'}fill', '{'+COLOR+'}stroke',
                     '{http://www.omg.org/spec/BPMN/non-normative/color/1.0}background-color',
                     '{http://www.omg.org/spec/BPMN/non-normative/color/1.0}border-color'):
            if previous is not None and attr in previous.attrib:
                shape.set(attr, previous.get(attr))
        elem = elements.get(key)
        if elem is None:
            continue
        kind = ET.QName(elem).localname
        shape.set('{'+COLOR+'}stroke', '#000000')
        if '{'+COLOR+'}fill' not in shape.attrib:
            if kind == 'startEvent':
                shape.set('{'+COLOR+'}fill', '#dff1df')
            elif kind == 'endEvent':
                shape.set('{'+COLOR+'}fill', '#f8d6d6')
        if kind.endswith('Gateway'):
            label = shape.find('d:BPMNLabel/dc:Bounds', NS)
            bounds = shape.find('dc:Bounds', NS)
            if label is not None and bounds is not None:
                width = float(label.get('width', '150'))
                height = float(label.get('height', '30'))
                label.set('x', str(float(bounds.get('x')) + float(bounds.get('width'))/2 - width/2))
                label.set('y', str(float(bounds.get('y')) - height - 12))

def fit_measured_labels(root, geometry):
    elements = {e.get('id'): e for e in root.iter() if e.get('id')}
    count = 0
    for measured in geometry['diagrams']:
        plane = root.find(f".//d:BPMNPlane[@id='{measured['planeId']}']", NS)
        if plane is None:
            raise ValueError('Measured plane is missing')
        shapes = {e.get('bpmnElement'): e for e in plane}
        internal = {l['ownerId']: l['bounds'] for l in measured['labels'] if l.get('internal')}
        for label in measured['labels']:
            if label.get('internal'):
                continue
            owner = label['ownerId']
            shape = shapes.get(owner)
            element = elements.get(owner)
            if shape is None or element is None:
                continue
            bound = shape.find('d:BPMNLabel/dc:Bounds', NS)
            if bound is None:
                continue
            box = dict(label['bounds'])
            kind = ET.QName(element).localname
            if kind.endswith('Gateway') or kind in ('dataObjectReference', 'dataStoreReference'):
                node = shape.find('dc:Bounds', NS)
                if node is not None:
                    box['x'] = float(node.get('x')) + float(node.get('width'))/2 - box['width']/2
                    box['y'] = float(node.get('y')) - box['height'] - 10
            if kind == 'messageFlow' and owner in internal:
                other = internal[owner]
                box['x'] = other['x'] + other['width'] + 30
                box['y'] = other['y']
            for key in ('x', 'y', 'width', 'height'):
                bound.set(key, str(round(box[key], 3)))
            count += 1
    return count

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('--output', type=Path, help='Defaults to input; written only after successful verification')
    ap.add_argument('--report-dir', type=Path, required=True)
    ap.add_argument('--reflow', action='store_true', help='Explicitly permit replacing existing DI')
    ap.add_argument('--node')
    ap.add_argument('--playwright')
    ap.add_argument('--browser')
    args = ap.parse_args()
    start = time.monotonic()
    original_bytes = args.input.read_bytes()
    original_sha = hashlib.sha256(original_bytes).hexdigest()
    root = parse(args.input)
    if root.findall('d:BPMNDiagram', NS) and not args.reflow:
        ap.error('Existing DI requires --reflow. For a local edit, patch only affected DI instead.')
    before = semantic_digest(root)
    output = (args.output or args.input).resolve()
    if output != args.input.resolve() and output.exists():
        ap.error('Output already exists; select that file as input for an authorized reflow')
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    if args.input.resolve().is_relative_to(report_dir) or output.is_relative_to(report_dir):
        ap.error('Report directory must not contain the source or output file; choose a separate temporary directory')
    for option in ('playwright', 'browser'):
        value = getattr(args, option)
        if value:
            setattr(args, option, str(Path(value).resolve()))
    report = {'input_sha256': original_sha, 'semantic_sha256': before, 'status': 'failed', 'output_written': False}
    try:
        from document_layout import arrange_documents
        from route_tidy import tidy_routes
        run([sys.executable, HERE/'topology_report.py', args.input.resolve(), '--output', report_dir/'topology.json'])
        report['topology'] = json.loads((report_dir/'topology.json').read_text(encoding='utf-8'))
        engine_in = report_dir/'engine-input.bpmn'
        engine_out = report_dir/'engine-output.bpmn'
        candidate = report_dir/'candidate.bpmn'
        save(prepare_engine_input(root), engine_in)
        node = runtime(args.node, 'node')
        run([node, HERE/'layout_engine.cjs', engine_in, engine_out, report_dir/'engine.json'])
        report['engine'] = json.loads((report_dir/'engine.json').read_text(encoding='utf-8'))
        transfer_di(root, parse(engine_out))
        report['documents'] = arrange_documents(root)
        if semantic_digest(root) != before:
            raise ValueError('Semantic fingerprint changed; output rejected')
        ids = [e.get('id') for e in root.iter() if e.get('id')]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate IDs after DI generation; output rejected')
        save(root, candidate)
        def render_at(directory):
            command = [node, HERE/'bpmn_render.cjs', candidate, '--out-dir', directory]
            if args.playwright:
                command += ['--playwright', args.playwright]
            if args.browser:
                command += ['--browser', args.browser]
            run(command)
        measured_dir = report_dir/'measure'
        render_at(measured_dir)
        measured_geometry = json.loads((measured_dir/'geometry.json').read_text(encoding='utf-8'))
        if measured_geometry.get('sha256') != hashlib.sha256(candidate.read_bytes()).hexdigest():
            raise ValueError('Measured labels belong to another XML')
        report['measured_labels'] = fit_measured_labels(root, measured_geometry)
        report['routes'] = tidy_routes(root)
        if semantic_digest(root) != before:
            raise ValueError('Semantics changed after routing; output rejected')
        save(root, candidate)
        preview = report_dir/'preview'
        render_at(preview)
        audit_path = report_dir/'audit.json'
        audit_path.unlink(missing_ok=True)
        audit_run = subprocess.run([sys.executable, str(HERE/'geometry_audit.py'), str(candidate),
                        '--render-report', str(preview/'report.json'), '--output', str(audit_path)],
                       cwd=HERE, capture_output=True, text=True, encoding='utf-8')
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        report['audit'] = audit
        if audit_run.returncode not in (0, 1) or audit.get('sha256') != hashlib.sha256(candidate.read_bytes()).hexdigest():
            raise ValueError('Audit failed or belongs to a different XML; output rejected')
        if audit.get('status') != 'pass':
            detail = ' The visual graph is nonplanar: a single-plane zero-crossing drawing is impossible without changing representation.' if report.get('topology', {}).get('status') == 'nonplanar' else ''
            raise ValueError('Geometry audit requires correction; inspect candidate and preview in report directory.' + detail)
        render = json.loads((preview/'report.json').read_text(encoding='utf-8'))
        if render.get('warnings'):
            raise ValueError('Renderer reported warnings; inspect report before accepting')
        if hashlib.sha256(args.input.read_bytes()).hexdigest() != original_sha:
            raise ValueError('Input changed during layout; reread latest file instead of overwriting')
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.bpmn-', suffix='.tmp', dir=output.parent)
        os.close(fd)
        try:
            Path(temporary).write_bytes(candidate.read_bytes())
            os.replace(temporary, output)
        finally:
            Path(temporary).unlink(missing_ok=True)
        report.update(status='pass', output_written=True, output=str(output))
    except (ValueError, RuntimeError, OSError, ET.XMLSyntaxError) as exc:
        report['error'] = str(exc)
    report['elapsed_seconds'] = round(time.monotonic()-start, 3)
    (report_dir/'layout-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
    print(json.dumps({k: report.get(k) for k in ('status', 'output_written', 'output', 'elapsed_seconds', 'error')}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1

if __name__ == '__main__':
    raise SystemExit(main())