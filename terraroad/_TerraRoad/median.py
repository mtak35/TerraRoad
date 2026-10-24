# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Semicircular median noses at junction approaches."""
import math
from PySide6.QtGui import QVector3D


def limits(template,stations,p):
    ends=p.get('_junction_ends',[])
    radius=p['median_width']/2
    setback=p['median_junction_setback']
    return (radius+setback if 0 in ends else 0.,stations[-1]-radius-setback if 1 in ends else stations[-1])


def add_caps(engine,section,root,template,route,axes,stations,p,quantities):
    if not section.divided(p) or not p.get('_junction_ends'):
        return
    api=engine.support('faces')
    marking=engine.support('markings')
    furniture=engine.support('furniture')
    radius=p['median_width']/2
    start,end=limits(template,stations,p)
    if end<=start:
        raise ValueError('The median is too short for its rounded ends and setbacks.')
    xcenter=template.params['offset']
    cw=p.get('median_curb_width')
    cw=p['curb_width'] if cw is None else cw
    height=p.get('median_curb_height')
    height=p['curb_height'] if height is None else height
    depth=p.get('median_curb_depth')
    depth=p['curb_depth'] if depth is None else depth
    for which in p['_junction_ends']:
        station=start if which==0 else end
        pt,n=furniture.frame(route,axes,stations,station)
        direction=(-n[1],n[0])
        origin=(pt[0]+n[0]*xcenter,pt[1]+n[1]*xcenter)
        angle=math.pi/2 if which==0 else -math.pi/2
        def half(r):
            return [QVector3D(origin[0]+direction[0]*r*math.cos(angle+i*math.pi/32)+n[0]*r*math.sin(angle+i*math.pi/32),
                              origin[1]+direction[1]*r*math.cos(angle+i*math.pi/32)+n[1]*r*math.sin(angle+i*math.pi/32),0) for i in range(33)]
        outer=api.ccw(half(radius))
        inner=api.ccw(half(max(.001,radius-cw))) if p['median_curb'] else outer
        inner_regions=[(inner,[])]
        plane=lambda v:pt[2]+p['adjust_height']
        if p['median_curb']:
            curb=api.union_regions(api.difference([(outer,[])],inner_regions))
            cells=api.paint_cells(curb,[(outer,[])],p['curb_block_length'],radius*2+1) if p['curb_paint'] else [(curb,None)]
            for number,(regions,index) in enumerate(cells):
                color=(.15,.15,.14) if index is not None and index%2==0 else (.92,.91,.85) if index is not None else (.79,.78,.75)
                group=marking.add_solid_parts(engine,root,regions,lambda v:plane(v)+height,lambda v:plane(v)-depth,
                    color,f'Median semicircle curb {which+1}.{number+1}','curb',quantities)
                group.ext[engine.KEY+'_part']['paint_index']=index
        green=p['median_type']=='green'
        top=height-p['median_soil_drop'] if green else 0.
        marking.add_solid_parts(engine,root,inner_regions,lambda v:plane(v)+top,lambda v:plane(v)+top-max(p['green_depth'],.0254),
            (.49,.61,.37) if green else (.34,.35,.36),'Median rounded nose','green' if green else 'pavement',quantities)
        # Fill the two corners beside the cap and any requested setback.
        distance=radius+p['median_junction_setback']
        lo,hi=(-distance,0.) if which==0 else (0.,distance)
        mask=marking.rectangle(origin,direction,lo,hi,-radius,radius)
        infill=api.union_regions(api.difference([(api.ccw(mask),[])],[(outer,[])]))
        marking.add_solid_parts(engine,root,infill,plane,lambda v:plane(v)-p['thickness'],(.333,.337,.353),'Median approach paving','pavement',quantities)
