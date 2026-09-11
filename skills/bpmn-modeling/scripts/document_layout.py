"""Place BPMN data references in a document strip, changing DI only.

The caller must route connections and audit/render the result afterwards. Text
measurements are conservative estimates; rendered text remains authoritative.
"""

import math
import textwrap
from collections.abc import Callable

from lxml import etree as ET

BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"
DI = "http://www.omg.org/spec/DD/20100524/DI"
DOC_TYPES = {"dataObjectReference", "dataStoreReference"}
CONTAINER_TYPES = {"participant", "lane", "subProcess", "transaction"}
LABEL_WIDTH = 160.0
GAP = 24.0
PADDING = 20.0


def _local(element: ET._Element) -> str:
    return ET.QName(element).localname


def _ref(value: str | None) -> str:
    return (value or "").split(":")[-1]


def _bounds(shape: ET._Element) -> ET._Element:
    result = shape.find(f"{{{DC}}}Bounds")
    if result is None:
        raise ValueError(f"Shape {shape.get('id')} has no Bounds")
    return result


def _rect(shape: ET._Element) -> tuple[float, float, float, float]:
    bounds = _bounds(shape)
    values = tuple(float(bounds.get(key, "nan")) for key in ("x", "y", "width", "height"))
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"Shape {shape.get('id')} has non-finite Bounds")
    return values


def _set(element: ET._Element, **values: float) -> None:
    for key, value in values.items():
        element.set(key, f"{value:.3f}".rstrip("0").rstrip(".") or "0")


def _scope(element: ET._Element) -> ET._Element | None:
    for parent in element.iterancestors():
        if _local(parent) in {"process", "subProcess", "transaction"}:
            return parent
    return None


def _labels(shape: ET._Element) -> list[ET._Element]:
    return list(shape.findall(f"{{{BPMNDI}}}BPMNLabel/{{{DC}}}Bounds"))


def _endpoint(element: ET._Element, semantics: dict[str, ET._Element], side: str) -> str:
    value = element.get(side)
    if value is None:
        child = element.find(f"{{{BPMN}}}{side}")
        value = child.text if child is not None else None
    target = semantics.get(_ref(value))
    if target is not None and _local(target) in {"dataInput", "dataOutput"}:
        target = target.getparent().getparent()
    return target.get("id", "") if target is not None else _ref(value)


def _move_geometry(
    plane: ET._Element,
    *,
    shapes: dict[str, ET._Element],
    semantics: dict[str, ET._Element],
    shifts: dict[str, float],
    map_y: Callable[[float], float],
) -> None:
    """Move shapes rigidly and preserve orthogonal end segments where possible."""
    for identifier, shape in shapes.items():
        delta = shifts.get(identifier, 0.0)
        if delta:
            bounds = _bounds(shape)
            _set(bounds, y=float(bounds.get("y")) + delta)
            for label in _labels(shape):
                _set(label, y=float(label.get("y")) + delta)
    for edge in plane.findall(f"{{{BPMNDI}}}BPMNEdge"):
        semantic = semantics.get(_ref(edge.get("bpmnElement")))
        if semantic is None:
            continue
        source = shifts.get(_endpoint(semantic, semantics, "sourceRef"), 0.0)
        target = shifts.get(_endpoint(semantic, semantics, "targetRef"), 0.0)
        waypoints = edge.findall(f"{{{DI}}}waypoint")
        old = [(float(p.get("x")), float(p.get("y"))) for p in waypoints]
        if source == target:
            new = [(x, y + source) for x, y in old]
        else:
            new = [(x, map_y(y)) for x, y in old]
            if len(new) >= 2:
                new[0] = (old[0][0], old[0][1] + source)
                new[-1] = (old[-1][0], old[-1][1] + target)
                if len(new) == 2 and old[0][1] == old[-1][1]:
                    mid_x = (new[0][0] + new[-1][0]) / 2
                    new = [new[0], (mid_x, new[0][1]), (mid_x, new[-1][1]), new[-1]]
                elif len(new) > 2:
                    if old[0][1] == old[1][1]:
                        new[1] = (new[1][0], new[0][1])
                    if old[-1][1] == old[-2][1]:
                        new[-2] = (new[-2][0], new[-1][1])
        if len(new) != len(waypoints):
            index = edge.index(waypoints[0])
            for waypoint in waypoints:
                edge.remove(waypoint)
            for offset, (x, y) in enumerate(new):
                waypoint = ET.Element(f"{{{DI}}}waypoint")
                _set(waypoint, x=x, y=y)
                edge.insert(index + offset, waypoint)
        else:
            for waypoint, (x, y) in zip(waypoints, new):
                _set(waypoint, x=x, y=y)
        for label in _labels(edge):
            y = float(label.get("y"))
            _set(label, y=y + source if source == target else map_y(y))


def _insert_space(
    plane: ET._Element,
    *,
    shapes: dict[str, ET._Element],
    semantics: dict[str, ET._Element],
    cut: float,
    height: float,
    grow_ids: set[str],
) -> None:
    """Insert a horizontal band across the plane, including enclosing pools."""
    if height <= 0:
        return
    shifts = {}
    for identifier, shape in shapes.items():
        _, y, _, h = _rect(shape)
        semantic = semantics[identifier]
        container = _local(semantic) in CONTAINER_TYPES
        if identifier in grow_ids or (container and y < cut < y + h):
            _set(_bounds(shape), height=h + height)
        elif y >= cut or (not container and y + h > cut):
            shifts[identifier] = height
    for identifier, semantic in semantics.items():
        if _local(semantic) == "boundaryEvent" and identifier in shapes:
            shifts[identifier] = shifts.get(_ref(semantic.get("attachedToRef")), 0.0)
    _move_geometry(plane, shapes=shapes, semantics=semantics, shifts=shifts,
                   map_y=lambda y: y + height if y >= cut else y)


def _container(
    scope: ET._Element, shapes: dict[str, ET._Element], semantics: dict[str, ET._Element]
) -> ET._Element | None:
    if scope.get("id") in shapes:
        return shapes[scope.get("id")]
    for identifier, shape in shapes.items():
        semantic = semantics[identifier]
        if _local(semantic) == "participant" and _ref(semantic.get("processRef")) == scope.get("id"):
            return shape
    return None


def _preferred_x(
    document: ET._Element, shapes: dict[str, ET._Element], semantics: dict[str, ET._Element]
) -> float:
    identifier = document.get("id")
    for kind, side in (("dataOutputAssociation", "targetRef"), ("dataInputAssociation", "sourceRef")):
        for element in semantics.values():
            if _local(element) != kind:
                continue
            refs = element.findall(f"{{{BPMN}}}{side}")
            if any(_ref(ref.text) == identifier for ref in refs):
                owner = element.getparent().get("id")
                if owner in shapes:
                    x, _, width, _ = _rect(shapes[owner])
                    return x + width / 2
    x, _, width, _ = _rect(shapes[identifier])
    return x + width / 2


def _pack(
    documents: list[ET._Element],
    *,
    shapes: dict[str, ET._Element],
    semantics: dict[str, ET._Element],
    left: float,
    right: float,
) -> tuple[list[tuple[str, float, float, float]], float]:
    """Reserve rows conservatively for the renderer's 90 px external text box."""
    rows: list[list[tuple[str, float, float]]] = [[]]
    cursor = left
    for document in sorted(documents, key=lambda item: (_preferred_x(item, shapes, semantics), item.get("id"))):
        desired = _preferred_x(document, shapes, semantics)
        center = max(cursor + LABEL_WIDTH / 2, min(desired, right - LABEL_WIDTH / 2))
        if center + LABEL_WIDTH / 2 > right and rows[-1]:
            rows.append([])
            cursor = left
            center = max(cursor + LABEL_WIDTH / 2, min(desired, right - LABEL_WIDTH / 2))
        lines = sum(max(1, len(textwrap.wrap(line, width=12, break_long_words=True)))
                    for line in (document.get("name") or "").split("\n"))
        rows[-1].append((document.get("id"), center, max(14.0, lines * 14.0)))
        cursor = center + LABEL_WIDTH / 2 + GAP
    positions = []
    top = PADDING
    for row in rows:
        label_height = max(item[2] for item in row)
        icon_height = max(_rect(shapes[item[0]])[3] for item in row)
        for identifier, center, height in row:
            positions.append((identifier, center, top + label_height - height, height))
        top += label_height + 10.0 + icon_height + GAP
    return positions, top - GAP + PADDING


def _raise_document_lane(
    plane: ET._Element,
    *,
    lane: ET._Element,
    shapes: dict[str, ET._Element],
    semantics: dict[str, ET._Element],
) -> None:
    identifier = lane.get("id")
    _, lane_y, _, lane_h = _rect(shapes[identifier])
    siblings = [item for item in lane.getparent() if item.get("id") in shapes]
    earlier = [item for item in siblings if _rect(shapes[item.get("id")])[1] < lane_y]
    if not earlier:
        return
    top = min(_rect(shapes[item.get("id")])[1] for item in earlier)
    shifted_ids = set()
    for sibling in earlier:
        shifted_ids.add(sibling.get("id"))
        shifted_ids.update(item.get("id") for item in sibling.iter() if item.get("id"))
        for member in sibling.iter(f"{{{BPMN}}}flowNodeRef"):
            semantic = semantics.get(_ref(member.text))
            if semantic is not None:
                shifted_ids.update(item.get("id") for item in semantic.iter() if item.get("id"))
    shifts = {item: lane_h for item in shifted_ids if item in shapes}
    for item, shape in shapes.items():
        semantic = semantics[item]
        x, y, width, height = _rect(shape)
        inside_earlier = any(
            lx <= x + width / 2 <= lx + lw and ly <= y + height / 2 < ly + lh
            for lx, ly, lw, lh in (_rect(shapes[sibling.get("id")]) for sibling in earlier)
        )
        if _local(semantic) not in CONTAINER_TYPES and inside_earlier:
            shifts[item] = lane_h
    shifts[identifier] = top - lane_y
    for item, semantic in semantics.items():
        if _local(semantic) == "boundaryEvent" and item in shapes:
            shifts[item] = shifts.get(_ref(semantic.get("attachedToRef")), 0.0)
    def map_y(y: float) -> float:
        if top <= y < lane_y:
            return y + lane_h
        if lane_y <= y < lane_y + lane_h:
            return y + top - lane_y
        return y
    _move_geometry(plane, shapes=shapes, semantics=semantics, shifts=shifts, map_y=map_y)


def arrange_documents(root: ET._Element) -> list[dict[str, object]]:
    """Arrange visible data references on every plane; preserve semantic XML.

    Returns diagnostics with code, elementId, message and needs_review. The
    caller remains responsible for rerouting connections and visual inspection.
    No semantic lane or element is created. Narrow containers are left unchanged.
    """
    semantics = {item.get("id"): item for item in root.iter()
                 if isinstance(item.tag, str) and ET.QName(item).namespace == BPMN and item.get("id")}
    diagnostics: list[dict[str, object]] = []
    for plane in root.iter(f"{{{BPMNDI}}}BPMNPlane"):
        shapes = {_ref(shape.get("bpmnElement")): shape
                  for shape in plane.findall(f"{{{BPMNDI}}}BPMNShape")
                  if _ref(shape.get("bpmnElement")) in semantics}
        groups: dict[ET._Element, list[ET._Element]] = {}
        for identifier in shapes:
            semantic = semantics[identifier]
            if _local(semantic) in DOC_TYPES:
                scope = _scope(semantic)
                if scope is not None:
                    groups.setdefault(scope, []).append(semantic)
        placed_documents: set[str] = set()
        for scope in sorted(groups, key=lambda item: len(list(item.iterancestors())), reverse=True):
            documents = groups[scope]
            container = _container(scope, shapes, semantics)
            candidates = [item for item in scope.iter(f"{{{BPMN}}}lane")
                          if _scope(item) is scope and (item.get("name") or "").strip().casefold() == "документы"]
            empty_lanes = [item for item in candidates if not list(item.iter(f"{{{BPMN}}}flowNodeRef"))
                           and item.find(f"{{{BPMN}}}childLaneSet") is None and item.get("id") in shapes]
            lane = empty_lanes[0] if empty_lanes else None
            if candidates and lane is None:
                diagnostics.append({"code": "DOCUMENT_LANE_NOT_EMPTY", "elementId": scope.get("id"),
                                    "message": "Дорожка Документы содержит действия, вложенные дорожки или не имеет DI; её структура сохранена.", "needs_review": True})
            strip = shapes[lane.get("id")] if lane is not None else container
            if strip is not None:
                x, _, width, _ = _rect(strip)
                left, right = x + 40.0, x + width - PADDING
            else:
                work = [shape for identifier, shape in shapes.items() if _local(semantics[identifier]) not in DOC_TYPES]
                left = min((_rect(shape)[0] for shape in work), default=80.0)
                right = max((_rect(shape)[0] + _rect(shape)[2] for shape in work), default=left + 300.0)
            if right - left < LABEL_WIDTH:
                diagnostics.append({"code": "DOCUMENT_STRIP_TOO_NARROW", "elementId": scope.get("id"),
                                    "message": "Недостаточно ширины для подписи документа; требуется расширить контейнер и повторить раскладку.", "needs_review": True})
                continue
            positions, required = _pack(documents, shapes=shapes, semantics=semantics, left=left, right=right)
            if lane is not None:
                _, old_y, _, old_h = _rect(strip)
                grow_ids = {lane.get("id")}
                for identifier, shape in shapes.items():
                    x, y, width, height = _rect(shape)
                    if _local(semantics[identifier]) in CONTAINER_TYPES and y <= old_y and y + height >= old_y + old_h:
                        lx, _, lw, _ = _rect(strip)
                        if x <= lx and x + width >= lx + lw:
                            grow_ids.add(identifier)
                _insert_space(plane, shapes=shapes, semantics=semantics, cut=old_y + old_h,
                              height=max(0.0, required - old_h), grow_ids=grow_ids)
                _raise_document_lane(plane, lane=lane, shapes=shapes, semantics=semantics)
                top = _rect(strip)[1]
            elif container is not None and _local(scope) in {"subProcess", "transaction"}:
                top = _rect(container)[1] + 40.0
                work_tops = []
                document_ids = {item.get("id") for item in documents}
                for identifier, shape in shapes.items():
                    if identifier in document_ids or identifier == scope.get("id"):
                        continue
                    if scope in semantics[identifier].iterancestors():
                        work_tops.append(_rect(shape)[1])
                        work_tops.extend(float(label.get("y")) for label in _labels(shape))
                first_work = min(work_tops, default=top)
                growth = max(0.0, top + required + PADDING - first_work)
                _insert_space(plane, shapes=shapes, semantics=semantics, cut=top,
                              height=growth, grow_ids={scope.get("id")})
            else:
                other_tops = []
                for identifier, shape in shapes.items():
                    if _local(semantics[identifier]) not in DOC_TYPES or identifier in placed_documents:
                        other_tops.append(_rect(shape)[1])
                        other_tops.extend(float(label.get("y")) for label in _labels(shape))
                top = min(other_tops, default=80.0) - required - GAP
            for identifier, center, label_top, label_height in positions:
                shape = shapes[identifier]
                _, _, width, height = _rect(shape)
                _set(_bounds(shape), x=center - width / 2, y=top + label_top + label_height + 10.0)
                label = shape.find(f"{{{BPMNDI}}}BPMNLabel")
                if label is None:
                    label = ET.SubElement(shape, f"{{{BPMNDI}}}BPMNLabel")
                bounds = label.find(f"{{{DC}}}Bounds")
                if bounds is None:
                    bounds = ET.SubElement(label, f"{{{DC}}}Bounds")
                _set(bounds, x=center - LABEL_WIDTH / 2, y=top + label_top,
                     width=LABEL_WIDTH, height=label_height)
            placed_documents.update(item.get("id") for item in documents)
            diagnostics.append({"code": "DOCUMENTS_ARRANGED", "elementId": scope.get("id"),
                                "message": f"Размещено документов: {len(documents)}. Ассоциации требуют повторной стыковки, подписи — проверки отрисовки.",
                                "needs_review": True})
        minimum = min((float(item.get("y")) for item in plane.iter()
                       if isinstance(item.tag, str) and _local(item) in {"Bounds", "waypoint"} and item.get("y") is not None), default=80.0)
        if minimum < 40.0:
            delta = 40.0 - minimum
            for item in plane.iter():
                if isinstance(item.tag, str) and _local(item) in {"Bounds", "waypoint"} and item.get("y") is not None:
                    _set(item, y=float(item.get("y")) + delta)
    return diagnostics
