# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Stall paint ported from Sweep.parking_mesh; SI, on the bay surface."""
import bisect
import math
from PySide6.QtGui import QVector3D
from core.mesh import Mesh
from core.group import Group


def add_markings(root,engine,template,route,axes,stations,p):
    if not p['parking_marks'] or not template.parking_bays:
        return {}
    angle=int(p['parking_angle'])
    width=p['parking_stall_width']
    length=p['parking_parallel_length'] if angle==180 else p['parking_stall_length']
    half=p['parking_line_width']/2
    lift=p['parking_line_lift']
    pitch=length if angle==180 else width if angle==90 else width/math.sin(math.radians(angle))
    if min(half,width,length,pitch,lift)<=0:
        raise ValueError('Parking line width/lift, stall width and stall length must be positive.')
    if stations[-1]/pitch>10000:
        raise ValueError('Too many parking stalls; increase stall width or shorten the road.')
    quantity=dict(length_m=0.,area_m2=0.,volume_m3=0.)
    def point(s,x,bay,raise_by):
        if s<-.00001 or s>stations[-1]+.00001:
            raise ValueError('A parking line extends beyond the road.')
        i=max(0,min(len(stations)-2,bisect.bisect_right(stations,s)-1))
        t=(s-stations[i])/(stations[i+1]-stations[i])
        pt=engine.mix(route[i],route[i+1],t)
        n=engine.mix(axes[i],axes[i+1],t)
        a,b,z0,z1=bay
        z=z0+(z1-z0)*(x-a)/(b-a)
        return QVector3D(pt[0]+n[0]*x,pt[1]+n[1]*x,pt[2]+z+raise_by+p['adjust_height'])
    for bay_number,(aisle,back,z0,z1,direction) in enumerate(template.parking_bays):
        if angle in (90,180):
            run,span=0.,back-aisle
        else:
            run=length*math.cos(math.radians(angle))*direction
            span=length*math.sin(math.radians(angle))*direction
        depth=abs(back-aisle)
        limit=depth-p['parking_line_setback']
        if limit<=0:
            limit=depth/2
        if abs(span)>limit:
            factor=limit/abs(span)
            run,span=run*factor,span*factor
        line_length=math.hypot(run,span)
        if line_length<.0001:
            continue
        px,po=-span/line_length*half,run/line_length*half
        lo,hi=min(run,0)-abs(px),max(run,0)+abs(px)
        start=-lo
        number=1
        while start+hi<=stations[-1]+1e-7:
            mesh=Mesh()
            steps=max(1,math.ceil(abs(run)/.3))
            rails=[]
            for i in range(steps+1):
                t=i/steps
                s,x=start+run*t,aisle+span*t
                bay=(aisle,back,z0,z1)
                rails.append([point(s-px,x-po,bay,lift),point(s+px,x+po,bay,lift),
                              point(s-px,x-po,bay,0),point(s+px,x+po,bay,0)])
            def face(pts):
                mesh.add_face(pts).attrs['color']=(.96,.96,.92)
            # Orient the solid by the actual lateral direction of this bay.
            reverse=True
            def oriented(pts):
                face(pts[::-1] if reverse else pts)
            for a,b in zip(rails,rails[1:]):
                oriented([a[0],b[0],b[1],a[1]])
                oriented([a[2],a[3],b[3],b[2]])
                oriented([a[0],a[2],b[2],b[0]])
                oriented([a[1],b[1],b[3],a[3]])
            a,b=rails[0],rails[-1]
            oriented([a[0],a[1],a[3],a[2]])
            oriented([b[0],b[2],b[3],b[1]])
            for edge in mesh.edges:
                edge.hidden=True
            group=Group(mesh,name=f'Parking marking {bay_number+1}.{number}')
            group.ext={engine.KEY+'_part':{'key':'parking_marking'}}
            root.children.append(group)
            quantity['length_m']+=line_length
            quantity['area_m2']+=line_length*half*2
            quantity['volume_m3']+=line_length*half*2*lift
            start+=pitch
            number+=1
    return {'Parking markings':quantity}
