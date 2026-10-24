# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Clipped face markings and keep-clear junction boxes, without dependencies."""
import math
from PySide6.QtGui import QVector3D
from core.group import Group
from core.triangulate import triangulate


def cross(a,b):
    return a.x()*b.y()-a.y()*b.x()


def clip(poly,boundary):
    if sum(cross(a,b) for a,b in zip(boundary,boundary[1:]+boundary[:1]))<0:
        boundary=boundary[::-1]
    out=list(poly)
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):
        source,out=out,[]
        if not source:
            break
        for p,q in zip(source,source[1:]+source[:1]):
            dp,dq=cross(b-a,p-a),cross(b-a,q-a)
            if dp>=-1e-7:
                out.append(p)
            if (dp>=-1e-7)!=(dq>=-1e-7):
                out.append(p+(q-p)*(dp/(dp-dq)))
    clean=[]
    for p in out:
        if not clean or (p-clean[-1]).length()>1e-5:
            clean.append(p)
    if len(clean)>1 and (clean[0]-clean[-1]).length()<1e-5:
        clean.pop()
    while len(clean)>3:
        for i,p in enumerate(clean):
            a,b=clean[i-1],clean[(i+1)%len(clean)]
            if abs(cross(p-a,b-p))<1e-6*max(1.,(b-a).length()):
                clean.pop(i)
                break
        else:
            break
    area=abs(sum(cross(a,b) for a,b in zip(clean,clean[1:]+clean[:1])))/2
    return clean if len(clean)>=3 and area>1e-8 else []


def triangles(regions):
    return [list(tri) for outer,holes in regions for tri in triangulate(outer,holes,QVector3D(0,0,1))]


def intersection(regions,mask):
    # Clipping each triangulated cell handles concavity and holes exactly.
    turns=[cross(b-a,c-b) for a,b,c in zip(mask,mask[1:]+mask[:1],mask[2:]+mask[:2])]
    convex=all(t>=-1e-7 for t in turns) or all(t<=1e-7 for t in turns)
    masks=[mask] if convex else triangles([(mask,[])])
    return [(poly,[]) for tri in triangles(regions) for boundary in masks for poly in [clip(tri,boundary)] if poly]


def rectangle(origin,direction,s0,s1,x0,x1):
    ux,uy=direction
    point=lambda s,x:QVector3D(origin[0]+ux*s+uy*x,origin[1]+uy*s-ux*x,0)
    return [point(s0,x0),point(s1,x0),point(s1,x1),point(s0,x1)]


def add_solid_parts(engine,root,regions,top,bottom,color,name,key,quantities=None):
    api=engine.support('faces')
    assembly=Group(name=name)
    area=0.
    volume=0.
    for i,(outer,holes) in enumerate(regions):
        def clean(loop):
            out=[]
            for v in loop:
                if not out or (v-out[-1]).length()>1e-5:
                    out.append(v)
            if len(out)>1 and (out[0]-out[-1]).length()<1e-5:
                out.pop()
            return out
        outer=clean(outer)
        holes=[h for loop in holes for h in [clean(loop)] if len(h)>=3]
        if len(outer)<3 or abs(api.area_xy(outer))<1e-8:
            continue
        mesh=api.solid([(outer,holes)],top,bottom,color)
        if key in ('stripe','box','parking_marking','crossing','curb'):
            # Black model outlines otherwise cover sub-pixel road paint.
            for edge in mesh.edges:
                edge.hidden=True
        assembly.children.append(Group(mesh,name=f'{name} part {i+1}'))
        area+=api.regions_area([(outer,holes)])
        for a,b,c in triangulate(outer,holes,QVector3D(0,0,1)):
            triangle=abs(cross(b-a,c-a))/2
            volume+=triangle*sum(max(0,top(v)-bottom(v)) for v in (a,b,c))/3
    if assembly.children:
        assembly.ext={engine.KEY+'_part':{'key':key}}
        root.children.append(assembly)
        if quantities is not None:
            q=quantities.setdefault(name,dict(length_m=0.,area_m2=0.,volume_m3=0.))
            q['area_m2']+=area
            q['volume_m3']+=volume
    return assembly


def yellow_box(engine,root,regions,p,plane,quantities):
    if not p['box_junction']:
        return
    width,spacing,inset=p['box_line_width'],p['box_spacing'],p['box_inset']
    if width<=0 or spacing<=width or inset<0:
        raise ValueError('Keep-clear box line width must be positive and less than its spacing.')
    api=engine.support('faces')
    inner=[]
    for outer,holes in regions:
        inner.extend(api.offset_shape(outer,holes,inset))
    if not inner:
        return
    points=[v for outer,holes in inner for v in outer]
    size=max(max(v.x() for v in points)-min(v.x() for v in points),max(v.y() for v in points)-min(v.y() for v in points))
    if size/spacing>1000:
        raise ValueError('Too many keep-clear lines; increase box spacing.')
    color=(1.,.78,.04)
    lift=max(.001,p['stripe_lift'])
    for direction in ((math.sqrt(.5),math.sqrt(.5)),(math.sqrt(.5),-math.sqrt(.5))):
        ux,uy=direction
        ss=[v.x()*ux+v.y()*uy for v in points]
        xs=[v.x()*uy-v.y()*ux for v in points]
        a,b=min(ss)-1,max(ss)+1
        for i in range(math.floor(min(xs)/spacing),math.ceil(max(xs)/spacing)+1):
            x=i*spacing
            cells=intersection(inner,rectangle((0,0),direction,a,b,x-width/2,x+width/2))
            add_solid_parts(engine,root,cells,lambda v:plane(v)+lift,plane,color,'Yellow keep-clear box','box',quantities)


def arrow_mask(point,direction,length=3.,width=.3):
    ux,uy=direction
    # +s points towards the arrow head.
    outline=[(-length/2,-width/2),(length*.12,-width/2),(length*.12,-width*1.7),
             (length/2,0),(length*.12,width*1.7),(length*.12,width/2),(-length/2,width/2)]
    return [QVector3D(point[0]+ux*s+uy*x,point[1]+uy*s-ux*x,0) for s,x in outline]
