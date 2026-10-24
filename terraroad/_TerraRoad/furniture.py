# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Native road furniture. Dimensions and placement follow furniture.rb in SI.

Each item has an isolated mesh and transform, so rebuilding a road never
changes another road's furniture. Geometry is ordinary editable host geometry.
"""
import bisect
import math
from PySide6.QtGui import QVector3D,QMatrix4x4
from core.mesh import Mesh
from core.group import Group,_copy_mesh

METAL=(.30,.34,.37)
LAMP=(1,.91,.55)


def tube(mesh,a,b,r0,r1=None,color=METAL,n=10):
    a,b=QVector3D(*a),QVector3D(*b)
    axis=b-a
    if axis.length()<1e-6 or r0<=0:
        return
    axis.normalize()
    ref=QVector3D(0,0,1) if abs(axis.z())<.9 else QVector3D(0,1,0)
    u=QVector3D.crossProduct(ref,axis).normalized()
    v=QVector3D.crossProduct(axis,u)
    r1=r0 if r1 is None else max(r1,.0001)
    rings=[[point+(u*math.cos(2*math.pi*i/n)+v*math.sin(2*math.pi*i/n))*radius
            for i in range(n)] for point,radius in ((a,r0),(b,r1))]
    def face(pts):
        mesh.add_face(pts).attrs['color']=color
    face(rings[0][::-1])
    face(rings[1])
    for i in range(n):
        j=(i+1)%n
        face([rings[0][i],rings[0][j],rings[1][j],rings[1][i]])


def box(mesh,lo,hi,color=METAL):
    x,y,z=lo
    X,Y,Z=hi
    pts=[QVector3D(*p) for p in ((x,y,z),(X,y,z),(X,Y,z),(x,Y,z),
                                  (x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z))]
    for idx in ((3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
        mesh.add_face([pts[i] for i in idx]).attrs['color']=color


def path_tube(mesh,pts,r0,r1,color=METAL):
    for i,(a,b) in enumerate(zip(pts,pts[1:])):
        t=i/max(1,len(pts)-2)
        tube(mesh,a,b,r0+(r1-r0)*t,color=color,n=8)


def lamp(mesh,tip,reach,dia):
    x,y,z=tip
    length=max(dia*3,.3)
    width=max(dia*1.5,.18)
    box(mesh,(x-length/2,y-width/2,z-dia*.8),(x+length/2,y+width/2,z),METAL)
    box(mesh,(x-length*.4,y-width*.4,z-dia*.85),(x+length*.4,y+width*.4,z-dia*.8),LAMP)


def pole_mesh(p):
    h=max(p['pole_height'],.3048)
    d=max(p['pole_diameter'],.0254)
    arm=p['pole_arm']
    if h<=3*d:
        raise ValueError('Pole height must exceed three pole diameters.')
    mesh=Mesh()
    r=d/2
    kind=p['pole_type']
    signs=(1,-1) if p['pole_arms']=='double' or kind=='butterfly' else (1,)
    if kind=='pylon':
        # Four tapered lattice legs, cross-braced panels and three crossarms.
        width=max(arm*.32,d*4)
        for sx,sy in ((-1,-1),(-1,1),(1,-1),(1,1)):
            tube(mesh,(sx*width,sy*width,0),(sx*width*.18,sy*width*.18,h),r*.28)
        for i in range(8):
            z0,z1=h*i/8,h*(i+1)/8
            w0,w1=width*(1-.82*i/8),width*(1-.82*(i+1)/8)
            for side in (-1,1):
                tube(mesh,(-w0,side*w0,z0),(w1,side*w1,z1),r*.18)
                tube(mesh,(w0,side*w0,z0),(-w1,side*w1,z1),r*.18)
                tube(mesh,(side*w0,-w0,z0),(side*w1,w1,z1),r*.18)
                tube(mesh,(side*w0,w0,z0),(side*w1,-w1,z1),r*.18)
        for fraction in (.65,.8,.95):
            tube(mesh,(-arm,0,h*fraction),(arm,0,h*fraction),r*.35)
            for sign in (-1,1):
                tube(mesh,(sign*arm,0,h*fraction),(sign*arm,0,h*fraction-d*2),r*.7,color=(.5,.66,.5))
        return mesh
    tube(mesh,(0,0,0),(0,0,d*1.5),r*1.6)
    shaft=h-arm*.45 if kind=='curved' else h
    tube(mesh,(0,0,0),(0,0,shaft),r*1.15,r*.8)
    if kind=='heritage':
        tube(mesh,(0,0,0),(0,0,d*3),r*2.6,r*1.9,n=8)
        tube(mesh,(0,0,h-d*.4),(0,0,h),r*1.7)
        for sign in signs if arm>0 else (0,):
            x=arm*.55*sign
            tube(mesh,(0,0,h-d*.4),(x,0,h+d*.4),r*.5)
            tube(mesh,(x,0,h+d*.4),(x,0,h+d*3.6),d*1.9*.55,d*1.9*.75,color=LAMP,n=6)
            tube(mesh,(x,0,h+d*3.6),(x,0,h+d*5),d*1.9*.8,d*.15,n=6)
    else:
        for sign in signs:
            if arm<=0:
                lamp(mesh,(0,0,h),1,d)
                continue
            if kind=='curved':
                pts=[(sign*arm*(1-math.cos(i*math.pi/20)),0,shaft+arm*.45*math.sin(i*math.pi/20)) for i in range(11)]
                path_tube(mesh,pts,r*.85,r*.65)
                tip=pts[-1]
            elif kind=='butterfly':
                pts=[(sign*arm*i/12,0,h+arm*.3*math.sin(math.pi*i/24)) for i in range(13)]
                path_tube(mesh,pts,r*.55,r*.32)
                path_tube(mesh,[(0,0,h-arm*.55),(sign*arm*.3,0,h-arm*.1),pts[7]],r*.34,r*.24)
                tip=pts[-1]
            else:
                tip=(sign*arm,0,h+arm*.18)
                tube(mesh,(0,0,h),tip,r*.7)
            lamp(mesh,tip,sign*arm,d)
    return mesh


def signal_mesh(p):
    mesh=Mesh()
    h=max(p['signal_height'],.6096)
    arm=p['signal_arm']
    d=.254
    tube(mesh,(0,0,0),(0,0,.4572),d*.85)
    tube(mesh,(0,0,0),(0,0,h),d*.5)
    if arm>0:
        tube(mesh,(0,0,h),(arm,0,h),d*.3,n=8)
    # Head faces approaching travel, +Y in the item's local coordinate frame.
    box(mesh,(arm-.18,-.12,h-1.016),(arm+.18,.12,h),(.09,.10,.11))
    for i,color in enumerate(((.88,.035,.025),(1,.67,.02),(.035,.65,.16))):
        z=h-.19-i*.32
        tube(mesh,(arm,.12,z),(arm,.145,z),.115,color=color,n=12)
        # Visor over each illuminated lens.
        box(mesh,(arm-.13,.145,z+.105),(arm+.13,.30,z+.135),(.09,.10,.11))
    box(mesh,(-.15,-.18,2.2),(.15,.18,2.75),(.10,.10,.11))
    box(mesh,(-.10,.18,2.3),(.10,.19,2.65),LAMP)
    return mesh


def frame(route,axes,stations,s):
    i=max(0,min(len(stations)-2,bisect.bisect_right(stations,s)-1))
    t=(s-stations[i])/(stations[i+1]-stations[i])
    pt=tuple(a+(b-a)*t for a,b in zip(route[i],route[i+1]))
    axis=tuple(a+(b-a)*t for a,b in zip(axes[i],axes[i+1]))
    size=math.hypot(*axis)
    return pt,(axis[0]/size,axis[1]/size)


def instance(mesh,name,base,toward):
    group=Group(mesh,name=name)
    tx,ty=toward
    # Columns: toward carriageway, direction facing traffic, up, origin.
    group.xform=QMatrix4x4(tx,-ty,0,base[0],ty,tx,0,base[1],0,0,1,base[2],0,0,0,1)
    return group


def stations_between(total,spacing,start=0,end=None):
    if not math.isfinite(spacing) or spacing<=.001:
        raise ValueError('Furniture/crossing spacing must be positive.')
    end=total if end is None else end
    count=max(0,int(math.floor((end-start)/spacing))+1)
    if count>2000:
        raise ValueError('Too many furniture items; increase spacing or shorten the road.')
    return [start+i*spacing for i in range(count)]


def add_to_road(root,engine,template,route,axes,stations,p):
    counts={'light_poles':0,'traffic_signals':0}
    placement=p['pole_placement']
    stood={}
    if placement!='none':
        mesh=pole_mesh(p)
        assembly=Group(name='Light Poles')
        for i,s in enumerate(stations_between(stations[-1],p['pole_spacing'])):
            sides=(('left','right') if placement=='both' else
                   (('left' if i%2==0 else 'right'),) if placement=='alternating' else (placement,))
            for side in sides:
                anchor=template.pole_anchors.get(side)
                if anchor is None:
                    continue
                pt,n=frame(route,axes,stations,s)
                x,z=anchor[:2]
                if side!='median' and p['pole_stand'] in ('walk','verge'):
                    suffix='Sidewalk' if p['pole_stand']=='walk' else 'Green Verge'
                    part=next((part for part in template.parts if part.name==side.capitalize()+' '+suffix),None)
                    if part:
                        x=(min(v[0] for v in part.points)+max(v[0] for v in part.points))/2
                        z=max(v[1] for v in part.points)
                base=(pt[0]+n[0]*x,pt[1]+n[1]*x,pt[2]+z+p['adjust_height'])
                sign=-1 if side=='right' else 1
                item=instance(_copy_mesh(mesh) if not p.get('share_furniture') else mesh,
                              'Light Pole '+str(counts['light_poles']+1),base,(n[0]*sign,n[1]*sign))
                assembly.children.append(item)
                stood.setdefault(side,[]).append(item.xform)
                counts['light_poles']+=1
        if assembly.children:
            root.children.append(assembly)
        if p['pole_type']=='pylon':
            conductors=Mesh()
            for row in stood.values():
                for a,b in zip(row,row[1:]):
                    for level in (.65,.8,.95):
                        for sign in (-1,1):
                            start=a.map(QVector3D(sign*p['pole_arm'],0,p['pole_height']*level-p['pole_diameter']*2))
                            end=b.map(QVector3D(sign*p['pole_arm'],0,p['pole_height']*level-p['pole_diameter']*2))
                            span=(end-start).length()
                            av,bv=start.toTuple(),end.toTuple()
                            pts=[tuple(av[j]+(bv[j]-av[j])*i/16-(span*.035*4*i/16*(1-i/16) if j==2 else 0) for j in range(3)) for i in range(17)]
                            path_tube(conductors,pts,max(.0127,p['pole_diameter']*.06),max(.0127,p['pole_diameter']*.06))
            if conductors.faces:
                assembly.children.append(Group(conductors,name='Conductors'))
    signal_mode=p['signal_placement']
    ends=[0,1] if signal_mode=='all_ends' else list(p.get('_junction_ends',[])) if signal_mode=='junctions' else []
    if ends:
        mesh=signal_mesh(p)
        assembly=Group(name='Traffic Signals')
        for end in ends:
            s=min(p['signal_setback'],stations[-1]/3)
            if end:
                s=stations[-1]-s
            pt,n=frame(route,axes,stations,s)
            sides=('left','right') if p['signal_side']=='both' else (p['signal_side'],)
            for side in sides:
                # Swap travel left/right at the outward end so each head faces
                # its own approach, rather than both heads facing one way.
                effective=side if not end else ('left' if side=='right' else 'right')
                anchor=template.curb_anchors.get(effective)
                if not anchor:
                    continue
                x,z,direction=anchor[:3]
                x+=direction*p['signal_offset']
                base=(pt[0]+n[0]*x,pt[1]+n[1]*x,pt[2]+z+p['adjust_height'])
                sign=-1 if effective=='right' else 1
                assembly.children.append(instance(_copy_mesh(mesh),'Traffic Signal',base,(n[0]*sign,n[1]*sign)))
                counts['traffic_signals']+=1
        if assembly.children:
            root.children.append(assembly)
    return counts


def add_to_face(root,engine,section,regions,p,plane,kind):
    """Perimeter lighting follows the actual curb, including face holes."""
    if p['pole_placement']=='none' or (kind=='junction' and not p['junction_poles']):
        return {'light_poles':0,'traffic_signals':0}
    if p['pole_placement']=='median':
        return {'light_poles':0,'traffic_signals':0}
    # The outward perimeter is the right side of each CCW ring. Hole paths
    # run clockwise so outward points into the unpaved hole.
    template=section.build({**p,'pole_placement':'right'})
    curb=template.kerb_faces['right'][0]
    anchor=template.pole_anchors['right']
    distance=anchor[0]-curb
    z=anchor[1]
    if p['pole_stand'] in ('walk','verge'):
        suffix='Sidewalk' if p['pole_stand']=='walk' else 'Green Verge'
        part=next((part for part in template.parts if part.name=='Right '+suffix),None)
        if part:
            distance=(min(v[0] for v in part.points)+max(v[0] for v in part.points))/2-curb
            z=max(v[1] for v in part.points)
    mesh=pole_mesh(p)
    assembly=Group(name='Light Poles')
    count=0
    for outer,holes in regions:
        for index,ring in enumerate([outer]+holes):
            ring=ring if index==0 else ring[::-1]
            route=[(pt.x(),pt.y(),plane(pt)) for pt in ring]
            route.append(route[0])
            axes=engine.frames([route[-2]]+route+[route[1]])[1:-1]
            stations=engine.station_lengths(route)
            for s in stations_between(stations[-1],p['pole_spacing'],end=stations[-1]-1e-5):
                pt,n=frame(route,axes,stations,s)
                base=(pt[0]+n[0]*distance,pt[1]+n[1]*distance,pt[2]+z)
                assembly.children.append(instance(_copy_mesh(mesh),'Light Pole '+str(count+1),base,(-n[0],-n[1])))
                count+=1
                if count>2000:
                    raise ValueError('Too many face light poles; increase spacing.')
    if count:
        root.children.append(assembly)
    return {'light_poles':count,'traffic_signals':0}
