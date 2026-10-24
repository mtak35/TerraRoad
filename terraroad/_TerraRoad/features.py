# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Station-based road edits: smooth grade/width changes and bridge solids."""
import math
from PySide6.QtGui import QVector3D,QMatrix4x4


def nearest(point,route,stations):
    best=None
    for a,b,s,t in zip(route,route[1:],stations,stations[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy)
        f=max(0.,min(1.,((point.x()-a[0])*dx+(point.y()-a[1])*dy)/(length*length)))
        px,py=a[0]+dx*f,a[1]+dy*f
        dist=(point.x()-px)**2+(point.y()-py)**2
        entry=(dist,s+(t-s)*f,(dy/length,-dx/length),a[2]+(b[2]-a[2])*f)
        if best is None or dist<best[0]:
            best=entry
    return best[1:]


def weight(station,item):
    distance=abs(station-item['station'])-item['length']/2
    if distance<=0:
        return 1.
    taper=item.get('taper',0.)
    if taper<=0 or distance>=taper:
        return 0.
    t=1-distance/taper
    return t*t*(3-2*t)


def warp(engine,root,template,route,stations,items):
    changes=[f for f in items if f['type'] in ('grade','bridge','widen')]
    if not changes:
        return
    from core.group import transformed_mesh
    xc=template.params['offset']
    divided=engine.support('section').divided(template.params)
    median=template.params['median_width'] if divided else 0.
    left=abs(template.kerb_faces['left'][0]-xc)-median/2
    right=abs(template.kerb_faces['right'][0]-xc)-median/2
    for item in changes:
        if item['type']=='widen':
            extra=item.get('road',0.)
            a=extra if item.get('side')=='left' else extra/2 if item.get('side')=='both' else 0
            b=extra if item.get('side')=='right' else extra/2 if item.get('side')=='both' else 0
            if min(left+a,right+b)<.5 or (divided and median+item.get('median',0.)<.05):
                raise ValueError('This width change would erase a carriageway or median.')
    if len(changes)>30:
        raise ValueError('Use at most 30 local width/level changes per road.')
    def transform(v):
        key=(round(v.x(),6),round(v.y(),6))
        if key not in cache:
            cache[key]=nearest(v,route,stations)
        s,n,z=cache[key]
        # nearest returns the route normal; projection gives lateral distance.
        import bisect
        i=max(0,min(len(route)-2,bisect.bisect_right(stations,s)-1))
        t=(s-stations[i])/(stations[i+1]-stations[i])
        px=route[i][0]+(route[i+1][0]-route[i][0])*t
        py=route[i][1]+(route[i+1][1]-route[i][1])*t
        x=(v.x()-px)*n[0]+(v.y()-py)*n[1]-xc
        dx,dz=0.,0.
        for item in changes:
            w=weight(s,item)
            if item['type'] in ('grade','bridge'):
                dz+=item['rise']*w
            else:
                dm=item.get('median',0.) if divided else 0.
                road=item['road']
                side=item.get('side','both')
                if x<0:
                    extra=road if side=='left' else road/2 if side=='both' else 0.
                    factor=max(0.,min(1.,(-x-median/2)/max(left,.01)))
                    dx-=w*(dm/2*min(1.,-x/max(median/2,.001))+extra*factor)
                else:
                    extra=road if side=='right' else road/2 if side=='both' else 0.
                    factor=max(0.,min(1.,(x-median/2)/max(right,.01)))
                    dx+=w*(dm/2*min(1.,x/max(median/2,.001))+extra*factor)
        return QVector3D(v.x()+n[0]*dx,v.y()+n[1]*dx,v.z()+dz)
    def walk(group,matrix):
        frame=matrix*group.xform if group.xform is not None else matrix
        # Give each physical component its own mesh before deforming it.
        if group.mesh.vertices:
            group.mesh=transformed_mesh(group.mesh,frame)
            for vertex in list(group.mesh.vertices):
                group.mesh.place_vertex(vertex,transform(vertex.position))
        group.xform=QMatrix4x4()
        for child in group.children:
            walk(child,frame)
    cache={}
    for child in root.children:
        walk(child,QMatrix4x4())


def bridges(engine,section,root,template,route,axes,stations,p,items,quantities):
    from core.group import Group
    from core.mesh import Mesh
    api=engine.support('furniture')
    for item in items:
        if item['type']!='bridge':
            continue
        if min(item['width'],item['depth'],item['length'])<=0 or not 1<=item.get('spans',1)<=100:
            raise ValueError('Bridge width, depth and span must be positive; use 1 to 100 spans.')
        s=item['station']
        start,end=s-item['length']/2,s+item['length']/2
        a,n=api.frame(route,axes,stations,s)
        direction=(-n[1],n[0])
        width=item['width']
        depth=item['depth']
        top=a[2]+p['adjust_height']+item['rise']-p['thickness']
        half=item['length']/2
        assembly=Group(name='Bridge deck and supports')
        def box(label,x0,x1,y0,y1,z0,z1,color=(.66,.66,.63)):
            if min(x1-x0,y1-y0,z1-z0)<=1e-6:
                return
            from PySide6.QtGui import QVector3D
            corners=[QVector3D(a[0]+n[0]*x+direction[0]*y,a[1]+n[1]*x+direction[1]*y,z)
                for z in (z0,z1) for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
            mesh=Mesh()
            for indices in ((3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
                mesh.add_face([corners[i] for i in indices]).attrs['color']=color
            assembly.children.append(Group(mesh,name=label))
        box('Bridge deck',-width/2,width/2,-half,half,top-depth,top)
        for y in (-half,half):
            box('Bridge abutment',-width/2,width/2,y-.35,y+.35,a[2]-p['thickness'],top-depth)
        if item.get('parapet'):
            for x in (-width/2,width/2-.2):
                box('Bridge parapet',x,x+.2,-half,half,top,top+item['parapet_height'])
        # Multiple spans receive genuine intermediate piers.
        for i in range(1,max(1,item.get('spans',1))):
            y=-half+item['length']*i/item['spans']
            box('Bridge pier',-width*.3,width*.3,y-.3,y+.3,a[2]-p['thickness'],top-depth)
        root.children.append(assembly)
        q=quantities.setdefault('Bridge structure',dict(length_m=0.,area_m2=0.,volume_m3=0.))
        q['length_m']+=item['length']
        q['area_m2']+=width*item['length']
        q['volume_m3']+=width*item['length']*depth


def median_spans(total,items):
    spans=[(0.,total)]
    for item in items:
        if item['type']!='uturn':
            continue
        a,b=item['station']-item['length']/2,item['station']+item['length']/2
        spans=[pair for lo,hi in spans for pair in ((lo,min(hi,a)),(max(lo,b),hi)) if pair[1]-pair[0]>1e-5]
    return spans
