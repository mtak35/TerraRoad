# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Shared-edge mouths and rectangular-layout face decomposition."""
import copy
import math
from PySide6.QtGui import QVector3D,QMatrix4x4


def shared(a,b,c,d):
    dx,dy=b.x()-a.x(),b.y()-a.y()
    size=math.hypot(dx,dy)
    if size<1e-6:
        return None
    ux,uy=dx/size,dy/size
    if max(abs((p.x()-a.x())*uy-(p.y()-a.y())*ux) for p in (c,d))>1e-4:
        return None
    projections=[(p.x()-a.x())*ux+(p.y()-a.y())*uy for p in (c,d)]
    lo,hi=max(0,min(projections)),min(size,max(projections))
    if hi-lo<.01:
        return None
    return [a+(b-a)*(lo/size),a+(b-a)*(hi/size)]


def connected(panel,groups):
    key=panel.engine.KEY
    polygons={g:[(g.xform or QMatrix4x4()).map(QVector3D(*v)) for v in g.ext[key]['loops'][0]] for g in groups}
    openings={g:[] for g in groups}
    for i,one in enumerate(groups):
        for two in groups[:i]:
            for a,b in zip(polygons[one],polygons[one][1:]+polygons[one][:1]):
                for c,d in zip(polygons[two],polygons[two][1:]+polygons[two][:1]):
                    edge=shared(a,b,c,d)
                    if edge and max(abs(edge[0].z()-c.z()),abs(edge[1].z()-d.z()))<.1:
                        for group in (one,two):
                            inverse=(group.xform or QMatrix4x4()).inverted()[0]
                            openings[group].append([list(inverse.map(v).toTuple()) for v in edge])
    pairs=[]
    for old in groups:
        values=copy.deepcopy(old.ext[key]['values'])
        values['_face_openings']=openings[old]
        new=panel.engine.support('faces').from_loops(panel.engine,panel.section,old.ext[key]['loops'],values,old.name,old.ext[key].get('kind','road'))
        panel.preserve(new,old)
        panel.apply_materials(new,values)
        pairs.append((old,new))
    return pairs


def split(panel):
    from core.mesh import Face
    api=panel.engine.support('faces')
    old=panel.selected()
    if old is not None:
        data=old.ext[panel.engine.KEY]
        if not data.get('face_road') or data.get('network_source'):
            raise ValueError('Select a converted face road or one loose face.')
        matrix=old.xform or QMatrix4x4()
        loops=[[matrix.map(QVector3D(*p)) for p in loop] for loop in data['loops']]
        values=copy.deepcopy(data['values'])
        source=None
    else:
        source=next((f for f in panel.app.scene.selection if isinstance(f,Face) and f in panel.app.scene.mesh.faces),None)
        if source is None:
            raise ValueError('Select one loose layout face or converted face road first.')
        loops=[list(source.vertices)]+[list(h) for h in source.holes]
        values=panel.collect()
    ring=loops[0]
    edge=max(zip(ring,ring[1:]+ring[:1]),key=lambda ab:(ab[1]-ab[0]).lengthSquared())
    d=(edge[1]-edge[0]).normalized()
    u,v=(d.x(),d.y()),(-d.y(),d.x())
    coords=[[(p.x()*u[0]+p.y()*u[1],p.x()*v[0]+p.y()*v[1]) for p in loop] for loop in loops]
    for loop in coords:
        if any(abs(a[0]-b[0])>1e-4 and abs(a[1]-b[1])>1e-4 for a,b in zip(loop,loop[1:]+loop[:1])):
            raise ValueError('Automatic cutting currently supports rectangular road layouts (including rotated layouts). Draw separate faces for curved or oblique branches.')
    xs=sorted({round(x,4) for loop in coords for x,y in loop})
    ys=sorted({round(y,4) for loop in coords for x,y in loop})
    if len(xs)*len(ys)>1200:
        raise ValueError('Too many layout cells. Split a smaller part of the plan first.')
    regions=[(api.ccw(loops[0]),[api.ccw(h) for h in loops[1:]])]
    normal=Face([__import__('core.mesh',fromlist=['Vertex']).Vertex(p) for p in ring]).normal()
    if abs(normal.z())<.01:
        raise ValueError('The layout face must be approximately horizontal.')
    base=ring[0]
    def world(x,y):
        a,b=x*u[0]+y*v[0],x*u[1]+y*v[1]
        return QVector3D(a,b,base.z()-(normal.x()*(a-base.x())+normal.y()*(b-base.y()))/normal.z())
    cells={}
    for i in range(len(xs)-1):
        for j in range(len(ys)-1):
            if api.in_regions(world((xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2),regions):
                cells[i,j]=[world(xs[i],ys[j]),world(xs[i+1],ys[j]),world(xs[i+1],ys[j+1]),world(xs[i],ys[j+1])]
    groups=[]
    for (i,j),poly in cells.items():
        neighbors=[(a,b) for a,b in ((i-1,j),(i+1,j),(i,j-1),(i,j+1)) if (a,b) in cells]
        kind='junction' if len(neighbors)>=3 else 'road'
        label='Junction' if kind=='junction' else 'Turn' if len(neighbors)==2 and neighbors[0][0]!=neighbors[1][0] and neighbors[0][1]!=neighbors[1][1] else 'Road'
        settings=copy.deepcopy(values)
        for field in ('_face_openings','_face_spine','_face_marks'):
            settings.pop(field,None)
        group=api.from_loops(panel.engine,panel.section,[[list(p.toTuple()) for p in poly]],settings,'TerraRoad '+label+f' {len(groups)+1}',kind)
        groups.append(group)
    if len(groups)<2:
        raise ValueError('This face is already one rectangular road. Draw a branched layout to cut into roads and junctions.')
    groups=[new for before,new in connected(panel,groups)]
    if old is None:
        panel.actions.execute(api.ConvertFaces([source],groups,panel.engine.KEY,values))
    else:
        from core.history import Command
        class Cut(Command):
            def do(self,scene):
                self.selection=set(scene.selection)
                self.index=scene.groups.index(old)
                scene.groups[self.index:self.index+1]=groups
                scene.selection.clear()
                scene.selection.update(groups)
                scene.version+=1
            def undo(self,scene):
                scene.groups[self.index:self.index+len(groups)]=[old]
                scene.selection.clear()
                scene.selection.update(self.selection)
                scene.version+=1
        panel.actions.execute(Cut())
    panel.result.setPlainText(f'Cut the layout into {len(groups)} independent groups with component parts and open shared mouths. Undo restores the source.')
