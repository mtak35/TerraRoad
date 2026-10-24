# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Circular circulatory pavement with tangent entry returns and traffic paint."""
import math
from PySide6.QtGui import QVector3D
from core.group import Group


def dimensions(p,roadside,half_width,entries=None):
    island=p['island_radius']
    apron=p['truck_apron']
    width=p['circulatory_width']
    if min(island,width)<=0:
        raise ValueError('Roundabout island radius and circulatory width must be positive.')
    outer=island+apron+width
    entry=max(p['entry_radius'],roadside+.1) if p['junction_radius_auto'] else p['entry_radius']
    if entry<=roadside:
        raise ValueError('Roundabout entry radius must exceed the roadside width, so curbs and sidewalks do not fold.')
    required=half_width+.2
    if entries:
        for a,b in zip(entries,entries[1:]+entries[:1]):
            angle=(b['angle']-a['angle'])%(2*math.pi)
            required=max(required,(max(a['left'],b['right'])+entry)/max(.05,math.sin(angle/2))-entry+.15)
    if outer<required:
        if not p['junction_radius_auto']:
            raise ValueError('The roundabout entries overlap. Increase its island radius/circulatory width or enable automatic radius.')
        outer=required
        island=outer-apron-width
    return island,apron,width,outer,entry


def corners(node,entries,p,roadside,half_width):
    island,apron,width,outer,radius=dimensions(p,roadside,half_width,entries)
    def side(arm,sign):
        dx,dy=arm['d']
        w=arm['left'] if sign==1 else arm['right']
        distance=math.sqrt((outer+radius)**2-(w+radius)**2)
        arm['trim']=max(arm['trim'],distance)
        if distance>arm['limit']:
            raise ValueError('The roundabout entry curves do not fit these approaches. Lengthen the centerlines or reduce the island/entry radii.')
        c=(dx*distance-dy*sign*(w+radius),dy*distance+dx*sign*(w+radius))
        start=(dx*distance-dy*sign*w,dy*distance+dx*sign*w)
        tangent=(c[0]*outer/(outer+radius),c[1]*outer/(outer+radius))
        a=math.atan2(start[1]-c[1],start[0]-c[0])
        b=math.atan2(tangent[1]-c[1],tangent[0]-c[0])
        sweep=(a-b)%(2*math.pi) if sign==1 else (b-a)%(2*math.pi)
        points=[(node[0]+c[0]+radius*math.cos(a-sign*sweep*i/24),node[1]+c[1]+radius*math.sin(a-sign*sweep*i/24),node[2]) for i in range(25)]
        return points,math.atan2(tangent[1],tangent[0])
    sides=[(side(a,1),side(a,-1)) for a in entries]
    result=[]
    for i,arm in enumerate(entries):
        left,begin=sides[i][0]
        right,end=sides[(i+1)%len(entries)][1]
        angle=(end-begin)%(2*math.pi)
        if angle>math.pi*1.5:
            raise ValueError('These roundabout entry curves overlap. Reduce the approach widths or entry radii.')
        circle=[(node[0]+outer*math.cos(begin+angle*j/32),node[1]+outer*math.sin(begin+angle*j/32),node[2]) for j in range(33)]
        result.append(left+circle[1:]+right[::-1][1:])
    return result


def add_details(engine,section,root,junction,node,entries,p,origin,quantities):
    api=engine.support('faces')
    marks=engine.support('markings')
    roadside=max((x for bands in section.build(p).outboard.values() for b in bands for x,z in b['loop']),default=0.)
    island,apron,width,outer,entry=dimensions(p,roadside,max(max(a['left'],a['right']) for a in entries),entries)
    cx,cy,cz=[node[i]-origin[i] for i in range(3)]
    jq=junction.ext[engine.KEY]['quantities']
    def add(container,regions,top,bottom,color,name,key):
        before=dict(jq.get(name,{}))
        part=marks.add_solid_parts(engine,container,regions,top,bottom,color,name,key,jq)
        q=quantities.setdefault(name,dict(length_m=0.,area_m2=0.,volume_m3=0.))
        for field in q:
            q[field]+=jq.get(name,{}).get(field,0)-before.get(field,0)
        return part
    plane=lambda v:cz+p['adjust_height']
    circle=lambda r:[QVector3D(cx+r*math.cos(i*math.pi/64),cy+r*math.sin(i*math.pi/64),0) for i in range(128)]
    curb_width=min(max(p['curb_width'],.15),island/3)
    assembly=Group(name='Roundabout island')
    if p['curb_paint']:
        count=max(8,math.ceil(2*math.pi*island/max(.05,p['curb_block_length'])))
        curb=Group(name='Island curb')
        for i in range(count):
            a,b=2*math.pi*i/count,2*math.pi*(i+1)/count
            steps=max(1,math.ceil((b-a)*64/math.pi))
            loop=[QVector3D(cx+r*math.cos(a+(b-a)*j/steps),cy+r*math.sin(a+(b-a)*j/steps),0)
                  for r,js in ((island,range(steps+1)),(island-curb_width,range(steps,-1,-1))) for j in js]
            block=add(curb,[(api.ccw(loop),[])],lambda v:plane(v)+p['curb_height'],
                lambda v:plane(v)-p['curb_depth'],(.24,.25,.26) if i%2==0 else (.94,.94,.90),'Island curb block','curb')
            if block is not None:
                block.ext={**(block.ext or {}),engine.KEY+'_part':{'key':'curb','paint_index':i}}
        assembly.children.append(curb)
    else:
        add(assembly,[(circle(island),[circle(island-curb_width)])],
            lambda v:plane(v)+p['curb_height'],lambda v:plane(v)-p['curb_depth'],(.82,.81,.77),'Island curb','curb')
    add(assembly,[(circle(island-curb_width),[])],
        lambda v:plane(v)+max(0,p['curb_height']-p['median_soil_drop']),lambda v:plane(v)-p['green_depth'],(.42,.61,.28),'Island planting','green')
    if apron>0:
        add(assembly,[(circle(island+apron),[circle(island)])],
            lambda v:plane(v)+p['truck_apron_rise'],lambda v:plane(v)-p['thickness'],(.67,.49,.33),'Truck apron','pavement')
    root.children.append(assembly)
    # Annular lane dashes visibly follow the circulation, never a yellow box.
    if width>=5.5:
        radius=island+apron+width/2
        count=max(8,int(2*math.pi*radius/6))
        for i in range(count):
            a=2*math.pi*i/count
            b=a+min(3./radius,math.pi/count)
            poly=[QVector3D(cx+r*math.cos(a+(b-a)*j/6),cy+r*math.sin(a+(b-a)*j/6),0) for r,js in ((radius-.075,range(7)),(radius+.075,range(6,-1,-1))) for j in js]
            add(root,[(api.ccw(poly),[])],lambda v:plane(v)+.006,plane,(.97,.97,.93),'Circulatory lane divider','stripe')
    for arm in entries:
        dx,dy=arm['d']
        station=arm['trim']+.7
        # Approach medians come exclusively from the road section. An
        # undivided road must never acquire a synthetic triangular island.
        side=1 if p.get('drive_side','left')=='left' else -1
        lateral_width=arm['right'] if side==1 else arm['left']
        # Positive lateral in rectangle is travel-right. Incoming traffic on
        # a left-driving outward ray uses its positive (right) half.
        lo,hi=(.25,lateral_width-.25) if side==1 else (-lateral_width+.25,-.25)
        if hi>lo:
            at=lo
            while at<hi:
                poly=marks.rectangle((cx,cy),(dx,dy),station,station+.3,at,min(at+.6,hi))
                add(root,[(api.ccw(poly),[])],lambda v:plane(v)+.006,plane,(.97,.97,.93),'Entry yield line','stripe')
                at+=1.
        # Arrow on the ring indicates the chosen circulation direction.
        angle=arm['angle']+.5
        r=island+apron+width*.55
        point=(cx+r*math.cos(angle),cy+r*math.sin(angle))
        direction=(-math.sin(angle),math.cos(angle)) if p.get('drive_side')=='right' else (math.sin(angle),-math.cos(angle))
        mask=marks.arrow_mask(point,direction,min(3.,width*.5),.22)
        regions=marks.intersection([(circle(outer),[circle(island+apron)])],mask)
        add(root,regions,lambda v:plane(v)+.007,plane,(.97,.97,.93),'Circulation arrow','stripe')
    junction.ext[engine.KEY]['roundabout']={'island_radius':island,'apron_width':apron,'circulatory_width':width,'outer_radius':outer,'entry_radius':entry,'drive_side':p.get('drive_side','left')}
