# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Port of TerraRoad section.rb's static section builder, in metres.

Original section algorithms: Copyright 2026 The Court Group.
The same template feeds the live preview and the native solid sweep.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
import copy
import json
import math
import re

DATA=json.loads(Path(__file__).with_name('assets.json').read_text(encoding='utf-8'))
DEFAULTS=DATA['defaults']
INCH=0.0254
EPS=1e-8
COLORS={'pavement':'#55565a','gutter':'#8e8f8b','shoulder':'#8c8c82',
        'parking':'#63656a','curb':'#c9c6be','sidewalk':'#b0aa9c','green':'#7d9b5e',
        'channel':'#969b9b','grill':'#7a8186'}


def truth(value):
    return value in (True,'true',1,'1')


def length(value,unit='m'):
    """Feet/inches, mixed fractions and SI lengths; never evaluate code."""
    text=str(value or '').strip().lower().replace('′',"'").replace('’',"'").replace('″','"')
    if text.count(',')==1 and '.' not in text:
        text=text.replace(',','.')
    if not text:
        return 0.0
    sign=-1 if text.startswith('-') else 1
    text=text.lstrip('+-').strip()
    def number(token):
        token=token.strip().replace('-',' ')
        pieces=token.split()
        if not pieces:
            return 0.0
        if len(pieces)>2:
            raise ValueError('Invalid mixed fraction')
        return sum(float(Fraction(s)) for s in pieces)
    try:
        if "'" in text or '"' in text:
            feet,inches=0.0,0.0
            if "'" in text:
                part,text=text.split("'",1)
                feet=number(part)
            text=text.strip()
            if text.endswith('"'):
                text=text[:-1]
            if text:
                inches=number(text)
            result=sign*(feet*0.3048+inches*INCH)
        else:
            match=re.fullmatch(r'([\d. /+-]+)\s*(mm|cm|m|ft|in|feet|foot|inch|inches)?',text)
            if not match:
                raise ValueError('Invalid length')
            factor={'mm':0.001,'cm':0.01,'m':1.0,'ft':0.3048,'in':INCH,
                    'feet':0.3048,'foot':0.3048,'inch':INCH,'inches':INCH}[match[2] or unit]
            result=sign*number(match[1])*factor
        if not math.isfinite(result):
            raise ValueError('Non-finite length')
        return result
    except (ValueError,ZeroDivisionError,KeyError,OverflowError) as exc:
        raise ValueError(f'Cannot read length {value!r}. Use e.g. 3.5m, 12\' or 6 1/2".') from exc


def parameters(values):
    raw={**DEFAULTS,**values}
    p=copy.deepcopy(raw)
    for key in DATA['lengths']:
        if key in raw:
            p[key]=length(raw[key],raw.get('_length_unit','m'))
    for key in DATA['percents']:
        p[key]=float(raw.get(key) or 0)/100
    for key in DATA['integers']:
        p[key]=int(raw.get(key) or 0)
    for key,default in DEFAULTS.items():
        if isinstance(default,bool):
            p[key]=truth(raw[key])
    # Some old styles encode checkboxes as strings instead of booleans.
    for key in ('face_fit','divided','median_curb','parking_auto_width'):
        p[key]=truth(raw[key])
    for key in ('median_curb_height','median_curb_width','median_curb_depth','median_curb_batter'):
        if str(raw.get(key) or '').strip()=='':
            # Zero supplied as a number/string is an answer, not inheritance.
            if raw.get(key) not in (0,'0'):
                p[key]=None
    p['lanes']=max(1,p['lanes'])
    p['service_lanes']=max(1,p['service_lanes'])
    if p['lanes']>30 or p['service_lanes']>30:
        raise ValueError('Lane count must be at most 30.')
    for key in DATA['lengths']:
        if key in p and p[key] is not None and p[key]<0 and key not in ('offset','adjust_height','hv_offset','bridge_rise','widen_by','widen_median'):
            raise ValueError(f'{key.replace("_"," ").capitalize()} cannot be negative.')
    if abs(p['crown'])>0.5:
        raise ValueError('Crossfall must be between -50% and 50%.')
    return p


@dataclass
class Part:
    key:str
    name:str
    points:list
    solid:bool=True


@dataclass
class Stripe:
    offset:float
    width:float
    z:float
    dashed:bool=False
    dash_length:float=0
    gap_length:float=0
    centre:bool=False
    edge:bool=False


@dataclass
class Template:
    parts:list=field(default_factory=list)
    stripes:list=field(default_factory=list)
    top_profile:list=field(default_factory=list)
    subgrade_profile:list=field(default_factory=list)
    left_hinge:tuple=(0,0)
    right_hinge:tuple=(0,0)
    left_extent:float=0
    right_extent:float=0
    carriageways:list=field(default_factory=list)
    pole_anchors:dict=field(default_factory=dict)
    curb_anchors:dict=field(default_factory=dict)
    parking_bays:list=field(default_factory=list)
    kerb_faces:dict=field(default_factory=dict)
    outboard:dict=field(default_factory=dict)
    params:dict=field(default_factory=dict)
    warnings:list=field(default_factory=list)


def rect(x0,z0,x1,z1,depth):
    return [(x0,z0-depth),(x1,z1-depth),(x1,z1),(x0,z0)]


def crowned(xc,hw,edge_z,depth):
    return [(xc-hw,edge_z-depth),(xc,-depth),(xc+hw,edge_z-depth),
            (xc+hw,edge_z),(xc,0),(xc-hw,edge_z)]


def transform(poly,x,z,direction):
    pts=[(x+direction*s,z+dz) for s,dz in poly]
    return pts[::-1] if direction<0 else pts


def divided(p):
    return p['divided'] and p['median_width']>0


def carriageway_width(p):
    if p['width_mode']=='lanes':
        return p['lanes']*p['lane_width']
    if p['width_mode']!='overall':
        return p['total_width']
    wanted=p['total_width']
    if wanted<=0:
        raise ValueError('Overall road width must be positive.')
    trial=24*0.3048
    probe=build({**p,'width_mode':'total','total_width':trial})
    count=2 if divided(p) else 1
    spare=probe.right_extent-probe.left_extent-trial*count
    return max(8*0.3048,(wanted-spare)/count)


def parking_depth(p):
    if not p['parking_auto_width']:
        return p['parking_width']
    angle=int(p['parking_angle'])
    if angle==180:
        return p['parking_stall_width']
    theta=math.radians(angle)
    return p['parking_stall_length']*math.sin(theta)+p['parking_stall_width']*math.cos(theta)


def parking_pitch(p):
    angle=int(p['parking_angle'])
    if angle==180:
        return p['parking_parallel_length']
    return p['parking_stall_width']/max(math.sin(math.radians(angle)),EPS)


def curb_profile(p):
    h,w=p['curb_height'],p['curb_width']
    depth=p['curb_depth']+(p['curb_additional_depth'] if p['curb_extend_bottom'] else 0)
    batter=min(p['curb_batter'],w)
    if min(w,depth)<=0:
        return None,0,0
    if p['curb_type']=='barrier':
        return [(0,-depth),(w,-depth),(w,h),(0,h)],h,w
    if p['curb_type']=='mountable':
        poly=[(0,-depth),(w,-depth),(w,h),(batter,h),(0,0)]
        # Remove coincident consecutive vertices when batter equals width.
        poly=[pt for i,pt in enumerate(poly) if pt!=poly[i-1]]
        return poly,h,w
    if p['curb_type']=='flush':
        return rect(0,0,w,0,depth),0,w
    return None,0,0


def linear_bands(name,x0,z0,x1,z1,depth,gutter):
    span=x1-x0
    if span<=EPS:
        raise ValueError('A carriageway band has no width.')
    if gutter<=0 or gutter*2>=span:
        return [Part('pavement',name,rect(x0,z0,x1,z1,depth))]
    at=lambda x:z0+(z1-z0)*(x-x0)/span
    a,b=x0+gutter,x1-gutter
    return [Part('gutter',name+' Gutter (left)',rect(x0,z0,a,at(a),depth)),
            Part('pavement',name,rect(a,at(a),b,at(b),depth)),
            Part('gutter',name+' Gutter (right)',rect(b,at(b),x1,z1,depth))]


def crowned_bands(xc,hw,crown,depth,gutter):
    edge=-hw*crown
    if gutter<=0 or gutter>=hw:
        return [Part('pavement','Pavement',crowned(xc,hw,edge,depth))]
    core=hw-gutter
    core_z=-core*crown
    return [Part('gutter','Left Gutter',rect(xc-hw,edge,xc-core,core_z,depth)),
            Part('pavement','Pavement',crowned(xc,core,core_z,depth)),
            Part('gutter','Right Gutter',rect(xc+core,core_z,xc+hw,edge,depth))]


def channel_parts(name,x_out,direction,z,p):
    w,d=p['channel_width'],p['channel_depth']
    if min(w,d)<=0:
        return []
    t=p['channel_wall']
    if t<=0 or t*2>=w:
        t=w/4
    g=p['grill_thickness'] or 2*INCH
    if g>=d:
        g=d/4
    lo,hi=sorted((x_out-direction*w,x_out))
    top,invert=z-g,z-d
    floor=invert+t
    if floor>=top:
        raise ValueError('Storm channel is too shallow for its floor and grating thickness.')
    u=[(lo,top),(lo,invert),(hi,invert),(hi,top),(hi-t,top),(hi-t,floor),(lo+t,floor),(lo+t,top)]
    return [Part('channel',name+' Storm Channel',u),Part('grill',name+' Channel Grating',rect(lo,z,hi,z,g))]


def median_parts(p,l0,r0):
    mp=p.copy()
    for key in ('height','width','depth','batter','type'):
        own=p.get('median_curb_'+key)
        if own is not None and own!='':
            mp['curb_'+key]=own
    if p.get('median_curb_depth') is not None:
        mp['curb_extend_bottom']=False
    poly,rise,out=curb_profile(mp) if p['median_curb'] else (None,0,0)
    parts,profile=[],[]
    if poly:
        if out*2>r0-l0+EPS:
            raise ValueError('Median is too narrow for its two curbs.')
        parts.extend([Part('curb','Left Median Curb',transform(poly,l0,0,1)),
                      Part('curb','Right Median Curb',transform(poly,r0,0,-1))])
        profile.extend([(l0,0),(l0+out,rise)])
    a,b=l0+out,r0-out
    top=rise
    if b-a>EPS:
        if p['median_type']=='green':
            top=rise-p['median_soil_drop']
            parts.append(Part('green','Median Green Belt',rect(a,top,b,top,max(p['green_depth'],INCH))))
        elif p['median_type']=='paved':
            top=0
            parts.append(Part('pavement','Median Paving',rect(a,0,b,0,p['thickness'])))
        profile.extend([(a,top),(b,top)])
    if poly:
        profile.extend([(r0-out,rise),(r0,0)])
    anchor=((a+b)/2,top) if p['pole_placement']=='median' and b>a else None
    return parts,sorted(profile),anchor


def divider_strip(p,x,z,direction,s,dz,width,name):
    poly,rise,out=curb_profile(p) if p['service_divider_curb'] else (None,0,0)
    parts,profile=[],[]
    if out*2>=width:
        out=0
    if out>0:
        parts.append(Part('curb',name+' Service Divider Curb (inner)',transform(poly,x+direction*s,z+dz,direction)))
        mirrored=[(-a,b) for a,b in poly][::-1]
        parts.append(Part('curb',name+' Service Divider Curb (outer)',transform(mirrored,x+direction*(s+width),z+dz,direction)))
    a,b=s+out,s+width-out
    top=dz+rise
    if b-a>EPS:
        if p['service_divider_type']=='paved':
            key,label,top,depth='pavement','Service Divider',dz,p['thickness']
        else:
            key,label,top,depth='green','Service Divider Planting',dz+rise-p['median_soil_drop'],max(p['green_depth'],INCH)
        parts.append(Part(key,name+' '+label,transform(rect(a,top,b,top,depth),x,z,direction)))
        profile.extend([(a,top),(b,top)])
    return parts,profile


def side_parts(p,side,x,z):
    direction=-1 if side=='left' else 1
    name=side.capitalize()
    parts,profile,bands=[],[(0,0)],[]
    ways=[]
    s=dz=hinge_s=0.0
    hinge_z=-p['thickness']
    has=lambda key:p[key] in ('both',side)
    def add(key,label,poly,outboard=False):
        parts.append(Part(key,name+' '+label,transform(poly,x,z,direction)))
        if outboard:
            bands.append((key,label,poly))
    sh=p['shoulder_width']
    if p['shoulder_mode']!='none' and sh>0:
        thick=max(p['shoulder_thickness'],0.5*INCH)
        end=dz-sh*p['shoulder_slope']
        add('shoulder','Shoulder',rect(s,dz,s+sh,end,thick))
        s+=sh
        dz=end
        profile.append((s,dz))
        hinge_s,hinge_z=s,dz-thick
    sw=p['service_width']
    if has('service_side') and sw>0:
        dw=p['service_divider_width']
        if dw>0:
            pp,pr=divider_strip(p,x,z,direction,s,dz,dw,name)
            parts.extend(pp)
            profile.extend(pr)
            s+=dw
        thick=max(p['service_thickness'],0.5*INCH)
        end=dz-sw*p['service_slope']
        add('pavement','Service Road',rect(s,dz,s+sw,end,thick))
        a,b=x+direction*s,x+direction*(s+sw)
        za,zb=z+dz,z+end
        ways.append((a,za,b,zb,p['service_lanes']) if direction>0 else (b,zb,a,za,p['service_lanes']))
        profile.extend([(s,dz),(s+sw,end)])
        s+=sw
        dz=end
        hinge_s,hinge_z=s,dz-thick
    pw=parking_depth(p)
    bay=None
    if has('parking_side') and pw>0:
        thick=max(p['parking_thickness'],0.5*INCH)
        end=dz-pw*(0 if p['parking_flat'] else p['parking_slope'])
        add('parking','Parking Bay',rect(s,dz,s+pw,end,thick))
        bay=(x+direction*s,x+direction*(s+pw),z+dz,z+end,direction)
        s+=pw
        dz=end
        profile.append((s,dz))
        hinge_s,hinge_z=s,dz-thick
    face_s,face_z=s,dz
    poly,rise,out=curb_profile(p) if has('curb_side') else (None,0,0)
    curb_top=dz+rise
    if poly:
        local=[(s+u,dz+v) for u,v in poly]
        add('curb','Curb',local,True)
        if p['curb_type']=='barrier':
            profile.append((s,curb_top))
        s+=out
        profile.append((s,curb_top))
        hinge_s=s
        hinge_z=dz-p['curb_depth']-(p['curb_additional_depth'] if p['curb_extend_bottom'] else 0)
    curb_back=s
    top=curb_top
    depth=max(p['green_depth'],INCH)
    verge=p['verge_width'] if has('verge_side') else 0
    if verge>0:
        if p['verge_green']:
            vt=top-p['median_soil_drop']
            add('green','Green Verge',rect(s,vt,s+verge,vt,depth),True)
            profile.extend([(s,vt),(s+verge,vt)])
            hinge_z=vt-depth
        else:
            profile.append((s+verge,top))
        s+=verge
        hinge_s=s
    walk_start=s
    ww,tw=p['walk_width'],p['walk_thickness']
    if has('sidewalk') and min(ww,tw)>0:
        end=top+ww*p['walk_slope']
        add('sidewalk','Sidewalk',rect(s,top,s+ww,end,tw),True)
        profile.extend([(s,top),(s+ww,end)])
        s+=ww
        top=end
        hinge_s,hinge_z=s,end-tw
    belt=p['outer_belt_width']
    if belt>0:
        bt=top-p['median_soil_drop']
        add('green','Outer Green Belt',rect(s,bt,s+belt,bt,depth),True)
        profile.extend([(s,bt),(s+belt,bt)])
        s+=belt
        hinge_s,hinge_z=s,bt-depth
    anchor=None
    if p['pole_placement'] in ('both','alternating',side):
        # Match section.rb's recorded anchor; furniture placement later refines
        # pole_stand for walk/verge in the longitudinal furniture generator.
        anchor=(x+direction*(curb_back+p['pole_offset']),z+curb_top)
    extent=x+direction*hinge_s
    return {'parts':parts,'profile':[(x+direction*a,z+b) for a,b in profile],
            'hinge':(extent,z+hinge_z),'extent':extent,'carriageways':ways,'anchor':anchor,
            'curb_anchor':(x+direction*curb_back,z+curb_top,direction),
            'kerb_face':(x+direction*face_s,z+(dz if out>0 else hinge_z),direction,out),
            'parking_bay':bay,'outboard':[{ 'key':key,'name':label,'loop':[(a-face_s,b-face_z) for a,b in poly]} for key,label,poly in bands]}


def lane_stripes(p,ways,is_divided,xc,top,bays):
    if p['surface_type'] in ('earthen','gravel','wbm') or p['mark_lanes']=='never':
        return []
    centers=[]
    if not is_divided:
        count=p['center_line_count']
        if count==1:
            centers=[xc]
        elif count>=2:
            half=p['center_line_spacing']/2
            centers=[xc-half,xc+half]
    out=[]
    for x0,z0,x1,z1,lanes in ways:
        span=x1-x0
        if span<=0:
            continue
        if p['edge_lines'] and p['edge_line_width']>0:
            inset=p['edge_inset']
            for x,edge in ((x0+inset,x0),(x1-inset,x1)):
                if not p['edge_line_at_parking'] and any(abs(a-edge)<6*INCH or abs(b-edge)<6*INCH for a,b,*_ in bays):
                    continue
                out.append(Stripe(x,p['edge_line_width'],top(x)+p['stripe_lift'],edge=True))
        if p['lane_divider_type']!='none':
            for i in range(1,max(1,lanes)):
                x=x0+span*i/lanes
                if any(abs(c-x)<p['center_line_spacing']/2+EPS for c in centers):
                    continue
                out.append(Stripe(x,p['lane_divider_width'],top(x)+p['stripe_lift'],p['lane_divider_type']=='dashed',p['divider_dash_length'],p['divider_gap_length']))
    if p['center_line_type']!='none':
        for x in centers:
            out.append(Stripe(x,p['center_line_width'],top(x)+p['stripe_lift'],p['center_line_type']=='dashed',p['center_dash_length'],p['center_gap_length'],centre=True))
    return [s for s in out if s.width>0]


def build_at(p):
    p=p.copy()
    if p['level_section']:
        for key in ('crown','shoulder_slope','parking_slope','walk_slope','service_slope','median_soil_drop'):
            p[key]=0.0
    cw=carriageway_width(p)
    xc,crown,thick=p['offset'],p['crown'],p['thickness']
    if min(cw,thick)<=0:
        raise ValueError('Road width and thickness must be greater than zero.')
    t=Template(params=p)
    is_divided=divided(p)
    fall=(cw if is_divided else cw/2)*crown
    if thick<=fall:
        raise ValueError('Road thickness is smaller than crown fall. Increase thickness or reduce crossfall.')
    def channel(side,limit):
        w=p['channel_width'] if p['storm_channel'] in (side,'both') else 0
        return w if w*2<limit else 0
    gutter=max(p['gutter_width'],0)
    if is_divided:
        mh=p['median_width']/2
        l0,r0=xc-mh,xc+mh
        left,right=l0-cw,r0+cw
        cl,cr=channel('left',cw),channel('right',cw)
        t.parts.extend(linear_bands('Right Carriageway',r0,0,right-cr,-fall,thick,gutter))
        t.parts.extend(linear_bands('Left Carriageway',left+cl,-fall,l0,0,thick,gutter))
        t.carriageways=[(r0,0,right,-fall,p['lanes']),(left,-fall,l0,0,p['lanes'])]
        top=lambda x:-fall*min(1,max(0,(x-r0)/cw if x>=xc else (l0-x)/cw))
        parts,median_profile,anchor=median_parts(p,l0,r0)
        t.parts.extend(parts)
        if anchor:
            t.pole_anchors['median']=anchor
            t.curb_anchors['median']=anchor
    else:
        hw=cw/2
        left,right=xc-hw,xc+hw
        cl,cr=channel('left',hw),channel('right',hw)
        if cl>0 or cr>0:
            t.parts.extend(linear_bands('Left Carriageway',left+cl,-fall,xc,0,thick,gutter))
            t.parts.extend(linear_bands('Right Carriageway',xc,0,right-cr,-fall,thick,gutter))
        else:
            t.parts.extend(crowned_bands(xc,hw,crown,thick,gutter))
        t.carriageways=[(left,-fall,right,-fall,p['lanes'])]
        top=lambda x:-abs(x-xc)*crown
        median_profile=[(xc,0)]
    for name,x,direction,take in (('Left',left,-1,cl),('Right',right,1,cr)):
        if take>0:
            t.parts.extend(channel_parts(name,x,direction,-fall,p))
    sides={side:side_parts(p,side,x,-fall) for side,x in (('left',left),('right',right))}
    for side,result in sides.items():
        t.parts.extend(result['parts'])
        t.carriageways.extend(result['carriageways'])
        if result['anchor']:
            t.pole_anchors[side]=result['anchor']
        t.curb_anchors[side]=result['curb_anchor']
        t.kerb_faces[side]=result['kerb_face']
        t.outboard[side]=result['outboard']
        if result['parking_bay']:
            t.parking_bays.append(result['parking_bay'])
    left_side,right_side=sides['left'],sides['right']
    t.left_hinge,t.right_hinge=left_side['hinge'],right_side['hinge']
    t.left_extent,t.right_extent=left_side['extent'],right_side['extent']
    t.top_profile=sorted(left_side['profile']+[(left,-fall)]+median_profile+[(right,-fall)]+right_side['profile'])
    t.subgrade_profile=sorted([t.left_hinge,(left,-fall-thick),(xc,-thick),(right,-fall-thick),t.right_hinge])
    t.stripes=lane_stripes(p,t.carriageways,is_divided,xc,top,t.parking_bays)
    return t


def mirror(t):
    for part in t.parts:
        part.points=[(-x,z) for x,z in part.points][::-1]
        part.name=part.name.replace('Left','@RIGHT@').replace('Right','Left').replace('@RIGHT@','Right')
    for stripe in t.stripes:
        stripe.offset=-stripe.offset
    for key in ('top_profile','subgrade_profile'):
        setattr(t,key,sorted((-x,z) for x,z in getattr(t,key)))
    t.left_extent,t.right_extent=-t.right_extent,-t.left_extent
    t.left_hinge,t.right_hinge=(-t.right_hinge[0],t.right_hinge[1]),(-t.left_hinge[0],t.left_hinge[1])
    for key in ('pole_anchors','curb_anchors','kerb_faces'):
        result={}
        for side,value in getattr(t,key).items():
            side={'left':'right','right':'left'}.get(side,side)
            result[side]=tuple((-v if i in (0,2) else v) for i,v in enumerate(value))
        setattr(t,key,result)
    t.carriageways=[(-b,zb,-a,za,n) for a,za,b,zb,n in t.carriageways]
    t.parking_bays=[(-b,-a,zb,za,-direction) for a,b,za,zb,direction in t.parking_bays]
    t.outboard={{'left':'right','right':'left'}.get(k,k):v for k,v in t.outboard.items()}
    return t


def build(p):
    p=p.copy()
    side=p['line_side']
    if side in ('left','right'):
        probe=build_at({**p,'offset':0,'line_side':'centre'})
        edge=p['line_edge']
        at=probe.left_extent if side=='left' else probe.right_extent
        if edge=='kerb' and side in probe.kerb_faces:
            at=probe.kerb_faces[side][0]
        elif edge=='carriageway':
            xs=[x for a,za,b,zb,n in probe.carriageways for x in (a,b)]
            at=min(xs) if side=='left' else max(xs)
        p['offset']-=at
        p['line_side']='centre'
    t=build_at(p)
    if p['mirror_section']:
        t=mirror(t)
    if p['width_mode']=='overall' and abs(t.right_extent-t.left_extent-p['total_width'])>0.01:
        t.warnings.append('The requested overall width cannot contain these roadside bands and the minimum carriageway; the section is wider than requested.')
    return t
