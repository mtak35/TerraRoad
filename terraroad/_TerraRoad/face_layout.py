# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Style accessories on planar faces: fitted lanes, parking and capsule medians."""
import math
from PySide6.QtGui import QVector3D


def basis(regions,values):
    points=[v for outer,holes in regions for v in outer]
    area=mx=my=ix=iy=ixy=0.
    for outer,holes in regions:
        for ring,role in [(outer,1)]+[(h,-1) for h in holes]:
            signed=sum(a.x()*b.y()-b.x()*a.y() for a,b in zip(ring,ring[1:]+ring[:1]))
            sign=role*(1 if signed>=0 else -1)
            for a,b in zip(ring,ring[1:]+ring[:1]):
                cross=(a.x()*b.y()-b.x()*a.y())*sign
                area+=cross/2
                mx+=(a.x()+b.x())*cross/6
                my+=(a.y()+b.y())*cross/6
                ix+=(a.x()**2+a.x()*b.x()+b.x()**2)*cross/12
                iy+=(a.y()**2+a.y()*b.y()+b.y()**2)*cross/12
                ixy+=(2*a.x()*a.y()+a.x()*b.y()+b.x()*a.y()+2*b.x()*b.y())*cross/24
    if area<=1e-8:
        raise ValueError('The paved face has no usable area.')
    cx,cy=mx/area,my/area
    spine=values.get('_face_spine')
    if spine and len(spine)>1:
        dx,dy=spine[-1][0]-spine[0][0],spine[-1][1]-spine[0][1]
        size=math.hypot(dx,dy)
        if size<1e-5:
            raise ValueError('The face spine must have a nonzero plan length.')
        direction=(dx/size,dy/size)
        origin=spine[0][:2]
    else:
        # Area moments are independent of triangulation/collinear vertices.
        # Counting boundary vertices tilted lanes after clipping open ends.
        xx,yy,xy=ix/area-cx*cx,iy/area-cy*cy,ixy/area-cx*cy
        angle=.5*math.atan2(2*xy,xx-yy)
        direction=(math.cos(angle),math.sin(angle))
        origin=(cx,cy)
    ux,uy=direction
    coords=[((p.x()-origin[0])*ux+(p.y()-origin[1])*uy,(p.x()-origin[0])*uy-(p.y()-origin[1])*ux) for p in points]
    return origin,direction,(min(s for s,x in coords),max(s for s,x in coords),min(x for s,x in coords),max(x for s,x in coords))


def capsule(origin,direction,s0,s1,radius,x=0):
    ux,uy=direction
    point=lambda s,v:QVector3D(origin[0]+ux*s+uy*v,origin[1]+uy*s-ux*v,0)
    if s1-s0<radius*2:
        radius=min(radius,(s1-s0)/2)
    result=[]
    for center,start in ((s1-radius,-math.pi/2),(s0+radius,math.pi/2)):
        for i in range(25):
            a=start+math.pi*i/24
            result.append(point(center+radius*math.cos(a),x+radius*math.sin(a)))
    # Build in (station,lateral) coordinates then orient via the host helper.
    return result


def open_boundary(outer,holes,values,depth):
    """Move end caps beyond the cut planes before offsetting roadside bands."""
    origin,direction,(s0,s1,x0,x1)=basis([(outer,holes)],values)
    candidates=[]
    count=len(outer)
    cross=lambda a,b:a.x()*b.y()-a.y()*b.x()
    for i,a in enumerate(outer):
        b=outer[(i+1)%count]
        before=a-outer[i-1]
        edge=b-a
        after=outer[(i+2)%count]-b
        if min(before.length(),edge.length(),after.length())<1e-5:
            continue
        if cross(before,edge)<=0 or cross(edge,after)<=0:
            continue
        if QVector3D.dotProduct(before.normalized(),after.normalized())>-.7:
            continue
        if max(abs(QVector3D.dotProduct(edge.normalized(),t.normalized())) for t in (before,after))>.5:
            continue
        n=QVector3D(edge.y(),-edge.x(),0).normalized()
        alignment=abs(n.x()*direction[0]+n.y()*direction[1])
        candidates.append((edge.length(),-alignment,i,n))
    caps=[]
    for item in sorted(candidates,key=lambda item:(round(item[0],4),item[1])):
        i=item[2]
        if all(i not in ((c[2]-1)%count,(c[2]+1)%count) for c in caps):
            caps.append(item)
        if len(caps)==2:
            break
    if len(caps)<2:
        return outer,None
    extend=max(depth*3,2.)
    result=[QVector3D(p) for p in outer]
    masks=[]
    reach=max(s1-s0,x1-x0,depth,1.)*5+extend*4
    for length,alignment,i,normal in caps:
        a,b=outer[i],outer[(i+1)%count]
        result[i]+=normal*extend
        result[(i+1)%count]+=normal*extend
        tangent=(b-a).normalized()
        # Interior lies to the left of a CCW boundary edge.
        masks.append([a-tangent*reach-normal*reach,b+tangent*reach-normal*reach,
                      b+tangent*reach,a-tangent*reach])
    return result,{'masks':masks}


def layout(engine,section,root,paved,p,values,plane,quantities):
    api=engine.support('faces')
    marks=engine.support('markings')
    origin,direction,(s0,s1,x0,x1)=basis(paved,values)
    ux,uy=direction
    actual_width=x1-x0
    p=p.copy()
    t=section.build(p)
    if section.truth(values.get('face_fit',True)):
        ways=section.carriageway_width(p)*(2 if section.divided(p) else 1)
        inside_width=t.kerb_faces['right'][0]-t.kerb_faces['left'][0]
        extra=inside_width-ways-(p['median_width'] if section.divided(p) else 0)
        p['width_mode']='total'
        p['total_width']=max(.5,(actual_width-extra-(p['median_width'] if section.divided(p) else 0))/(2 if section.divided(p) else 1))
        p['offset']=0.
        t=section.build(p)
    shift=(x0+x1)/2-(t.kerb_faces['left'][0]+t.kerb_faces['right'][0])/2
    lateral=lambda v:(v.x()-origin[0])*uy-(v.y()-origin[1])*ux-shift
    solid_parts=[]
    cuts=[]
    # Median is rounded at both ends and set back inside the selected face.
    if section.divided(p):
        radius=p['median_width']/2
        setback=p['median_junction_setback']
        outline=capsule(origin,direction,s0+setback,s1-setback,radius,shift)
        median=api.union_regions(marks.intersection(paved,outline))
        if median:
            cuts.extend(median)
            cw=p.get('median_curb_width')
            cw=p['curb_width'] if cw is None else cw
            height=p.get('median_curb_height')
            height=p['curb_height'] if height is None else height
            depth=p.get('median_curb_depth')
            depth=p['curb_depth'] if depth is None else depth
            # Offset the capsule as a single region before clipping. This
            # avoids seams where triangulated cells touch one another.
            inner=api.offset_shape(api.ccw(outline),[],cw) if p['median_curb'] else [(api.ccw(outline),[])]
            inner=[region for region in inner if region[0]]
            interior=[]
            for poly,holes in inner:
                interior.extend(marks.intersection(paved,poly))
            interior=api.union_regions(interior)
            if p['median_curb']:
                curb=api.union_regions(api.difference(median,interior))
                cells=(api.paint_cells(curb,[(api.ccw(outline),[])],p['curb_block_length'],max(radius*2,1.)) if p['curb_paint'] else [(curb,None)])
                for number,(regions,index) in enumerate(cells):
                    assembly=marks.add_solid_parts(engine,root,regions,lambda v:plane(v)+height,lambda v:plane(v)-depth,
                        ((.15,.15,.14) if index is not None and index%2==0 else (.92,.91,.85) if index is not None else (.79,.78,.75)),
                        f'Median Curb {number+1}','curb',quantities)
                    assembly.ext[engine.KEY+'_part']['paint_index']=index
            if interior:
                key='green' if p['median_type']=='green' else 'pavement'
                top=(height-p['median_soil_drop']) if key=='green' else 0.
                marks.add_solid_parts(engine,root,interior,lambda v:plane(v)+top,lambda v:plane(v)+top-max(p['green_depth'],.0254),
                    (.49,.61,.37) if key=='green' else (.34,.35,.36),'Median '+('Green Belt' if key=='green' else 'Paving'),key,quantities)
    # The selected face already supplies its real perimeter roadside bands.
    # Interior parking/service/shoulder strips come from the fitted section.
    for part in t.parts:
        if 'Median' in part.name:
            continue
        internal=(part.key in ('parking','shoulder','channel','grill') or 'Service' in part.name)
        if not internal:
            continue
        lo,hi=min(x for x,z in part.points),max(x for x,z in part.points)
        if hi-lo<1e-6:
            continue
        regions=marks.intersection(paved,marks.rectangle(origin,direction,s0,s1,lo+shift,hi+shift))
        if not regions:
            continue
        cuts.extend(regions)
        color=tuple(int(section.COLORS[part.key][i:i+2],16)/255 for i in (1,3,5))
        marks.add_solid_parts(engine,root,regions,lambda v,poly=part.points:plane(v)+api.envelope(poly,lateral(v))[1],
            lambda v,poly=part.points:plane(v)+api.envelope(poly,lateral(v))[0],color,part.name,part.key,quantities)
    # Remove accessories' occupied regions from the asphalt so no coplanar
    # faces flicker and median soil is not sitting over a duplicate slab.
    if cuts:
        cuts=api.union_regions(cuts)
        pavement=api.union_regions(api.difference(paved,cuts))
        slab=next(g for g in root.children if g.name=='Pavement')
        slab.mesh=api.solid(pavement,plane,lambda v:plane(v)-p['thickness'],(.333,.337,.353))
        area=api.regions_area(pavement)
        quantities['Pavement'].update(area_m2=area,volume_m3=area*p['thickness'])
    lift=max(p['stripe_lift'],.002)
    for stripe in t.stripes:
        width=stripe.width
        spans=[(s0,s1)]
        if stripe.dashed:
            pitch=stripe.dash_length+stripe.gap_length
            if pitch<=0 or (s1-s0)/pitch>2000:
                raise ValueError('Invalid face marking dash/gap length.')
            spans=[(s,min(s1,s+stripe.dash_length)) for s in (s0+i*pitch for i in range(math.ceil((s1-s0)/pitch)))]
        for start,end in spans:
            regions=marks.intersection(paved,marks.rectangle(origin,direction,start,end,stripe.offset+shift-width/2,stripe.offset+shift+width/2))
            if cuts:
                regions=api.difference(regions,cuts)
            label='Edge line' if stripe.edge else 'Centre line' if stripe.centre else 'Lane divider'
            marks.add_solid_parts(engine,root,regions,lambda v:plane(v)+lift,plane,(.96,.78,.08) if stripe.edge else (.97,.97,.93),label,'stripe',quantities)
    if p['parking_marks'] and t.parking_bays:
        # Reuse the exact centerline bay-mark geometry, then clip its plan
        # footprint to the face. All paint sits on the bay's actual surface.
        from core.group import Group
        path=[(0.,s0,0.),(0.,s1,0.)]
        temporary=Group(name='Parking paint')
        engine.support('parking').add_markings(temporary,engine,t,path,[(1.,0.),(1.,0.)],[0.,s1-s0],p)
        for group in temporary.children:
            tops=[f for f in group.mesh.faces if f.normal().z()>.5]
            for face in tops:
                mask=[QVector3D(origin[0]+ux*v.y()+uy*(v.x()+shift),origin[1]+uy*v.y()-ux*(v.x()+shift),0) for v in face.vertices]
                regions=marks.intersection(paved,mask)
                normal=face.normal()
                anchor=face.vertices[0]
                def paint_top(v):
                    station=(v.x()-origin[0])*ux+(v.y()-origin[1])*uy
                    return plane(v)+anchor.z()-(normal.x()*(lateral(v)-anchor.x())+normal.y()*(station-anchor.y()))/normal.z()
                marks.add_solid_parts(engine,root,regions,paint_top,lambda v:paint_top(v)-.001,(.96,.96,.92),'Parking marking','parking_marking',quantities)
    for item in values.get('_face_marks',[]):
        point=item['point']
        if item['type']=='arrow':
            mask=marks.arrow_mask(point,direction,float(item.get('length',3)))
            regions=marks.intersection(paved,mask)
            marks.add_solid_parts(engine,root,regions,lambda v:plane(v)+lift,plane,(.97,.97,.93),'Lane arrow','stripe',quantities)
        elif item['type']=='crossing':
            station=(point[0]-origin[0])*ux+(point[1]-origin[1])*uy
            count=int(actual_width/(p['crossing_bar_width']+p['crossing_bar_gap']))
            for i in range(count):
                x=x0+i*(p['crossing_bar_width']+p['crossing_bar_gap'])
                regions=marks.intersection(paved,marks.rectangle(origin,direction,station-p['crossing_length']/2,station+p['crossing_length']/2,x,x+p['crossing_bar_width']))
                if cuts:
                    regions=api.difference(regions,cuts)
                marks.add_solid_parts(engine,root,regions,lambda v:plane(v)+lift,plane,(.97,.97,.93),'Zebra crossing','crossing',quantities)
    return dict(origin=list(origin),direction=list(direction),actual_width=actual_width)
