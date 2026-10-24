# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Recover editable centerlines and snap new branches to their centerlines."""
import math
from PySide6.QtGui import QVector3D,QMatrix4x4


def sources(engine,scene,groups):
    segments=[]
    included=[]
    designs=set()
    for group in groups:
        data=(group.ext or {}).get(engine.KEY,{})
        frame=group.xform or QMatrix4x4()
        if data.get('network_source'):
            design=data['design_id']
            if design in designs:
                continue
            designs.add(design)
            source=data['network_source']['segments']
            frame=frame*QMatrix4x4(*data['member_frame']).inverted()[0]*QMatrix4x4(*data['network_frame'])
            included.extend(g for g in scene.groups if (g.ext or {}).get(engine.KEY,{}).get('design_id')==design)
        elif data.get('network'):
            source=data['segments']
            included.append(group)
        elif data.get('points'):
            source=list(zip(data['points'],data['points'][1:]))
            included.append(group)
        else:
            continue
        segments.extend((frame.map(QVector3D(*a)).toTuple(),frame.map(QVector3D(*b)).toTuple()) for a,b in source)
    return segments,list(dict.fromkeys(included))


def snap(engine,scene,point,exclude=()):
    best=None
    for group in scene.groups:
        if group in exclude:
            continue
        data=(group.ext or {}).get(engine.KEY,{})
        if not data.get('points'):
            continue
        frame=group.xform or QMatrix4x4()
        points=[frame.map(QVector3D(*v)) for v in data['points']]
        section=data.get('section',{})
        tolerance=max(abs(section.get('left',0)),abs(section.get('right',0)),.5)
        for a,b in zip(points,points[1:]):
            dx,dy=b.x()-a.x(),b.y()-a.y()
            length=dx*dx+dy*dy
            if length<1e-8:
                continue
            t=max(0.,min(1.,((point.x()-a.x())*dx+(point.y()-a.y())*dy)/length))
            at=a+(b-a)*t
            distance=math.hypot(point.x()-at.x(),point.y()-at.y())
            if distance<=tolerance and abs(point.z()-at.z())<2. and (best is None or distance<best[0]):
                best=(distance,at,group)
    return (QVector3D(point),None) if best is None else (best[1],best[2])
