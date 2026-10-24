# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Native selected-face road conversion with robust inset bands and undo.

Supports simple planar polygon faces with holes, including concave outlines.
Uses IngeTrazo's offset/arrangement engine; no external geometry dependency.
"""
import copy
import math

from PySide6.QtGui import QVector3D,QMatrix4x4
from core.mesh import Mesh,Face,Vertex
from core.group import Group
from core.history import Command
from core.offset import offset_regions,_dist_to_boundary
from core.arrangement import planar_arrangement
from core.triangulate import triangulate

UP=QVector3D(0,0,1)
EPS=1e-5


def area_xy(loop):
    return sum(a.x()*b.y()-b.x()*a.y() for a,b in zip(loop,loop[1:]+loop[:1]))/2


def ccw(loop):
    points=[QVector3D(p.x(),p.y(),0) for p in loop]
    return points if area_xy(points)>0 else points[::-1]


def inside(point,loop):
    x,y=point.x(),point.y()
    result=False
    for a,b in zip(loop,loop[1:]+loop[:1]):
        if (a.y()>y)!=(b.y()>y) and x<(b.x()-a.x())*(y-a.y())/(b.y()-a.y())+a.x():
            result=not result
    return result


def in_regions(point,regions):
    return any(inside(point,outer) and not any(inside(point,h) for h in holes) for outer,holes in regions)


def sample(outer,holes):
    triangles=triangulate(outer,holes,UP)
    if not triangles:
        raise ValueError('Could not triangulate the face boundary.')
    a,b,c=max(triangles,key=lambda tri:QVector3D.crossProduct(tri[1]-tri[0],tri[2]-tri[0]).lengthSquared())
    return (a+b+c)/3


def difference(a,b):
    if not a or not b:
        return a
    segments=[]
    for outer,holes in a+b:
        for loop in [outer]+holes:
            segments.extend(zip(loop,loop[1:]+loop[:1]))
    cells=planar_arrangement(segments,segments[0][0],UP)
    return [(ccw(outer),[ccw(h) for h in holes]) for outer,holes in cells
            if in_regions(sample(outer,holes),a) and not in_regions(sample(outer,holes),b)]


def union_regions(regions):
    """Dissolve internal arrangement edges before creating a closed solid."""
    if len(regions)<2:
        return regions
    segments=[(a,b) for outer,holes in regions for loop in [outer]+holes for a,b in zip(loop,loop[1:]+loop[:1])]
    cells=planar_arrangement(segments,segments[0][0],UP)
    boundary={}
    key=lambda p:(round(p.x(),5),round(p.y(),5))
    for outer,holes in cells:
        if not in_regions(sample(outer,holes),regions):
            continue
        for loop in [ccw(outer)]+[ccw(h)[::-1] for h in holes]:
            for a,b in zip(loop,loop[1:]+loop[:1]):
                ka,kb=key(a),key(b)
                if (kb,ka) in boundary:
                    boundary.pop((kb,ka))
                else:
                    boundary[(ka,kb)]=(a,b)
    loops=[]
    while boundary:
        edge=next(iter(boundary))
        start=edge[0]
        loop=[]
        for _ in range(len(boundary)+2):
            a,b=boundary.pop(edge)
            loop.append(a)
            if edge[1]==start:
                break
            choices=[e for e in boundary if e[0]==edge[1]]
            if not choices:
                raise ValueError('An accessory boundary could not be closed.')
            incoming=b-a
            def turn(e):
                c,d=boundary[e]
                v=d-c
                return math.atan2(incoming.x()*v.y()-incoming.y()*v.x(),QVector3D.dotProduct(incoming,v))%(2*math.pi)
            edge=min(choices,key=turn)
        if len(loop)>=3:
            loops.append(loop)
    # Arrangement boundaries can touch at a circle's tangent point. Two
    # lobes meeting there need separate solids, rather than a vertical edge
    # shared by four faces in one mesh.
    pending,loops=loops,[]
    while pending:
        loop=pending.pop()
        seen={}
        for i,point in enumerate(loop):
            k=key(point)
            if k in seen:
                j=seen[k]
                for part in (loop[j:i],loop[:j]+loop[i:]):
                    if len(part)>=3:
                        pending.append(part)
                break
            seen[k]=i
        else:
            loops.append(loop)
    outer=[(loop,[]) for loop in loops if area_xy(loop)>1e-8]
    for hole in (loop for loop in loops if area_xy(loop)<-1e-8):
        candidates=[entry for entry in outer if inside(hole[0],entry[0])]
        if candidates:
            min(candidates,key=lambda entry:abs(area_xy(entry[0])))[1].append(hole)
    return outer


def offset_shape(outer,holes,distance):
    if abs(distance)<1e-8:
        return [(outer,holes)]
    regions=offset_regions(outer,UP,distance)
    for hole in holes:
        cut=offset_regions(hole,UP,-distance)
        regions=difference(regions,cut)
    return regions


def regions_area(regions):
    return sum(abs(area_xy(outer))-sum(abs(area_xy(h)) for h in holes) for outer,holes in regions)


def distance_to_regions(point,regions):
    return min((_dist_to_boundary(point,loop) for outer,holes in regions for loop in [outer]+holes),default=math.inf)


def paint_cells(regions,reference,block,reach):
    """Partition perimeter bands at real chainages, then color each cell."""
    if block<=.001:
        raise ValueError('Curb paint block length must be positive.')
    segments=[]
    for outer,holes in regions:
        for loop in [outer]+holes:
            segments.extend(zip(loop,loop[1:]+loop[:1]))
    edges=[]
    cut_count=0
    for outer,holes in reference:
        for loop in [outer]+holes:
            at=0.
            next_cut=block
            for a,b in zip(loop,loop[1:]+loop[:1]):
                length=(b-a).length()
                if length<1e-7:
                    continue
                edges.append((a,b,at,length))
                normal=QVector3D(b.y()-a.y(),a.x()-b.x(),0).normalized()
                while next_cut<at+length-1e-7:
                    if next_cut>=at-1e-7:
                        point=a+(b-a)*((next_cut-at)/length)
                        segments.append((point-normal*reach,point+normal*reach))
                        cut_count+=1
                        if cut_count>2000:
                            raise ValueError('Too many painted curb blocks; increase their length.')
                    next_cut+=block
                at+=length
    cells=planar_arrangement(segments,segments[0][0],UP)
    result=[]
    for outer,holes in cells:
        point=sample(outer,holes)
        if not in_regions(point,regions):
            continue
        best=(math.inf,0.)
        for a,b,at,length in edges:
            t=max(0.,min(1.,QVector3D.dotProduct(point-a,b-a)/(length*length)))
            d=(point-(a+(b-a)*t)).lengthSquared()
            if d<best[0]:
                best=(d,at+t*length)
        index=int((best[1]+1e-7)/block)
        result.append(([(ccw(outer),[ccw(h) for h in holes])],index))
    return result


def envelope(poly,x):
    lo,hi=min(a for a,b in poly),max(a for a,b in poly)
    if lo-1e-4<=x<=hi+1e-4:
        x=max(lo,min(hi,x))
    zs=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if min(a[0],b[0])-1e-7<=x<=max(a[0],b[0])+1e-7:
            if abs(b[0]-a[0])<1e-9:
                zs.extend((a[1],b[1]))
            else:
                t=(x-a[0])/(b[0]-a[0])
                zs.append(a[1]+(b[1]-a[1])*t)
    if not zs:
        raise ValueError('Invalid roadside profile.')
    return min(zs),max(zs)


def solid(regions,top,bottom,color):
    mesh=Mesh()
    def face(loop,holes=None):
        f=mesh.add_face(loop,holes)
        f.attrs['color']=color
    for outer,holes in regions:
        # Face loops need a consistent outer CCW / inner CW winding for walls.
        outer=ccw(outer)
        holes=[ccw(h)[::-1] for h in holes]
        lifted=lambda loop,fn:[QVector3D(p.x(),p.y(),fn(p)) for p in loop]
        face(lifted(outer,top),[lifted(h,top) for h in holes])
        face(lifted(outer,bottom)[::-1],[lifted(h,bottom)[::-1] for h in holes])
        for loop in [outer]+holes:
            for a,b in zip(loop,loop[1:]+loop[:1]):
                at,bt=QVector3D(a.x(),a.y(),top(a)),QVector3D(b.x(),b.y(),top(b))
                ab,bb=QVector3D(a.x(),a.y(),bottom(a)),QVector3D(b.x(),b.y(),bottom(b))
                if min((at-ab).length(),(bt-bb).length())<1e-6:
                    raise ValueError('A face-road band collapses to zero thickness.')
                face([ab,bb,bt,at])
    return mesh


def from_loops(engine,section,loops,values,name,kind='road'):
    p=section.parameters(values)
    points=[QVector3D(*v) for v in loops[0]]
    if len(points)<3:
        raise ValueError('The face has fewer than three vertices.')
    normal=Face([Vertex(v) for v in points]).normal()
    if abs(normal.z())<.2:
        raise ValueError('Select a ground or sloping road face, not a vertical wall.')
    origin=points[0]
    if any(abs(QVector3D.dotProduct(normal,v-origin))>1e-4 for ring in loops for v in [QVector3D(*pt) for pt in ring]):
        raise ValueError('The selected face must be planar.')
    local=[[QVector3D(v[0]-origin.x(),v[1]-origin.y(),v[2]-origin.z()) for v in ring] for ring in loops]
    outer=ccw(local[0])
    holes=[ccw(h) for h in local[1:]]
    plane=lambda v:-(normal.x()*v.x()+normal.y()*v.y())/normal.z()+p['adjust_height']
    root=Group(name=name)
    root.xform=QMatrix4x4()
    root.xform.translate(origin)
    quantities={}
    warnings=[]
    colors=lambda key:tuple(int(section.COLORS.get(key,'#999999')[i:i+2],16)/255 for i in (1,3,5))
    # Perimeter bands are defined outward from the kerb face. On a face the
    # boundary has no travel direction; select the right-hand section's bands,
    # falling back to the left when the style only provides a left roadside.
    template=section.build(p)
    bands=template.outboard.get('right') or template.outboard.get('left') or []
    if kind=='junction':
        bands=[]
    depth=max((x for band in bands for x,z in band['loop']),default=0)
    reserve=p['face_means']=='reserve' and kind!='junction'
    base=depth if reserve else 0
    boundary=outer
    open_ends=None
    if kind=='road' and section.truth(values.get('_face_open_ends',True)):
        boundary,open_ends=engine.support('face_layout').open_boundary(outer,holes,values,depth)
    cache={}
    def shape(d):
        key=round(d,9)
        if key not in cache:
            regions=offset_shape(boundary,holes,d)
            if open_ends:
                for mask in open_ends['masks']:
                    regions=union_regions(engine.support('markings').intersection(regions,mask))
            cache[key]=regions
        return cache[key]
    paved=shape(base)
    mouths=[]
    for edge in values.get('_face_openings',[]):
        a,b=(QVector3D(*v)-origin for v in edge)
        direction=b-a
        length=math.hypot(direction.x(),direction.y())
        if length<1e-5:
            continue
        direction/=length
        n=QVector3D(-direction.y(),direction.x(),0)*max(depth*2+.01,1.)
        mouths.append((ccw([a-n,b-n,b+n,a+n]),[]))
    if mouths:
        # Continue the asphalt across the reserved perimeter at each join.
        extension=[]
        for mask,h in mouths:
            extension.extend(engine.support('markings').intersection([(outer,holes)],mask))
        paved=union_regions(paved+extension)
    if not paved:
        raise ValueError('The selected face is too narrow for the curb, planting and sidewalk widths. Reduce them or choose “asphalt” for what the face means.')
    asphalt=solid(paved,plane,lambda v:plane(v)-p['thickness'],colors('pavement'))
    root.children.append(Group(asphalt,name='Pavement'))
    area=regions_area(paved)
    quantities['Pavement']={'length_m':0,'area_m2':area,'volume_m3':area*p['thickness']}
    for band in bands:
        poly=band['loop']
        xs=sorted(set(x for x,z in poly))
        for lo,hi in zip(xs,xs[1:]):
            if hi-lo<1e-7:
                continue
            a,b=shape(base-hi),shape(base-lo)
            regions=union_regions(difference(a,b))
            if mouths:
                regions=union_regions(difference(regions,mouths))
            if not regions:
                continue
            def zvalue(v,which,lo=lo,hi=hi,a=a,b=b,poly=poly):
                # Boundary vertices are on one of the two known offset loops;
                # this preserves the exact profile height at mitred corners.
                da,db=distance_to_regions(v,a),distance_to_regions(v,b)
                x=lo+(hi-lo)*db/max(da+db,1e-9)
                return plane(v)+envelope(poly,x)[which]
            cells=(paint_cells(regions,paved,p['curb_block_length'],max(1.,depth*2+1.))
                   if band['key']=='curb' and p['curb_paint'] else [(regions,None)])
            for cell_number,(cell,paint_index) in enumerate(cells):
                color=colors(band['key'])
                if paint_index is not None:
                    color=(.15,.15,.14) if paint_index%2==0 else (.92,.91,.85)
                for piece_number,piece in enumerate(cell):
                    mesh=solid([piece],lambda v:zvalue(v,1),lambda v:zvalue(v,0),color)
                    suffix=f' {cell_number+1}' if paint_index is not None else ''
                    if len(cell)>1:
                        suffix+=f' part {piece_number+1}'
                    if band['key']=='curb' and p['curb_paint']:
                        for edge in mesh.edges:
                            edge.hidden=True
                    group=Group(mesh,name=band['name']+suffix)
                    group.ext={engine.KEY+'_part':{'key':band['key'],'paint_index':paint_index}}
                    root.children.append(group)
            area=regions_area(regions)
            avg_depth=sum(envelope(poly,x)[1]-envelope(poly,x)[0] for x in (lo,hi))/2
            q=quantities.setdefault(band['name'],{'length_m':0,'area_m2':0,'volume_m3':0})
            q['area_m2']+=area
            q['volume_m3']+=area*avg_depth
    layout=None
    if kind=='road' and not values.get('_bare_face'):
        layout=engine.support('face_layout').layout(engine,section,root,paved,p,values,plane,quantities)
    furniture=engine.support('furniture').add_to_face(root,engine,section,paved,p,plane,kind)
    if p['signal_placement']!='none':
        warnings.append('Signals need approach directions. Build a centerline network to place junction traffic signals automatically.')
    if kind=='junction':
        engine.support('markings').yellow_box(engine,root,paved,p,plane,quantities)
    root.ext={engine.KEY:{'schema':3,'kind':kind,'face_road':True,'values':copy.deepcopy(values),
        'loops':[[[v.x(),v.y(),v.z()] for v in ring] for ring in local],
        'quantities':quantities,'centerline_length_m':0,'furniture':furniture,'layout':layout,'open_ends':bool(open_ends),
        'section':{'left':template.left_extent,'right':template.right_extent,
                   'parts':[{'key':b['key'],'name':b['name'],'points':[list(pt) for pt in b['loop']]} for b in bands]},'warnings':warnings}}
    return engine.support('model').components(root)


def from_face(engine,section,face,values,name,kind='road'):
    loops=[[p.toTuple() for p in face.vertices]]+[[p.toTuple() for p in h] for h in face.holes]
    return from_loops(engine,section,loops,values,name,kind)


class ConvertFaces(Command):
    def __init__(self,faces,groups,key,values):
        self.faces,self.groups,self.key,self.values=faces,groups,key,copy.deepcopy(values)
        self.before=self.after=None
        self.selection=None
        self.document_before=None
        self.existed=False
    def do(self,scene):
        if self.before is None:
            if any(f not in scene.mesh.faces for f in self.faces):
                raise ValueError('The selected face is no longer in this model.')
            self.before=scene.mesh.capture_state()
            self.selection=set(scene.selection)
            self.existed=self.key in scene.plugin_data
            self.document_before=copy.deepcopy(scene.plugin_data.get(self.key))
            edges={edge for face in self.faces for loop in [face.loop]+face.hole_loops
                   for vertex in loop for edge in vertex.edges if face in edge.faces}
            for face in self.faces:
                scene.mesh.remove_face(face)
            for edge in edges:
                if not edge.faces:
                    scene.mesh.remove_edge(edge)
            self.after=scene.mesh.capture_state()
        else:
            scene.mesh.restore_state(self.after)
        for group in self.groups:
            if group not in scene.groups:
                scene.groups.append(group)
        scene.selection.clear()
        scene.selection.update(self.groups)
        data=copy.deepcopy(scene.plugin_data.get(self.key) or {})
        data['values']=copy.deepcopy(self.values)
        scene.plugin_data[self.key]=data
        scene.version+=1
    def undo(self,scene):
        scene.mesh.restore_state(self.before)
        for group in self.groups:
            scene.groups.remove(group)
        scene.selection.clear()
        scene.selection.update(self.selection)
        if self.existed:
            scene.plugin_data[self.key]=copy.deepcopy(self.document_before)
        else:
            scene.plugin_data.pop(self.key,None)
        scene.version+=1
