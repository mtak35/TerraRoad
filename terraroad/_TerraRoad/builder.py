# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Sweep the detailed section template directly; keep preview/build identical."""
import math
from dataclasses import asdict


def make_road(engine,section,points,values,name):
    from PySide6.QtGui import QMatrix4x4,QVector3D
    from core.group import Group
    from core.mesh import Mesh
    p=section.parameters(values)
    features=engine.support('features')
    items=values.get('_features',[])
    if items:
        p['station_interval']=min(p['station_interval'],1.)
    template=section.build(p)
    alignment=engine.Parameters(lanes=1,lane_width=1,thickness=max(p['thickness'],0.01),
        crown=0,sidewalk=0,curb_width=0,markings=False,
        radius=p['corner_radius'],station_interval=max(p['station_interval'],0.0254),
        offset=0,elevation=p['adjust_height'])
    def rgb(hex_color):
        return tuple(int(hex_color[i:i+2],16)/255 for i in (1,3,5))
    specs=[(part.name,part.points,rgb(section.COLORS.get(part.key,'#999999'))) for part in template.parts]
    route,axes,_=engine.prepare(points,alignment,specs)
    origin=tuple(points[0])
    local=[tuple(v-o for v,o in zip(pt,origin)) for pt in route]
    stations=engine.station_lengths(local)
    parent=Group(name=name)
    parent.xform=QMatrix4x4()
    parent.xform.translate(QVector3D(*origin))
    quantities={}
    # Bound work before creating meshes: curb blocks and very short dashes can
    # otherwise turn a long alignment into millions of tiny pieces.
    if len(route)*sum(len(part.points) for part in template.parts)>250000:
        raise ValueError('Too many section vertices; increase station interval or shorten the road.')

    def sweep(poly,path,normals,color,material_key):
        mesh=Mesh()
        rings=[[QVector3D(pt[0]+n[0]*x,pt[1]+n[1]*x,pt[2]+z+alignment.elevation)
                for x,z in poly] for pt,n in zip(path,normals)]
        def face(vertices):
            f=mesh.add_face(vertices)
            f.attrs['color']=color
            return f
        face(rings[0])
        face(rings[-1][::-1])
        for a,b in zip(rings,rings[1:]):
            for j in range(len(poly)):
                k=(j+1)%len(poly)
                face([a[j],b[j],b[k]])
                face([a[j],b[k],a[k]])
        # Hide internal coplanar tessellation, retaining true section corners.
        # This makes the road read as paving rather than a triangular grid.
        for edge in mesh.edges:
            if material_key in ('edge','stripe','crossing'):
                edge.hidden=True
            if len(edge.faces)==2 and QVector3D.dotProduct(edge.faces[0].normal(),edge.faces[1].normal())>0.99999:
                edge.soft=True
        return mesh

    def add_quantity(name,poly,span):
        q=quantities.setdefault(name,{'length_m':0.0,'area_m2':0.0,'volume_m3':0.0})
        q['length_m']+=span
        q['area_m2']+=(max(x for x,z in poly)-min(x for x,z in poly))*span
        q['volume_m3']+=engine._area(poly)*span

    def intervals(length,gap=0):
        if length<=0:
            raise ValueError('Block or dash length must be positive.')
        total=stations[-1]
        if total/(length+gap)>10000:
            raise ValueError('Too many blocks/dashes; increase their spacing or shorten the road.')
        result=[]
        start=0
        while start<total-1e-7:
            result.append((start,min(total,start+length)))
            start+=length+gap
        return result

    for part,(part_name,poly,color) in zip(template.parts,specs):
        spans=[(0,stations[-1])]
        if part.key=='curb' and p['curb_paint']:
            spans=intervals(p['curb_block_length'])
        if 'Median' in part_name and (p.get('_junction_ends') or items):
            first,last=engine.support('median').limits(template,stations,p)
            allowed=features.median_spans(stations[-1],items)
            radius=p['median_width']/2
            allowed=[(max(first,a+radius if a>0 else a),min(last,b-radius if b<stations[-1] else b)) for a,b in allowed]
            spans=[(max(a,c),min(b,d)) for a,b in spans for c,d in allowed if min(b,d)>max(a,c)+1e-6]
        for i,(start,end) in enumerate(spans):
            path=engine.slice_path(local,stations,start,end)
            # Frames interpolated from the complete route preserve exact miters
            # at block and dash boundaries instead of making tiny open seams.
            normals=axes_at(path,local,stations,axes,start,end)
            c=color
            if part.key=='curb' and p['curb_paint']:
                c=(0.15,0.15,0.14) if i%2==0 else (0.92,0.91,0.85)
            mesh=sweep(poly,path,normals,c,part.key)
            if part.key=='curb' and p['curb_paint']:
                for edge in mesh.edges:
                    edge.hidden=True
            parent.children.append(Group(mesh,name=part_name+(f' {i+1}' if len(spans)>1 else '')))
        add_quantity(part_name,poly,sum(b-a for a,b in spans))
    for stripe in template.stripes:
        spans=intervals(stripe.dash_length,stripe.gap_length) if stripe.dashed else [(0,stations[-1])]
        x0,x1=stripe.offset-stripe.width/2,stripe.offset+stripe.width/2
        # Like the original stripe sweep, the line sits at its recorded top_z.
        poly=section.rect(x0,stripe.z,x1,stripe.z,0.001)
        name='Edge line' if stripe.edge else ('Centre line' if stripe.centre else 'Lane divider')
        color=(0.96,0.77,0.12) if stripe.edge else (0.97,0.97,0.93)
        for start,end in spans:
            path=engine.slice_path(local,stations,start,end)
            mesh=sweep(poly,path,axes_at(path,local,stations,axes,start,end),color,'edge' if stripe.edge else 'stripe')
            parent.children.append(Group(mesh,name=name))
            add_quantity(name,poly,end-start)
    engine.support('median').add_caps(engine,section,parent,template,local,axes,stations,p,quantities)
    if section.divided(p):
        for item in items:
            if item['type']!='uturn':
                continue
            start,end=item['station']-item['length']/2,item['station']+item['length']/2
            if start<=p['median_width'] or end>=stations[-1]-p['median_width']:
                raise ValueError('Move the U-turn farther from the road ends.')
            for a,b,which in ((0.,start,1),(end,stations[-1],0)):
                path=engine.slice_path(local,stations,a,b)
                normals=axes_at(path,local,stations,axes,a,b)
                engine.support('median').add_caps(engine,section,parent,template,path,normals,engine.station_lengths(path),
                    {**p,'_junction_ends':[which],'median_junction_setback':0.},quantities)
            x=p['offset']
            poly=section.rect(x-p['median_width']/2,0,x+p['median_width']/2,0,p['thickness'])
            path=engine.slice_path(local,stations,start,end)
            parent.children.append(Group(sweep(poly,path,axes_at(path,local,stations,axes,start,end),rgb(section.COLORS['pavement']),'pavement'),name='U-turn paving'))
            add_quantity('U-turn paving',poly,end-start)
            if p['u_turn_marks']:
                stripe=section.rect(x-p['median_width']/2,max(p['stripe_lift'],.002),x+p['median_width']/2,max(p['stripe_lift'],.002),.001)
                for at in (start,end-.15):
                    path=engine.slice_path(local,stations,at,at+.15)
                    parent.children.append(Group(sweep(stripe,path,axes_at(path,local,stations,axes,at,at+.15),(.97,.97,.93),'stripe'),name='U-turn marking'))
                    add_quantity('U-turn marking',stripe,.15)
    quantities.update(engine.support('parking').add_markings(parent,engine,template,local,axes,stations,p))
    furniture=engine.support('furniture')
    counts=furniture.add_to_road(parent,engine,template,local,axes,stations,p)
    crossing_mode=p['crossing_placement']
    crossing_starts=[]
    crossing_length=p['crossing_length']
    crossing_starts.extend(item['station']-crossing_length/2 for item in items if item['type']=='crossing')
    if crossing_mode in ('ends','both'):
        crossing_starts.extend((p['crossing_setback'],stations[-1]-p['crossing_setback']-crossing_length))
    if crossing_mode in ('spacing','both'):
        crossing_starts.extend(furniture.stations_between(stations[-1],p['crossing_spacing'],p['crossing_spacing'],stations[-1]-crossing_length))
    crossing_starts=sorted(set(round(s,7) for s in crossing_starts if 0<=s<=stations[-1]-crossing_length))
    bar,gap=p['crossing_bar_width'],p['crossing_bar_gap']
    if crossing_starts and (bar<=0 or crossing_length<=0 or bar+gap<=0):
        raise ValueError('Crossing length and bar width must be positive.')
    for start in crossing_starts:
        end=start+crossing_length
        path=engine.slice_path(local,stations,start,end)
        normals=axes_at(path,local,stations,axes,start,end)
        for x0,z0,x1,z1,lanes in template.carriageways:
            count=int((x1-x0+gap)/(bar+gap))
            if count>2000:
                raise ValueError('Too many crossing bars; increase bar width.')
            margin=(x1-x0-(count*(bar+gap)-gap))/2
            def top(x):
                profile=template.top_profile
                for (a,za),(b,zb) in zip(profile,profile[1:]):
                    if a-1e-8<=x<=b+1e-8 and b-a>1e-8:
                        return za+(zb-za)*(x-a)/(b-a)+max(p['stripe_lift'],.002)
                return max(z0,z1)+max(p['stripe_lift'],.002)
            for i in range(count):
                a=x0+margin+i*(bar+gap)
                b=a+bar
                # Keep the crown breakpoint so paint follows both crossfalls.
                xs=sorted(set([a,b]+[x for x,z in template.top_profile if a<x<b]))
                for a,b in zip(xs,xs[1:]):
                    poly=section.rect(a,top(a),b,top(b),.001)
                    parent.children.append(Group(sweep(poly,path,normals,(.96,.96,.92),'crossing'),name='Zebra crossing'))
                    add_quantity('Zebra crossing',poly,end-start)
    features.warp(engine,parent,template,local,stations,items)
    features.bridges(engine,section,parent,template,local,axes,stations,p,items,quantities)
    parent.ext={engine.KEY:{'schema':2,'version':engine.VERSION,'values':values.copy(),
        'points':[[v-o for v,o in zip(pt,origin)] for pt in points],
        'centerline_length_m':stations[-1],'quantities':quantities,
        'section':{'left':template.left_extent,'right':template.right_extent,
                   'parts':[{**asdict(part),'points':[list(point) for point in part.points]} for part in template.parts]},
        'warnings':template.warnings,'furniture':counts}}
    return parent


def axes_at(path,route,stations,axes,start,end):
    """Evaluate complete-route station frames for a clipped sweep interval."""
    import bisect
    # slice_path always retains all internal route stations in the interval.
    numbers=[start]+[s for s in stations if start+1e-7<s<end-1e-7]+[end]
    out=[]
    for s in numbers:
        i=max(0,min(len(stations)-2,bisect.bisect_right(stations,s)-1))
        t=(s-stations[i])/(stations[i+1]-stations[i])
        out.append(tuple(a+(b-a)*t for a,b in zip(axes[i],axes[i+1])))
    if len(out)!=len(path):
        raise ValueError('Station/frame mismatch while sweeping the road.')
    return out
