# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Selected-line networks: split crossings, trim arms and pave T/X junctions.

Uses exact tangent returns, with editable nested roads in the host scene.
Junction networks currently require level cross-sections; grade separation and
adaptive widening need the separate original algorithms and are not inferred.
"""
import copy
import math
from collections import defaultdict
from PySide6.QtGui import QVector3D,QMatrix4x4
from core.group import Group
from core.mesh import Mesh


def cross(a,b):
    return a[0]*b[1]-a[1]*b[0]


def graph_paths(segments):
    segments=[(tuple(a),tuple(b)) for a,b in segments]
    if len(segments)>1000:
        raise ValueError('Select at most 1000 centerline segments per network.')
    cuts=[{0.,1.} for _ in segments]
    for i,(a,b) in enumerate(segments):
        u=(b[0]-a[0],b[1]-a[1])
        if math.hypot(*u)<1e-5:
            raise ValueError('Network centerlines cannot be vertical or zero length.')
        if not all(math.isfinite(x) for x in (*a,*b)):
            raise ValueError('Network coordinates must be finite.')
        for j in range(i):
            c,d=segments[j]
            v=(d[0]-c[0],d[1]-c[1])
            delta=(c[0]-a[0],c[1]-a[1])
            den=cross(u,v)
            if abs(den)>1e-8:
                t,s=cross(delta,v)/den,cross(delta,u)/den
                if -1e-7<=t<=1+1e-7 and -1e-7<=s<=1+1e-7:
                    z1=a[2]+(b[2]-a[2])*t
                    z2=c[2]+(d[2]-c[2])*s
                    # Bridges crossing at separate elevations remain separate.
                    if abs(z1-z2)<1e-4:
                        cuts[i].add(max(0.,min(1.,t)))
                        cuts[j].add(max(0.,min(1.,s)))
            elif abs(cross(delta,u))<1e-7:
                for point in (c,d):
                    t=((point[0]-a[0])*u[0]+(point[1]-a[1])*u[1])/(u[0]**2+u[1]**2)
                    if 1e-7<t<1-1e-7:
                        cuts[i].add(t)
                for point in (a,b):
                    s=((point[0]-c[0])*v[0]+(point[1]-c[1])*v[1])/(v[0]**2+v[1]**2)
                    if 1e-7<s<1-1e-7:
                        cuts[j].add(s)
    graph=defaultdict(set)
    points={}
    seen=set()
    for (a,b),ts in zip(segments,cuts):
        ts=sorted(ts)
        for t,s in zip(ts,ts[1:]):
            pa=tuple(a[k]+(b[k]-a[k])*t for k in range(3))
            pb=tuple(a[k]+(b[k]-a[k])*s for k in range(3))
            ka,kb=tuple(round(x,4) for x in pa),tuple(round(x,4) for x in pb)
            if ka==kb:
                continue
            edge=tuple(sorted((ka,kb)))
            if edge in seen:
                continue
            seen.add(edge)
            points[ka],points[kb]=pa,pb
            graph[ka].add(kb)
            graph[kb].add(ka)
    visited=set()
    paths=[]
    for node in sorted(graph):
        if len(graph[node])==2:
            continue
        for neighbor in sorted(graph[node]):
            if frozenset((node,neighbor)) in visited:
                continue
            path=[node]
            prev,current=node,neighbor
            while True:
                visited.add(frozenset((prev,current)))
                path.append(current)
                if len(graph[current])!=2:
                    break
                following=next(x for x in graph[current] if x!=prev)
                prev,current=current,following
                if len(path)>len(graph):
                    raise ValueError('Closed centerline loops must be opened before building a network.')
            paths.append([points[key] for key in path])
    if len(visited)!=len(seen):
        raise ValueError('The selection includes a closed centerline loop. Open it first.')
    return paths,{key:points[key] for key in graph if len(graph[key])>=3}


def key(point):
    return tuple(round(x,4) for x in point)


def make_network(engine,section,segments,values,name='TerraRoad network'):
    paths,nodes=graph_paths(segments)
    if not paths:
        raise ValueError('Select connected centerlines first.')
    if len(paths)==1 and not nodes:
        return engine.make_detailed_road(paths[0],values,name)
    p=section.parameters(values)
    if nodes and not p['level_section']:
        raise ValueError('Junction networks currently require “Level cross-section”. Crowned single roads remain supported.')
    if nodes and p['crossing_type']=='bridge':
        raise ValueError('Automatic bridge crossings are not ported yet. Use separate centerlines at different elevations.')
    if nodes and abs(p['offset'])>1e-6:
        raise ValueError('Network junctions require zero lateral offset. Use individual roads for offset alignments.')
    template=section.build(p)
    left=abs(template.kerb_faces['left'][0])
    right=abs(template.kerb_faces['right'][0])
    arms=defaultdict(list)
    for i,path in enumerate(paths):
        for end in (0,1):
            node,inner=(path[0],path[1]) if end==0 else (path[-1],path[-2])
            if key(node) not in nodes:
                continue
            length=math.dist(node[:2],inner[:2])
            d=((inner[0]-node[0])/length,(inner[1]-node[1])/length)
            arms[key(node)].append({'path':i,'end':end,'d':d,'angle':math.atan2(d[1],d[0]),
                'left':left if end==0 else right,'right':right if end==0 else left,
                'limit':length*(.45 if key(path[0]) in nodes and key(path[-1]) in nodes else .9),'trim':0.})
    junctions=[]
    roundabout=p['crossing_type']=='roundabout'
    for node_key,entries in arms.items():
        node=nodes[node_key]
        entries.sort(key=lambda a:a['angle'])
        corners=[]
        if roundabout:
            roadside=max((x for bands in template.outboard.values() for band in bands for x,z in band['loop']),default=0.)
            corners=engine.support('roundabout').corners(node,entries,p,roadside,max(left,right))
        else:
            for a,b in zip(entries,entries[1:]+entries[:1]):
                u,v=a['d'],b['d']
                angle=(b['angle']-a['angle'])%(2*math.pi)
                den=cross(u,v)
                if abs(den)<1e-6 or angle>=math.pi-.001:
                    corners.append([])
                    continue
                # Intersection of the left curb of A with the right curb of B.
                q=(-u[1]*a['left'],u[0]*a['left'])
                r=(v[1]*b['right'],-v[0]*b['right'])
                t=cross((r[0]-q[0],r[1]-q[1]),v)/den
                corner=(q[0]+u[0]*t,q[1]+u[1]*t)
                sb=corner[0]*v[0]+corner[1]*v[1]
                radius=p['junction_radius']
                if p['junction_radius_auto']:
                    radius=min(max(left,right)*float(p.get('radius_scale') or 1),radius)
                    # Outside a concave return, an offset wider than its
                    # radius folds through the arc center and inverts walks.
                    roadside=max((x for bands in template.outboard.values() for band in bands for x,z in band['loop']),default=0.)
                    radius=max(radius,roadside+.0254)
                if p['crossing_type']=='plain':
                    radius=0.
                available=max(0.,min(a['limit']-t,b['limit']-sb))*math.tan(angle/2)
                if radius>available and p['crossing_type']!='plain':
                    roadside=max((x for bands in template.outboard.values() for band in bands for x,z in band['loop']),default=0.)
                    if available<=roadside:
                        raise ValueError('The junction is too short for these curb/walkway widths without folding the return. Lengthen the arms or reduce roadside widths.')
                radius=min(radius,available)
                if p['crossing_type']!='plain' and not p['junction_radius_auto']:
                    roadside=max((x for bands in template.outboard.values() for band in bands for x,z in band['loop']),default=0.)
                    if radius<=roadside:
                        raise ValueError('Return radius is smaller than the roadside width and would fold the walkway. Enable automatic radius or increase the radius.')
                tangent=radius/max(math.tan(angle/2),1e-6)
                ta,tb=max(0.,t+tangent),max(0.,sb+tangent)
                a['trim']=max(a['trim'],ta)
                b['trim']=max(b['trim'],tb)
                first=(corner[0]+u[0]*tangent,corner[1]+u[1]*tangent)
                if radius<1e-5:
                    corners.append([(node[0]+corner[0],node[1]+corner[1],node[2])])
                    continue
                center=(first[0]-u[1]*radius,first[1]+u[0]*radius)
                begin=math.atan2(first[1]-center[1],first[0]-center[0])
                sweep=math.pi-angle
                corners.append([(node[0]+center[0]+radius*math.cos(begin-sweep*i/16),
                                 node[1]+center[1]+radius*math.sin(begin-sweep*i/16),node[2]) for i in range(17)])
        for a in entries:
            # A parallel pair still needs the same trim on each arm to join
            # the rounded corner on the other side of that mouth.
            a['trim']=max(a['trim'],max(left,right))
            if a['trim']>a['limit']+1e-5:
                raise ValueError('These arms are too short for the junction widths.')
        # Include both straight connectors, even on the opposite side of a
        # T-junction. Sweeping only the arc left whole sidewalks/curbs absent.
        for index,(a,b) in enumerate(zip(entries,entries[1:]+entries[:1])):
            dx,dy=a['d']
            ex,ey=b['d']
            start=(node[0]+dx*a['trim']-dy*a['left'],node[1]+dy*a['trim']+dx*a['left'],node[2])
            finish=(node[0]+ex*b['trim']+ey*b['right'],node[1]+ey*b['trim']-ex*b['right'],node[2])
            full=[]
            for pt in [start]+corners[index]+[finish]:
                if not full or math.dist(pt,full[-1])>1e-5:
                    full.append(pt)
            corners[index]=full
        boundary=[]
        for index,a in enumerate(entries):
            dx,dy=a['d']
            dx,dy=a['d']
            mouth=(node[0]+dx*a['trim'],node[1]+dy*a['trim'],node[2])
            boundary.extend([(mouth[0]+dy*a['right'],mouth[1]-dx*a['right'],mouth[2]),
                             (mouth[0]-dy*a['left'],mouth[1]+dx*a['left'],mouth[2])])
            boundary.extend(corners[index])
        # Drop duplicate tangent vertices before handing the ring to the host.
        clean=[]
        for pt in boundary:
            if not clean or math.dist(pt,clean[-1])>1e-5:
                clean.append(pt)
        if math.dist(clean[0],clean[-1])<1e-5:
            clean.pop()
        junctions.append((node,clean,corners,entries))
    origin=paths[0][0]
    root=Group(name=name)
    root.xform=QMatrix4x4()
    root.xform.translate(QVector3D(*origin))
    quantities={}
    def local_point(pt):
        return tuple(pt[i]-origin[i] for i in range(3))
    def add(group):
        root.children.append(group)
        for label,q in group.ext[engine.KEY].get('quantities',{}).items():
            target=quantities.setdefault(label,dict(length_m=0.,area_m2=0.,volume_m3=0.))
            for k in target:
                target[k]+=q[k]
    for i,path in enumerate(paths):
        route=[local_point(pt) for pt in path]
        junction_ends=[]
        for node,ring,corners,entries in junctions:
            for arm in entries:
                if arm['path']!=i:
                    continue
                end=arm['end']
                index=0 if end==0 else -1
                d=arm['d']
                t=arm['trim'] if p['junction_mode']!='overlap' else 0
                t+=p['junction_gap'] if p['junction_mode']=='gap' else 0
                route[index]=local_point((node[0]+d[0]*t,node[1]+d[1]*t,node[2]))
                junction_ends.append(end)
        arm_values={**values,'_junction_ends':junction_ends}
        group=engine.make_detailed_road(route,arm_values,f'Road {i+1}')
        add(group)
    face_api=engine.support('faces')
    for i,(node,ring,corners,entries) in enumerate(junctions):
        if p['junction_mode']!='paved':
            continue
        loops=[[local_point(pt) for pt in ring]]
        if roundabout:
            roadside=max((x for bands in template.outboard.values() for band in bands for x,z in band['loop']),default=0.)
            island,apron,*_=engine.support('roundabout').dimensions(p,roadside,max(left,right),entries)
            radius=island+apron
            loops.append([local_point((node[0]+radius*math.cos(j*math.pi/64),node[1]+radius*math.sin(j*math.pi/64),node[2])) for j in range(128)])
        jvalues={**values,'adjust_height':p['adjust_height'].__str__()+'m','junction_poles':False}
        if roundabout:
            jvalues['box_junction']=False
        junction=face_api.from_loops(engine,section,loops,jvalues,f'Junction {i+1}','junction')
        add(junction)
        # Sweep roadside bands only along the returns, leaving every mouth open.
        for corner_index,corner in enumerate(corners):
            if len(corner)<2:
                continue
            a,b=entries[corner_index],entries[(corner_index+1)%len(entries)]
            start_bands=template.outboard.get('left' if a['end']==0 else 'right',[])
            end_bands=template.outboard.get('right' if b['end']==0 else 'left',[])
            first_normal=(-a['d'][1],a['d'][0])
            last_normal=(b['d'][1],-b['d'][0])
            all_axes=engine.frames(corner)
            all_axes[0],all_axes[-1]=first_normal,last_normal
            stations=engine.station_lengths(corner)
            length=stations[-1]
            for band,end_poly in band_pairs(start_bands,end_bands):
                spans=[(0.,length)]
                if band['key']=='curb' and p['curb_paint']:
                    block=p['curb_block_length']
                    if block<=.001 or length/block>10000:
                        raise ValueError('Curb block length must be positive and produce at most 10000 blocks.')
                    spans=[(i*block,min(length,(i+1)*block)) for i in range(math.ceil(length/block))]
                for block_index,(start,stop) in enumerate(spans):
                    path=engine.slice_path(corner,stations,start,stop)
                    normals=engine.support('builder').axes_at(path,corner,stations,all_axes,start,stop)
                    blend=lambda t:[(x+(X-x)*t,z+(Z-z)*t) for (x,z),(X,Z) in zip(band['loop'],end_poly)]
                    color=section.COLORS[band['key']]
                    if band['key']=='curb' and p['curb_paint']:
                        color='#262624' if block_index%2==0 else '#ebe8d9'
                    mesh=sweep_band(engine,path,blend(start/length),origin,p['adjust_height'],color,normals,blend(stop/length))
                    if band['key']=='curb' and p['curb_paint']:
                        for edge in mesh.edges:
                            edge.hidden=True
                    group=Group(mesh,name='Junction '+band['name']+(f' {block_index+1}' if len(spans)>1 else ''))
                    group.ext={engine.KEY+'_part':{'key':band['key'],'paint_index':block_index if band['key']=='curb' and p['curb_paint'] else None}}
                    root.children.append(group)
                q=quantities.setdefault('Junction '+band['name'],dict(length_m=0.,area_m2=0.,volume_m3=0.))
                q['length_m']+=length
                q['area_m2']+=(max(x for x,z in band['loop'])-min(x for x,z in band['loop']))*length
                q['volume_m3']+=engine._area(band['loop'])*length
                jq=junction.ext[engine.KEY]['quantities'].setdefault('Junction '+band['name'],dict(length_m=0.,area_m2=0.,volume_m3=0.))
                jq['length_m']+=length
                jq['area_m2']+=(max(x for x,z in band['loop'])-min(x for x,z in band['loop']))*length
                jq['volume_m3']+=engine._area(band['loop'])*length
            if p['junction_shoulders'] and p['shoulder_mode']!='none' and p['shoulder_width']>0:
                poly=section.rect(-p['shoulder_width'],0,0,0,p['shoulder_thickness'])
                root.children.append(Group(sweep_band(engine,corner,poly,origin,p['adjust_height'],section.COLORS['shoulder']),name='Junction Shoulder'))
            if p['junction_edge_lines'] and p['edge_line_width']>0:
                inset=p['edge_inset']
                poly=section.rect(-inset-p['edge_line_width'],p['stripe_lift'],-inset,p['stripe_lift'],.001)
                root.children.append(Group(sweep_band(engine,corner,poly,origin,p['adjust_height'],'#f4c51f'),name='Junction Edge line'))
            if p['junction_poles'] and p['pole_placement']!='none':
                furniture=engine.support('furniture')
                route=[local_point(pt) for pt in corner]
                stations=engine.station_lengths(route)
                axes=engine.frames(route)
                length=stations[-1]
                assembly=Group(name='Junction Light Poles')
                mesh=furniture.pole_mesh(p)
                from core.group import _copy_mesh
                for s in furniture.stations_between(length,p['pole_spacing'],min(length/2,p['pole_spacing']/2)):
                    pt,n=furniture.frame(route,axes,stations,s)
                    offset=template.pole_anchors.get('right',(right+p['pole_offset'],0))[0]-right
                    assembly.children.append(furniture.instance(_copy_mesh(mesh),'Light Pole',
                        (pt[0]+n[0]*offset,pt[1]+n[1]*offset,pt[2]+p['curb_height']+p['adjust_height']),(-n[0],-n[1])))
                if assembly.children:
                    root.children.append(assembly)
        if roundabout:
            engine.support('roundabout').add_details(engine,section,root,junction,node,entries,p,origin,quantities)
    root.ext={engine.KEY:{'schema':4,'network':True,'values':copy.deepcopy(values),
        'segments':[[list(local_point(a)),list(local_point(b))] for a,b in segments],
        'junction_count':len(nodes),'centerline_length_m':sum((g.ext or {}).get(engine.KEY,{}).get('centerline_length_m',0) for g in root.children),
        'quantities':quantities,'section':{'parts':[]},
        'warnings':['Automatic junction networks currently use level cross-sections. Adaptive flares, bridge crossings and terrain grading are not yet ported.']}}
    return root


def band_pairs(start,end):
    """Match both approach roadsides instead of copying the right side."""
    before={b['name']:b for b in start}
    after={b['name']:b for b in end}
    for name in dict.fromkeys(list(before)+list(after)):
        a,b=before.get(name),after.get(name)
        template=a or b
        ap=a['loop'] if a else [(0,z) for x,z in b['loop']]
        bp=b['loop'] if b else [(0,z) for x,z in a['loop']]
        if len(ap)!=len(bp):
            raise ValueError('These two junction roadside profiles cannot be blended yet.')
        yield {**template,'loop':ap},bp


def sweep_band(engine,path,poly,origin,elevation,color,normals=None,end_poly=None):
    from core.mesh import Mesh
    color=tuple(int(color[i:i+2],16)/255 for i in (1,3,5))
    route=[tuple(pt[i]-origin[i] for i in range(3)) for pt in path]
    axes=normals if normals is not None else engine.frames(route)
    mesh=Mesh()
    end_poly=end_poly or poly
    stations=engine.station_lengths(route)
    rings=[]
    for pt,n,s in zip(route,axes,stations):
        t=s/stations[-1]
        profile=[(x+(X-x)*t,z+(Z-z)*t) for (x,z),(X,Z) in zip(poly,end_poly)]
        rings.append([QVector3D(pt[0]+n[0]*x,pt[1]+n[1]*x,pt[2]+z+elevation) for x,z in profile])
    def face(pts):
        if len({tuple(round(v,6) for v in pt.toTuple()) for pt in pts})>=3:
            mesh.add_face(pts).attrs['color']=color
    face(rings[0])
    face(rings[-1][::-1])
    for a,b in zip(rings,rings[1:]):
        for i in range(len(poly)):
            j=(i+1)%len(poly)
            face([a[i],b[i],b[j],a[j]])
    return mesh
