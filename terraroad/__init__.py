# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""TerraRoad for IngeTrazo 0.5.9 — native Python port, development build.

Original TerraRoad 172.0.0: Copyright 2026 The Court Group.
This file implements the centerline corridor workflow; see PORT_STATUS.md
for the full feature parity inventory. All distances are metres.
"""
from __future__ import annotations

import copy
import csv
import math
import importlib.util
from pathlib import Path
import sys
from dataclasses import asdict, dataclass

KEY = "TerraRoad"
VERSION = "0.8.0-dev"
EPS = 1e-7


@dataclass
class Parameters:
    lanes: int = 2
    lane_width: float = 3.5
    thickness: float = 0.25
    crown: float = 0.02
    median: float = 0.0
    shoulder: float = 0.0
    curb_width: float = 0.15
    curb_height: float = 0.15
    verge: float = 0.0
    sidewalk: float = 1.5
    sidewalk_thickness: float = 0.1
    markings: bool = True
    line_width: float = 0.1
    dash: float = 3.0
    gap: float = 6.0
    radius: float = 0.0
    station_interval: float = 2.0
    offset: float = 0.0
    elevation: float = 0.0

    def validate(self):
        for name, value in asdict(self).items():
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite.")
        if isinstance(self.lanes, bool) or int(self.lanes) != self.lanes or not 1 <= self.lanes <= 20:
            raise ValueError("Lane count must be an integer from 1 to 20.")
        if self.lane_width < 0.5 or self.thickness < 0.01:
            raise ValueError("Lane width must be at least 0.5 m and pavement thickness at least 0.01 m.")
        for key in ("median", "shoulder", "curb_width", "curb_height", "verge", "sidewalk", "sidewalk_thickness", "radius", "gap"):
            if getattr(self, key) < 0:
                raise ValueError(f"{key} cannot be negative.")
        if not 0 <= self.crown <= 0.12:
            raise ValueError("Crown must be between 0 and 0.12 (12%).")
        if min(self.line_width, self.dash, self.station_interval) < 0.01:
            raise ValueError("Line width, dash length and station interval must be positive.")
        if self.line_width >= self.lane_width:
            raise ValueError("Line width must be less than lane width.")
        if self.sidewalk > 0 and self.sidewalk_thickness < 0.01:
            raise ValueError("Sidewalk thickness must be at least 0.01 m.")


def distance(a, b):
    return math.dist(a, b)


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def ordered_path(segments):
    """Order an undirected, connected open chain; reject branches and loops."""
    graph, points, seen = {}, {}, set()
    for a, b in segments:
        a, b = tuple(a), tuple(b)
        if len(a) != 3 or len(b) != 3 or not all(math.isfinite(v) for v in (*a, *b)):
            raise ValueError("Centerline coordinates must be finite XYZ values.")
        ka, kb = tuple(round(v, 4) for v in a), tuple(round(v, 4) for v in b)
        if ka == kb:
            raise ValueError("The selection includes a zero-length edge.")
        edge = tuple(sorted((ka, kb)))
        if edge in seen:
            raise ValueError("The selection includes duplicate edges.")
        seen.add(edge)
        points[ka], points[kb] = a, b
        graph.setdefault(ka, []).append(kb)
        graph.setdefault(kb, []).append(ka)
    if not graph:
        raise ValueError("Select the connected edges of an open centerline first.")
    ends = sorted(k for k, neighbors in graph.items() if len(neighbors) == 1)
    if len(ends) != 2 or any(len(neighbors) > 2 for neighbors in graph.values()):
        raise ValueError("Select one open centerline with no branches or closed loops.")
    result, previous, current = [], None, ends[0]
    while current is not None:
        result.append(points[current])
        following = [v for v in graph[current] if v != previous]
        previous, current = current, (following[0] if following else None)
        if len(result) > len(graph):
            raise ValueError("The centerline contains a loop.")
    if len(result) != len(graph):
        raise ValueError("The selected edges are disconnected.")
    return result


def rounded_path(points, radius, step):
    """Circular fillets in XY, interpolating height along each fillet."""
    if radius <= EPS:
        return list(points)
    corners = [None] * len(points)
    for i in range(1, len(points) - 1):
        a, b, c = points[i-1:i+2]
        l0, l1 = math.dist(a[:2], b[:2]), math.dist(b[:2], c[:2])
        if min(l0, l1) < EPS:
            raise ValueError("Vertical edges cannot form a road centerline.")
        u = ((b[0]-a[0])/l0, (b[1]-a[1])/l0)
        v = ((c[0]-b[0])/l1, (c[1]-b[1])/l1)
        theta = math.acos(max(-1.0, min(1.0, u[0]*v[0]+u[1]*v[1])))
        if theta < 1e-5:
            continue
        if theta > math.pi - 0.05:
            raise ValueError("A centerline cannot double back on itself.")
        tangent = radius * math.tan(theta/2)
        if tangent > min(l0, l1) * 0.49:
            raise ValueError("The corner radius does not fit these edges. Reduce the radius or lengthen the centerline.")
        start, end = mix(b, a, tangent/l0), mix(b, c, tangent/l1)
        turn = 1 if u[0]*v[1]-u[1]*v[0] > 0 else -1
        center = (start[0]-turn*u[1]*radius, start[1]+turn*u[0]*radius)
        angle = math.atan2(start[1]-center[1], start[0]-center[0])
        count = max(2, math.ceil(radius*theta/step), math.ceil(theta/math.radians(10)))
        corners[i] = [
            (center[0]+radius*math.cos(angle+turn*theta*j/count),
             center[1]+radius*math.sin(angle+turn*theta*j/count),
             start[2]+(end[2]-start[2])*j/count)
            for j in range(count+1)
        ]
    out = [tuple(points[0])]
    for i in range(1, len(points)-1):
        out.extend(corners[i] or [tuple(points[i])])
    out.append(tuple(points[-1]))
    return out


def resample(points, step):
    result = [tuple(points[0])]
    for a, b in zip(points, points[1:]):
        horizontal = math.dist(a[:2], b[:2])
        if horizontal < 0.001:
            raise ValueError("Centerline segments must have horizontal length of at least 1 mm.")
        n = max(1, math.ceil(horizontal / step))
        if len(result) + n > 10000:
            raise ValueError("Too many stations; increase station interval or shorten the selection.")
        result.extend(mix(a, b, j/n) for j in range(1, n+1))
    return result


def frames(points):
    directions = []
    for a, b in zip(points, points[1:]):
        length = math.dist(a[:2], b[:2])
        directions.append(((b[0]-a[0])/length, (b[1]-a[1])/length))
    result = []
    for i in range(len(points)):
        u = directions[max(0, i-1)]
        v = directions[min(i, len(directions)-1)]
        # +lateral is right of travel, matching TerraRoad's section axes.
        normal = (u[1]+v[1], -u[0]-v[0])
        magnitude = math.hypot(*normal)
        if magnitude < EPS:
            raise ValueError("The centerline turns back on itself.")
        normal = (normal[0]/magnitude, normal[1]/magnitude)
        dot = normal[0]*v[1]-normal[1]*v[0]
        if dot < 0.25:
            raise ValueError("A corner is too sharp; round the corner or revise the centerline.")
        result.append((normal[0]/dot, normal[1]/dot))
    return result


def section(p):
    """(part, polygon in lateral/vertical metres, color)."""
    w = p.lanes * p.lane_width
    half = w / 2
    parts = []
    def slab(name, a, b, za, zb, thickness, color):
        if b-a > EPS:
            parts.append((name, [(a, za-thickness), (b, zb-thickness), (b, zb), (a, za)], color))
    asphalt = (0.18, 0.19, 0.20)
    concrete = (0.67, 0.67, 0.64)
    grass = (0.27, 0.48, 0.20)
    if p.median > EPS:
        # On divided roads lanes are per carriageway, as in the original.
        for side in (-1, 1):
            lo, hi = sorted((side*p.median/2, side*(p.median/2+w)))
            za, zb = ((-w*p.crown, 0) if side < 0 else (0, -w*p.crown))
            slab("Pavement", lo, hi, za, zb, p.thickness, asphalt)
        slab("Median", -p.median/2, p.median/2, 0, 0, 0.15, grass)
        outer = p.median/2+w
        edge_z = -w*p.crown
    else:
        slab("Pavement", -half, 0, -half*p.crown, 0, p.thickness, asphalt)
        slab("Pavement", 0, half, 0, -half*p.crown, p.thickness, asphalt)
        outer, edge_z = half, -half*p.crown
    for side in (-1, 1):
        edge, height = outer, edge_z
        for name, width, rise, thickness, color in (
            ("Shoulder", p.shoulder, 0, p.thickness, (0.39, 0.38, 0.35)),
            ("Curb", p.curb_width, p.curb_height, p.curb_height+p.thickness, concrete),
            ("Verge", p.verge, 0, 0.15, grass),
            ("Sidewalk", p.sidewalk, 0, p.sidewalk_thickness, concrete),
        ):
            if width <= EPS:
                continue
            height += rise
            a, b = sorted((side*edge, side*(edge+width)))
            slab(name, a, b, height, height, thickness, color)
            edge += width
    return parts


def station_lengths(points):
    result = [0.0]
    for a, b in zip(points, points[1:]):
        result.append(result[-1]+math.dist(a[:2], b[:2]))
    return result


def slice_path(points, stations, start, end):
    out = []
    for i, (a, b) in enumerate(zip(points, points[1:])):
        lo, hi = max(start, stations[i]), min(end, stations[i+1])
        if hi-lo <= EPS:
            continue
        span = stations[i+1]-stations[i]
        first, last = mix(a, b, (lo-stations[i])/span), mix(a, b, (hi-stations[i])/span)
        if not out or distance(first, out[-1]) > EPS:
            out.append(first)
        out.append(last)
    return out


def marking_specs(p):
    if not p.markings:
        return []
    out = []
    width = p.lanes*p.lane_width
    if p.median > EPS:
        ranges = [(-p.median/2-width, -p.median/2), (p.median/2, p.median/2+width)]
    else:
        ranges = [(-width/2, width/2)]
    for lo, hi in ranges:
        out.extend([(lo+p.line_width, False), (hi-p.line_width, False)])
        out.extend((lo+j*p.lane_width, True) for j in range(1, p.lanes))
    return out


def pavement_z(x, p):
    return -(abs(x)-p.median/2)*p.crown if p.median > EPS else -abs(x)*p.crown


def _area(poly):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1])))/2


def _segments_cross(a,b,c,d):
    def orient(p,q,r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return orient(a,b,c)*orient(a,b,d) < -EPS and orient(c,d,a)*orient(c,d,b) < -EPS


def prepare(points, p, specs=None):
    p.validate()
    if len(points) < 2:
        raise ValueError("At least two centerline points are required.")
    points = [tuple(float(v) for v in point) for point in points]
    if any(len(pt) != 3 or not all(math.isfinite(v) for v in pt) for pt in points):
        raise ValueError("Centerline coordinates must be finite XYZ values.")
    # Ignore redundant collinear vertices before filleting; retain changes of grade.
    cleaned = [points[0]]
    for i in range(1,len(points)-1):
        a,b,c = cleaned[-1],points[i],points[i+1]
        ab,bc = distance(a,b),distance(b,c)
        if ab < EPS or bc < EPS:
            raise ValueError("Repeated centerline points are not supported.")
        if abs(ab+bc-distance(a,c)) > 1e-6:
            cleaned.append(b)
    cleaned.append(points[-1])
    for i in range(len(cleaned)-1):
        for j in range(i+2,len(cleaned)-1):
            if _segments_cross(cleaned[i],cleaned[i+1],cleaned[j],cleaned[j+1]):
                raise ValueError("This centerline crosses itself. Split it into separate roads.")
    route = resample(rounded_path(cleaned,p.radius,p.station_interval),p.station_interval)
    normals = frames(route)
    specs = section(p) if specs is None else specs
    extent = max(abs(x+p.offset) for _,poly,_ in specs for x,_ in poly)
    # Each offset station must advance along the segment on both sides.
    # This prevents the inside of a tight bend folding over itself.
    for i,(a,b) in enumerate(zip(route,route[1:])):
        dx,dy = b[0]-a[0], b[1]-a[1]
        for side in (-extent,extent):
            advance = ((dx+side*(normals[i+1][0]-normals[i][0]))*dx
                       +(dy+side*(normals[i+1][1]-normals[i][1]))*dy)
            if advance <= EPS:
                raise ValueError("The road is wider than this bend permits. Increase the corner radius or reduce widths.")
    return route,normals,specs


def make_road(points, p, name="TerraRoad"):
    """Build off-document; only the completed group enters the undo command."""
    from PySide6.QtGui import QMatrix4x4, QVector3D
    from core.group import Group
    from core.mesh import Mesh

    route,normals,specs = prepare(points,p)
    origin = tuple(points[0])
    local = [tuple(v-o for v,o in zip(pt,origin)) for pt in route]
    stations = station_lengths(local)
    group = Group(name=name)
    group.xform = QMatrix4x4()
    group.xform.translate(QVector3D(*origin))
    quantities = {}

    def sweep(mesh, poly, path, axes, color):
        rings = [[QVector3D(pt[0]+n[0]*(x+p.offset),pt[1]+n[1]*(x+p.offset),pt[2]+z+p.elevation)
                  for x,z in poly] for pt,n in zip(path,axes)]
        def face(vertices):
            f = mesh.add_face(vertices)
            f.attrs["color"] = color
        # Polygon winding is CCW in the section XZ plane. At travel +Y,
        # its normal points backward, so the first cap keeps this winding.
        face(rings[0])
        face(list(reversed(rings[-1])))
        for a,b in zip(rings,rings[1:]):
            for j in range(len(poly)):
                k = (j+1)%len(poly)
                # Triangles remain planar across grade/corner transitions.
                face([a[j],b[j],b[k]])
                face([a[j],b[k],a[k]])

    for part_name,poly,color in specs:
        # Keep each swept section piece as its own solid; the two crown halves
        # meet at the center but must not weld their coincident internal caps.
        mesh = Mesh()
        sweep(mesh,poly,local,normals,color)
        child = Group(mesh,name=part_name)
        group.children.append(child)
        values = quantities.setdefault(part_name,{"length_m":0.0,"area_m2":0.0,"volume_m3":0.0})
        width = max(x for x,_ in poly)-min(x for x,_ in poly)
        values["length_m"] += stations[-1]
        values["area_m2"] += width*stations[-1]
        values["volume_m3"] += _area(poly)*stations[-1]
    # Clip dashed markings by station; the width and crown follow the road.
    for offset,dashed in marking_specs(p):
        mesh = Mesh()
        intervals = [(0,stations[-1])]
        if dashed:
            intervals = []
            start = 0.0
            while start < stations[-1]-EPS:
                intervals.append((start,min(start+p.dash,stations[-1])))
                start += p.dash+p.gap
                if len(intervals)>10000:
                    raise ValueError("Too many lane marking dashes.")
        marked_length = 0.0
        x0,x1 = offset-p.line_width/2,offset+p.line_width/2
        z0,z1 = pavement_z(x0,p)+0.002,pavement_z(x1,p)+0.002
        poly = [(x0,z0),(x1,z1),(x1,z1+0.001),(x0,z0+0.001)]
        for lo,hi in intervals:
            path = slice_path(local,stations,lo,hi)
            if len(path)>1:
                sweep(mesh,poly,path,frames(path),(0.96,0.94,0.82))
                marked_length += hi-lo
        group.children.append(Group(mesh,name="Dashed lane line" if dashed else "Edge line"))
        values = quantities.setdefault("Markings",{"length_m":0.0,"area_m2":0.0,"volume_m3":0.0})
        values["length_m"] += marked_length
        values["area_m2"] += marked_length*p.line_width
        values["volume_m3"] += marked_length*p.line_width*0.001
    group.ext = {KEY:{"schema":1,"version":VERSION,
                      "points":[[v-o for v,o in zip(pt,origin)] for pt in points],
                      "parameters":asdict(p),"quantities":quantities,
                      "centerline_length_m":stations[-1]}}
    return group


def support(name):
    """Load private helpers by absolute path (plugin folders aren't on sys.path)."""
    module_name=__name__+'_'+name
    if module_name not in sys.modules:
        target=Path(__file__).with_name('_TerraRoad')/(name+'.py')
        spec=importlib.util.spec_from_file_location(module_name,target)
        module=importlib.util.module_from_spec(spec)
        sys.modules[module_name]=module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(module_name,None)
            raise
    return sys.modules[module_name]


def make_detailed_road(points, values, name='TerraRoad'):
    return support('model').components(support('builder').make_road(sys.modules[__name__],support('section'),points,values,name))


def setup(app):
    """Native IngeTrazo menus. Import Qt only when the host loads the plugin."""
    from PySide6.QtWidgets import (
        QCheckBox,QDialog,QDialogButtonBox,QDoubleSpinBox,QFileDialog,
        QFormLayout,QLabel,QMessageBox,QScrollArea,QSpinBox,QVBoxLayout,QWidget,
    )
    from core.history import Command
    from core.mesh import Edge

    def ReplaceRoad(new,old=None):
        return support('model').Replace(sys.modules[__name__],new,old)

    def run(command):
        app.viewport.history.execute(command)
        if app.viewport.history.last_error:
            raise RuntimeError(app.viewport.history.last_error)
        app.viewport.notify_scene_changed()
        app.viewport.update()

    def selected_road():
        roads = [g for g in app.scene.selection if KEY in (getattr(g,"ext",None) or {})]
        if len(roads)!=1:
            raise ValueError("Select one TerraRoad road group first.")
        if roads[0] not in app.scene.groups:
            raise ValueError("Exit group editing and select the complete road.")
        return roads[0]

    def parameters(initial):
        from PySide6.QtCore import QSettings
        system=support('units').settings().value('system','metric')
        factor=1/.3048 if system=='imperial' else 1
        unit_name='feet' if system=='imperial' else 'metres'
        dialog = QDialog(app.window)
        dialog.setWindowTitle(f"TerraRoad — Road settings ({unit_name})")
        outer = QVBoxLayout(dialog)
        note = QLabel(f"Native development port: centerline corridors.\nAll distances are in {unit_name}; crown is a fraction (0.02 = 2%).\nFor divided roads, lane count is per carriageway.")
        note.setWordWrap(True)
        outer.addWidget(note)
        area = QScrollArea()
        area.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        fields = {}
        labels = {
            "lanes":"Lanes", "lane_width":"Lane width", "thickness":"Pavement thickness",
            "crown":"Crown (fraction)", "median":"Median width (0 = undivided)",
            "shoulder":"Shoulder width, each side", "curb_width":"Curb width, each side",
            "curb_height":"Curb rise", "verge":"Verge width, each side",
            "sidewalk":"Sidewalk width, each side", "sidewalk_thickness":"Sidewalk thickness",
            "markings":"Lane and edge markings", "line_width":"Marking width",
            "dash":"Dash length", "gap":"Dash gap", "radius":"Corner radius (0 = miter)",
            "station_interval":"Maximum station spacing", "offset":"Lateral offset",
            "elevation":"Elevation adjustment",
        }
        for key,value in asdict(initial).items():
            if key=="markings":
                widget = QCheckBox()
                widget.setChecked(value)
            elif key=="lanes":
                widget = QSpinBox()
                widget.setRange(1,20)
                widget.setValue(value)
            else:
                widget = QDoubleSpinBox()
                widget.setDecimals(6 if system=='imperial' else 3)
                widget.setRange(-10000 if key in ("offset","elevation") else 0,10000)
                widget.setValue(value*factor if key!='crown' else value)
                widget.setSingleStep(0.01 if key=="crown" else 0.1)
            fields[key]=widget
            form.addRow(labels[key],widget)
        area.setWidget(content)
        outer.addWidget(area)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)
        dialog.resize(520,740)
        if dialog.exec()!=QDialog.Accepted:
            return None
        result = Parameters(**{k:(w.isChecked() if k=="markings" else w.value()) for k,w in fields.items()})
        if system=='imperial':
            for key in fields:
                if key not in ('markings','lanes','crown'):
                    setattr(result,key,getattr(result,key)*.3048)
        result.validate()
        return result

    def guarded(callback):
        def wrapped(*_):
            try:
                callback()
            except Exception as exc:
                QMessageBox.warning(app.window,"TerraRoad",str(exc))
        return wrapped

    def create():
        if app.scene.edit_group is not None:
            raise ValueError("Exit group editing before creating a road.")
        selection = app.scene.selection
        if not selection or any(not isinstance(e,Edge) for e in selection):
            raise ValueError("Select only the edges of one open centerline, then create the road.")
        points = ordered_path([(e.a.toTuple(),e.b.toTuple()) for e in selection])
        p = parameters(Parameters())
        if p is None:
            return
        number = 1
        names = {g.name for g in app.scene.groups}
        while f"TerraRoad {number}" in names:
            number += 1
        run(ReplaceRoad(make_road(points,p,f"TerraRoad {number}")))

    def rebuild(edit=True):
        if app.scene.edit_group is not None:
            raise ValueError("Exit group editing before rebuilding a road.")
        old = selected_road()
        data = old.ext[KEY]
        if 'values' in data:
            if edit:
                open_designer()
                return
            new=support('model').rebuild(sys.modules[__name__],support('section'),data,data['values'],old.name)
            preserve(new,old)
            support('materials').apply(sys.modules[__name__],app.scene,new,data['values'])
            run(ReplaceRoad(new,old))
            return
        p = Parameters(**data["parameters"])
        if edit:
            p = parameters(p)
            if p is None:
                return
        new = make_road(data["points"],p,old.name)
        # make_road stores coordinates relative to its first input point;
        # the original local centerline always begins at zero.
        new.xform = copy.copy(old.xform)
        for attr in ("layer","ifc","uid","hidden","locked","axes","material"):
            setattr(new,attr,copy.deepcopy(getattr(old,attr)))
        new.ext = {**copy.deepcopy(old.ext),KEY:new.ext[KEY]}
        run(ReplaceRoad(new,old))

    def preserve(new,old):
        new.xform=copy.copy(old.xform)
        for attr in ('layer','ifc','uid','hidden','locked','axes','material'):
            setattr(new,attr,copy.deepcopy(getattr(old,attr)))
        new.ext={**copy.deepcopy(old.ext),KEY:new.ext[KEY]}

    designer=None
    def open_designer():
        nonlocal designer
        if designer is None:
            designer=support('panel').Designer(app,sys.modules[__name__],support('section'),
                lambda new,old=None:run(ReplaceRoad(new,old)),preserve,export)
        designer.refresh_selection(load_settings=True)
        designer.search.clear()
        designer.filter_sections('')
        designer.fold_all(False)
        designer.show()
        designer.raise_()
        designer.activateWindow()
        return designer

    def export():
        from PySide6.QtCore import QSettings
        system=support('units').settings().value('system','metric')
        unit_api=support('units')
        len_unit='ft' if system=='imperial' else 'm'
        area_unit='ft2' if system=='imperial' else 'm2'
        vol_unit='ft3' if system=='imperial' else 'm3'
        roads = [g for g in app.scene.groups if KEY in (g.ext or {})]
        if not roads:
            raise ValueError("There are no native TerraRoad roads in this document.")
        filename,_ = QFileDialog.getSaveFileName(app.window,"TerraRoad quantities","terraroad_quantities.csv","CSV (*.csv)")
        if not filename:
            return
        with open(filename,"w",newline="",encoding="utf-8-sig") as stream:
            writer=csv.writer(stream)
            writer.writerow(["Road","Part",f"Plan length ({len_unit})",f"Plan area ({area_unit})",f"Section volume ({vol_unit})"])
            for road in roads:
                for part,values in road.ext[KEY]["quantities"].items():
                    writer.writerow([road.name,part,
                        round(values['length_m']/(.3048 if system=='imperial' else 1),4),
                        round(unit_api.area(values['area_m2'],system)[0],4),
                        round(unit_api.volume(values['volume_m3'],system)[0],4)])
        app.viewport.flash_status("TerraRoad quantities exported",3000)

    def about():
        QMessageBox.information(app.window,"TerraRoad for IngeTrazo",
            f"TerraRoad {VERSION} — native Python development port\n"
            "Target: IngeTrazo 0.5.9\nOriginal TerraRoad 172.0.0: The Court Group\n\n"
            "Implemented: centerline pavement, crowned sections, divided roads, shoulders, curbs, verges, sidewalks, markings, circular corners, selected-face road/junction conversion, editing, undo/redo, metric/imperial units, language selection and CSV quantities.\n\n"
            "Also implemented: street lights, traffic signals, zebra crossings, parking stall paint, level T/X junction/roundabout networks, right-click editing and Site & Map reference images/traced roads.\n\n"
            "New in 0.6: separate road/junction groups with component parts; drawn roads; face lanes, medians, parking, arrows and shared mouths; yellow keep-clear boxes; rounded median ends; local width/level edits, U-turns, deck bridges and two-corner map cropping.\n\n"
            "Still pending: curved/adaptive face layouts, adaptive junction flares, terrain drape and cut/fill, arch/culvert bridges, standalone power lines, studs and advanced original design rules. Some technical notes retain English.\n\n"
            "Quantities use plan length and section dimensions; they are not terrain cut/fill or a measured solid takeoff. Manual geometry edits and scaling are not reflected in parameters or quantities.")

    menu = app.add_menu("TerraRoad")
    menu.addAction("TerraRoad designer — original sections…",guarded(open_designer))
    menu.addAction("Create road from selected centerline…",guarded(open_designer))
    menu.addAction("Edit selected road…",guarded(lambda:rebuild(True)))
    menu.addAction("Rebuild selected road",guarded(lambda:rebuild(False)))
    menu.addAction("Export quantities (CSV)…",guarded(export))
    menu.addSeparator()
    menu.addAction("About / port status…",guarded(about))

    if hasattr(app,'add_context_menu'):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QInputDialog
        from core.mesh import Face
        def context_menu(menu,selection):
            roads=[g for g in selection if KEY in (getattr(g,'ext',None) or {})]
            faces=[f for f in selection if isinstance(f,Face)]
            edges=[e for e in selection if isinstance(e,Edge)]
            if not (roads or faces or edges):
                return
            here=menu.addMenu('TerraRoad')
            scene=app.scene
            def add(label,fn):
                def later():
                    if app.scene is scene:
                        guarded(fn)()
                here.addAction(label,lambda _checked=False:QTimer.singleShot(0,later))
            def edit(road=None):
                if road is not None:
                    if road not in app.scene.groups:
                        raise ValueError('Select the complete TerraRoad road outside group editing.')
                    picked_edges={item for item in app.scene.selection if isinstance(item,Edge)}
                    app.scene.selection.clear()
                    app.scene.selection.update(picked_edges)
                    app.scene.selection.add(road)
                return open_designer()
            if len(roads)==1:
                road=roads[0]
                data=road.ext[KEY]
                add('Edit road / apply a style…',lambda:edit(road))
                add('Load its settings into the panel',lambda:edit(road).load_selected())
                def rename():
                    panel=edit(road)
                    name,ok=QInputDialog.getText(panel,'TerraRoad — rename road','Name',text=road.name)
                    if ok and name.strip():
                        panel.fields['road_name'].setText(name.strip())
                        panel.build_road()
                add('Rename…',rename)
                if not data.get('face_road'):
                    def mirror():
                        panel=edit(road)
                        values=panel.collect()
                        values['mirror_section']=not support('section').truth(values.get('mirror_section'))
                        panel.apply(values)
                        panel.build_road()
                    add('Turn the section round (mirror)',mirror)
                add('Rebuild / repair selected road',lambda:(edit(road),rebuild(False)))
                if data.get('face_road'):
                    add('Road ↔ junction',lambda:edit(road).swap_face_kind())
                    add('Wider or narrower…',lambda:edit(road).resize_face())
                    if not data.get('network_source'):
                        add('Arrow in a lane…',lambda:edit(road).actions.face_mark('arrow'))
                        add('Crossing across it…',lambda:edit(road).actions.face_mark('crossing'))
                        add('Remove arrows / crossings',lambda:edit(road).actions.clear_marks())
                        add('Set the line its markings follow',lambda:edit(road).actions.spine())
                        add('Work out markings from the face',lambda:edit(road).actions.spine(True))
                        add('Connect adjoining face roads',lambda:edit(road).actions.connect())
                        add('Cut into roads, turns and junctions',lambda:edit(road).actions.split())
                else:
                    if not data.get('network'):
                        add('Branch off this road…',lambda:edit(road).actions.branch())
                        add('Move a centerline point…',lambda:edit(road).actions.move_point())
                        for label,kind in [('Add a U-turn…','uturn'),('Add a zebra crossing…','crossing'),('Change the width here…','widen'),('Raise / lower the road…','grade'),('Add a deck bridge…','bridge')]:
                            add(label,lambda k=kind:edit(road).actions.feature(k))
                    def align(side):
                        panel=edit(road)
                        panel.apply({**panel.collect(),'line_side':side})
                        panel.build_road()
                    inside=here.addMenu('The line I drew is its…')
                    for label,side in [('Centre','centre'),('Left edge','left'),('Right edge','right')]:
                        inside.addAction(label,lambda _c=False,s=side:QTimer.singleShot(0,guarded(lambda:align(s))))
                add('Mirrored copy across a line…',lambda:edit(road).actions.mirror_copy())
                add('Make parts separate components',lambda:edit(road).actions.components())
                add('Delete road',lambda:edit(road).delete_road())
            elif roads:
                add('Open road settings…',lambda:edit())
                add('Rebuild all TerraRoad roads',lambda:edit().rebuild_all())
            if faces:
                add('Make selected face(s) into a road',lambda:edit().convert_faces('road'))
                add('Make selected face(s) into a junction',lambda:edit().convert_faces('junction'))
            if edges:
                add('Build road / junctions from selected lines…',lambda:edit())
            here.addSeparator()
            add('TerraRoad designer…',lambda:edit())
            add('Export quantities…',export)
        app.add_context_menu(context_menu)

    # Native Qt toolbar uses the same commands as the complete designer.
    from PySide6.QtWidgets import QToolBar
    from PySide6.QtGui import QIcon,QPixmap,QPainter,QColor,QPen
    from PySide6.QtCore import QSize,Qt
    toolbar=app.window.findChild(QToolBar,'TerraRoadToolbar')
    if toolbar is None:
        toolbar=QToolBar('TerraRoad',app.window)
        toolbar.setObjectName('TerraRoadToolbar')
        if hasattr(app.window,'addToolBar'):
            app.window.addToolBar(toolbar)
    else:
        toolbar.clear()
    toolbar.setIconSize(QSize(28,28))
    toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    image=QPixmap(32,32)
    image.fill(Qt.transparent)
    painter=QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor('#404d5c'))
    painter.setPen(QPen(QColor('#93b4cc'),2))
    painter.drawRoundedRect(3,1,26,30,4,4)
    painter.setPen(QPen(QColor('#ffffff'),2))
    painter.drawLine(8,3,8,29)
    painter.drawLine(24,3,24,29)
    painter.setPen(QPen(QColor('#ffcf55'),2,Qt.DashLine))
    painter.drawLine(16,3,16,29)
    painter.end()
    action=toolbar.addAction(QIcon(image),'TerraRoad')
    action.setToolTip('Open TerraRoad — all original sections and options')
    action.triggered.connect(guarded(open_designer))
    toolbar.show()
