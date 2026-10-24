# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Site/map operations: native image planes, cached tiles and editable OSM lines.

Network work happens off the GUI thread. Scene changes use one undo command.
Only the requested visible map patch is fetched; there is no tile prefetch.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
from PySide6.QtCore import QThread,Signal
from PySide6.QtGui import QImage,QPainter,QColor,QFont,QFontDatabase,QVector3D
from core.history import Command
from core.image_plane import ImagePlane

R=6378137.
MAP_LAYER='TerraRoad Map'
PREFIX='TerraRoad Map — '


def map_frame(plane):
    return {key:list(getattr(plane,key).toTuple()) for key in ('origin','u','v')}


def flip_frame(frame):
    """Convert the old top-left/south frame to the host's bottom-left/north UVs."""
    return {**frame,'origin':[a+b for a,b in zip(frame['origin'],frame['v'])],
            'v':[-a for a in frame['v']]}


def corrected_maps(scene,saved):
    """Return an undoable repair for maps saved by versions through 0.7."""
    maps=[p for p in scene.image_planes if p.name.startswith(PREFIX)]
    if not maps or not saved or saved.get('map_uv_version',0)>=1:
        return None
    # Older TerraRoad maps alone used a downward facing image frame.
    if QVector3D.crossProduct(maps[0].u,maps[0].v).z()>=0:
        return None
    site=copy.deepcopy(saved)
    site['map_reference']=flip_frame(site.get('map_reference') or map_frame(maps[0]))
    site['map_uv_version']=1
    repaired=[]
    for plane in maps:
        frame=flip_frame(map_frame(plane))
        repaired.append(ImagePlane(plane.path,*(QVector3D(*frame[k]) for k in ('origin','u','v')),
            plane.aspect,plane.name,plane.opacity,plane.layer,plane.locked))
    return site,repaired


def cropped_reference(reference,a,b,c,d):
    o,u,v=(QVector3D(*reference[k]) for k in ('origin','u','v'))
    return dict(origin=list((o+u*a+v*b).toTuple()),u=list((u*(c-a)).toTuple()),v=list((v*(d-b)).toTuple()))


def trace_site(scene,saved):
    maps=[p for p in scene.image_planes if p.name.startswith(PREFIX)]
    if not maps or not saved or 'lat' not in saved:
        raise ValueError('Place a georeferenced TerraRoad map before tracing roads.')
    site=copy.deepcopy(saved)
    reference=site.get('map_reference') or map_frame(maps[0])
    corners=[QVector3D(*reference['origin'])+QVector3D(*reference['u'])*u+QVector3D(*reference['v'])*v for u,v in ((0,0),(0,1),(1,0),(1,1))]
    geo=[earth_point(p.toTuple(),site) for p in corners]
    site['crop_bbox']=[min(a for a,b in geo),min(b for a,b in geo),max(a for a,b in geo),max(b for a,b in geo)]
    site['_trace_placement']={'reference':reference,'current':map_frame(maps[0])}
    return site


def place_trace(point,site):
    placement=site.get('_trace_placement')
    if not placement:
        return point
    ref,current=placement['reference'],placement['current']
    p=QVector3D(*point)-QVector3D(*ref['origin'])
    u,v=QVector3D(*ref['u']),QVector3D(*ref['v'])
    a=QVector3D.dotProduct(p,u)/u.lengthSquared()
    b=QVector3D.dotProduct(p,v)/v.lengthSquared()
    q=QVector3D(*current['origin'])+QVector3D(*current['u'])*a+QVector3D(*current['v'])*b
    q.setZ(q.z()+.07)
    return q.toTuple()


def place_ways(ways,site):
    placement=site.get('_trace_placement')
    if not placement:
        return ways
    ref=placement['reference']
    origin,u,v=(QVector3D(*ref[k]) for k in ('origin','u','v'))
    def uv(point):
        d=QVector3D(*point)-origin
        return QVector3D.dotProduct(d,u)/u.lengthSquared(),QVector3D.dotProduct(d,v)/v.lengthSquared()
    result=[]
    for way in ways:
        chain=[]
        def finish():
            nonlocal chain
            if len(chain)>=2:
                result.append({**way,'points':chain})
            chain=[]
        for a,b in zip(way['points'],way['points'][1:]):
            x,y=uv(a)
            X,Y=uv(b)
            dx,dy=X-x,Y-y
            lo,hi=0.,1.
            for d,gap in ((-dx,x),(dx,1-x),(-dy,y),(dy,1-y)):
                if abs(d)<1e-12:
                    if gap<0:
                        lo,hi=1.,0.
                elif d<0:
                    lo=max(lo,gap/d)
                else:
                    hi=min(hi,gap/d)
            if hi<=lo:
                finish()
                continue
            first=place_trace(tuple(a[i]+(b[i]-a[i])*lo for i in range(3)),site)
            last=place_trace(tuple(a[i]+(b[i]-a[i])*hi for i in range(3)),site)
            if chain and math.dist(chain[-1],first)>1e-4:
                finish()
            if not chain:
                chain.append(first)
            chain.append(last)
            if hi<1.-1e-8:
                finish()
        finish()
    return result


def coordinates(text):
    text=urllib.parse.unquote(str(text).strip())
    match=(re.search(r'@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)',text) or
           re.search(r'(?:[?&](?:q|query|ll)=|!3d)(-?\d+(?:\.\d+)?)(?:,\s*|!4d)(-?\d+(?:\.\d+)?)',text) or
           re.fullmatch(r'\s*(-?\d+(?:\.\d+)?)\s*[,; ]\s*(-?\d+(?:\.\d+)?)\s*',text))
    if not match:
        raise ValueError('Paste latitude, longitude or a full Google Maps link. Shortened links must be opened and copied as a full link first.')
    lat,lon=map(float,match.groups())
    if not -85<=lat<=85 or not -180<=lon<=180:
        raise ValueError('Site coordinates must be between 85°S/85°N and 180°W/180°E.')
    return lat,lon


def mercator(lat,lon):
    return R*math.radians(lon),R*math.log(math.tan(math.pi/4+math.radians(lat)/2))


def latlon(x,y):
    return math.degrees(2*math.atan(math.exp(y/R))-math.pi/2),math.degrees(x/R)


def world_point(lat,lon,site):
    x,y=mercator(lat,lon)
    cx,cy=mercator(site['lat'],site['lon'])
    scale=math.cos(math.radians(site['lat']))
    east,north=(x-cx)*scale,(y-cy)*scale
    theta=math.radians(site['north'])
    ax,ay,az=site['anchor']
    return ax+east*math.cos(theta)-north*math.sin(theta),ay+east*math.sin(theta)+north*math.cos(theta),az


def earth_point(point,site):
    x,y=point[0]-site['anchor'][0],point[1]-site['anchor'][1]
    theta=math.radians(site['north'])
    east,north=x*math.cos(theta)+y*math.sin(theta),-x*math.sin(theta)+y*math.cos(theta)
    cx,cy=mercator(site['lat'],site['lon'])
    scale=math.cos(math.radians(site['lat']))
    return latlon(cx+east/scale,cy+north/scale)


def design_bounds(scene):
    from PySide6.QtGui import QMatrix4x4
    pts=[]
    def group_points(group,matrix):
        transform=matrix*group.xform if group.xform is not None else matrix
        # Furniture can stand far above the ground; only XY affects coverage.
        pts.extend(transform.map(v.position).toTuple() for v in group.mesh.vertices)
        for child in group.children:
            group_points(child,transform)
    pts.extend(v.position.toTuple() for v in scene.mesh.vertices)
    for group in scene.groups:
        group_points(group,QMatrix4x4())
    if not pts:
        return (0.,0.,0.),500.
    lo=[min(p[i] for p in pts) for i in range(3)]
    hi=[max(p[i] for p in pts) for i in range(3)]
    return ((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2]),max(100.,(hi[0]-lo[0])*1.3,(hi[1]-lo[1])*1.3)


def site_from_values(section,values,scene,saved=None):
    saved=saved or {}
    if str(values.get('site_place','')).strip():
        lat,lon=coordinates(values['site_place'])
    elif 'lat' in saved:
        lat,lon=saved['lat'],saved['lon']
    else:
        raise ValueError('Enter a Google Maps link or latitude, longitude under Site & map first.')
    anchor,width=design_bounds(scene)
    north=float(values.get('site_north') or 0)
    if not math.isfinite(north):
        raise ValueError('North rotation must be a finite number of degrees.')
    if saved and abs(saved.get('lat',lat)-lat)<1e-8 and abs(saved.get('lon',lon)-lon)<1e-8:
        anchor=tuple(saved['anchor'])
    text=str(values.get('site_map_width') or '').strip()
    if text:
        width=section.length(text,values.get('_length_unit','m'))
    if not 10<=width<=10000:
        raise ValueError('Map width must be between 10 m and 10 km.')
    result=dict(lat=lat,lon=lon,north=north,anchor=list(anchor),width=width)
    if all(abs(result[k]-saved.get(k,result[k]+1))<1e-8 for k in ('lat','lon','north','width')) and saved.get('crop_bbox'):
        result['crop_bbox']=copy.deepcopy(saved['crop_bbox'])
    return result


def fetch(url,token='',body=None,limit=16*1024*1024):
    headers={'User-Agent':'TerraRoad/0.5 (IngeTrazo desktop extension)'}
    if token:
        headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url,headers=headers,data=body)
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            data=response.read(limit+1)
            if len(data)>limit:
                raise ValueError('Map server response exceeded the size limit.')
            return data
    except ValueError:
        raise
    except Exception as exc:
        # Do not copy credential-bearing URLs from urllib exceptions into UI.
        code=getattr(exc,'code',None)
        raise ValueError('The map service could not be reached'+(f' (HTTP {code})' if code else '')+'. Check the connection or use a local map picture.') from None


def cache_dir():
    path=Path(os.environ.get('TERRAROAD_CACHE_DIR') or Path(__file__).with_name('map_cache'))
    path.mkdir(parents=True,exist_ok=True)
    return path


def provider(values):
    source=values.get('map_source','osm')
    if source=='satellite':
        return 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}','','© Esri, Maxar, Earthstar Geographics, GIS User Community'
    if source=='cesium':
        token=str(values.get('cesium_token','')).strip()
        asset=str(values.get('cesium_asset') or '3954').strip()
        if not token or not asset.isdigit():
            raise ValueError('Cesium imagery needs your ion access token and a numeric imagery asset ID.')
        data=json.loads(fetch('https://api.cesium.com/v1/assets/'+asset+'/endpoint',token))
        url=data.get('url','')
        if '{z}' not in url or not url.startswith('https://'):
            raise ValueError('This Cesium asset does not expose a flat tile URL. Choose a tiled imagery asset, OpenStreetMap, satellite, or a local picture.')
        credit='; '.join(re.sub('<[^>]+>','',a.get('html','')) for a in data.get('attributions',[])) or 'Cesium ion imagery'
        return url,data.get('accessToken',''),credit
    return 'https://tile.openstreetmap.org/{z}/{x}/{y}.png','','© OpenStreetMap contributors'


def stamp(image,credit):
    if 'Segoe UI' not in QFontDatabase.families():
        font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeui.ttf'
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    painter=QPainter(image)
    painter.setFont(QFont('Segoe UI',9))
    painter.fillRect(0,image.height()-24,image.width(),24,QColor(255,255,255,230))
    painter.setPen(QColor('#202020'))
    painter.drawText(6,image.height()-7,credit)
    painter.end()


def fetch_map(site,values,interrupted=lambda:False):
    template,token,credit=provider(values)
    n=1<<17
    lat,lon=site['lat'],site['lon']
    x,y=mercator(lat,lon)
    zoom=17
    while True:
        n=1<<zoom
        cx=(lon+180)/360*n*256
        cy=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n*256
        pixel_size=2*math.pi*R*math.cos(math.radians(lat))/(n*256)
        pixels=site['width']/pixel_size
        x0,y0=math.floor(cx-pixels/2),math.floor(cy-pixels/2)
        size=math.ceil(pixels)
        tx0,ty0=x0//256,y0//256
        tx1,ty1=(x0+size-1)//256,(y0+size-1)//256
        if max(tx1-tx0,ty1-ty0)<4 or zoom<=2:
            break
        zoom-=1
    if min(tx0,ty0)<0 or max(tx1,ty1)>=n:
        raise ValueError('This map patch crosses the date line or a polar boundary. Use a smaller patch.')
    image=QImage((tx1-tx0+1)*256,(ty1-ty0+1)*256,QImage.Format_RGB32)
    image.fill(QColor('white'))
    painter=QPainter(image)
    try:
        for tx in range(tx0,tx1+1):
            for ty in range(ty0,ty1+1):
                if interrupted():
                    raise ValueError('Map request cancelled.')
                url=template.replace('{z}',str(zoom)).replace('{x}',str(tx)).replace('{y}',str(ty)).replace('{reverseY}',str(n-1-ty))
                name=hashlib.sha256(url.encode()).hexdigest()+'.png'
                path=cache_dir()/name
                tile=QImage(str(path)) if path.exists() and time.time()-path.stat().st_mtime<7*86400 else QImage()
                if tile.isNull():
                    tile=QImage.fromData(fetch(url,token))
                    if tile.isNull():
                        raise ValueError('The map server returned an unreadable tile.')
                    tile.save(str(path),'PNG')
                painter.drawImage((tx-tx0)*256,(ty-ty0)*256,tile.scaled(256,256))
    finally:
        painter.end()
    image=image.copy(x0-tx0*256,y0-ty0*256,size,size)
    stamp(image,credit)
    target=cache_dir()/('map-'+os.urandom(8).hex()+'.png')
    if not image.save(str(target),'PNG'):
        raise ValueError('Could not save the map image to the local cache.')
    # Exact pixel bounds keep the center and physical scale aligned to tiles.
    west=x0/(n*256)*360-180
    north=math.degrees(math.atan(math.sinh(math.pi*(1-2*y0/(n*256)))))
    actual_width=size*pixel_size
    return dict(path=str(target),credit=credit,top_left=[north,west],width=actual_width,height=actual_width,site=site)


def image_plane(result):
    site=result['site']
    o=QVector3D(*world_point(*result['top_left'],site))
    o.setZ(o.z()-.05)
    theta=math.radians(site['north'])
    width,height=result['width'],result['height']
    u=QVector3D(width*math.cos(theta),width*math.sin(theta),0)
    v=QVector3D(-height*math.sin(theta),height*math.cos(theta),0)
    return ImagePlane(result['path'],o-v,u,v,height/width,PREFIX+result['credit'],layer=MAP_LAYER,locked=True)


def osm_bbox(south,west,north,east):
    """Read public OSM nodes/ways when an Overpass interpreter is unavailable."""
    import xml.etree.ElementTree as ET
    bbox=','.join(str(v) for v in (west,south,east,north))
    document=ET.fromstring(fetch('https://api.openstreetmap.org/api/0.6/map?bbox='+bbox))
    nodes={n.attrib['id']:{'lat':float(n.attrib['lat']),'lon':float(n.attrib['lon'])} for n in document.findall('node')}
    ways=[]
    for way in document.findall('way'):
        tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
        if 'highway' in tags:
            ways.append(dict(tags=tags,geometry=[nodes[n.attrib['ref']] for n in way.findall('nd') if n.attrib['ref'] in nodes]))
    return {'elements':ways}


def fetch_roads(site,values,interrupted=lambda:False):
    width=min(site['width'],5000.)
    cx,cy=mercator(site['lat'],site['lon'])
    half=width/2/math.cos(math.radians(site['lat']))
    south,west=latlon(cx-half,cy-half)
    north,east=latlon(cx+half,cy+half)
    if site.get('crop_bbox'):
        south,west,north,east=site['crop_bbox']
    query=f'[out:json][timeout:20];way["highway"]({south},{west},{north},{east});out tags geom;'
    body=urllib.parse.urlencode({'data':query}).encode()
    response=None
    # The main map API is faster and more reliable for a small design patch;
    # larger requests belong on the filtered Overpass service.
    if width<=1000 or site.get('crop_bbox'):
        try:
            response=osm_bbox(south,west,north,east)
        except Exception:
            pass
    for endpoint in ('https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter'):
        if response is not None:
            break
        if interrupted():
            raise ValueError('Map tracing cancelled.')
        try:
            response=json.loads(fetch(endpoint,body=body))
            if response.get('remark') and not response.get('elements'):
                raise ValueError('The road data service is busy. Try again or crop a smaller area.')
            break
        except (ValueError,TypeError):
            if endpoint.endswith('kumi.systems/api/interpreter'):
                try:
                    if width>2000 and not site.get('crop_bbox'):
                        raise ValueError('Crop the map to a smaller patch (about 1 km across) and retry tracing.')
                    response=osm_bbox(south,west,north,east)
                except Exception:
                    raise ValueError('The road data services could not complete this request. Try again or crop a smaller map area (about 1 km across).') from None
    result=[]
    for way in response.get('elements',[]):
        tags=way.get('tags',{})
        if tags.get('highway') in ('steps','proposed','construction'):
            continue
        # Overpass returns whole ways, sometimes kilometres past the crop.
        # Clip every segment to the requested geographic rectangle.
        geometry=[pt for pt in way.get('geometry',[]) if pt and 'lat' in pt]
        chain=[]
        def finish():
            nonlocal chain
            if len(chain)>=2:
                result.append({'points':chain,'tags':tags})
            chain=[]
        for a,b in zip(geometry,geometry[1:]):
            x,y=a['lon'],a['lat']
            dx,dy=b['lon']-x,b['lat']-y
            lo,hi=0.,1.
            for delta,distance in ((-dx,x-west),(dx,east-x),(-dy,y-south),(dy,north-y)):
                if abs(delta)<1e-15:
                    if distance<0:
                        lo,hi=1.,0.
                        break
                elif delta<0:
                    lo=max(lo,distance/delta)
                else:
                    hi=min(hi,distance/delta)
            if hi-lo<=1e-10:
                finish()
                continue
            first=world_point(y+dy*lo,x+dx*lo,site)
            last=world_point(y+dy*hi,x+dx*hi,site)
            if chain and math.dist(chain[-1],first)>1e-4:
                finish()
            if not chain:
                chain.append(first)
            chain.append(last)
            if hi<1.-1e-9:
                finish()
        finish()
        if len(result)>2000:
            raise ValueError('Too many map roads; reduce the map width.')
    if not result:
        raise ValueError('No mapped roads were returned for this site.')
    return place_ways(result,site)


class Job(QThread):
    result_ready=Signal(object)
    failed=Signal(str)
    def __init__(self,operation,site,values,parent=None):
        super().__init__(parent)
        self.operation,self.site,self.values=operation,site,values.copy()
    def run(self):
        try:
            result=(fetch_map(self.site,self.values,self.isInterruptionRequested) if self.operation=='map'
                    else fetch_roads(self.site,self.values,self.isInterruptionRequested))
            self.result_ready.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class ChangeSite(Command):
    def __init__(self,key,site,images=None,group=None):
        self.key,self.site,self.images,self.group=key,copy.deepcopy(site),images,group
        self.groups=group if isinstance(group,list) else [group] if group is not None else []
        self.before=None
    def do(self,scene):
        from core.layers import Layer
        if self.before is None:
            self.before=(copy.deepcopy(scene.plugin_data.get(self.key)),self.key in scene.plugin_data,
                         list(scene.image_planes),list(scene.layers),set(scene.selection))
        data=copy.deepcopy(scene.plugin_data.get(self.key) or {})
        data['site']=copy.deepcopy(self.site)
        scene.plugin_data[self.key]=data
        if self.images is not None:
            scene.selection.difference_update(image for image in scene.image_planes if image.name.startswith(PREFIX))
            scene.image_planes[:]=[image for image in scene.image_planes if not image.name.startswith(PREFIX)]+self.images
            if scene.layer(MAP_LAYER) is None:
                scene.layers.append(Layer(MAP_LAYER))
        if self.groups:
            scene.groups.extend(g for g in self.groups if g not in scene.groups)
            scene.selection.clear()
            scene.selection.update(self.groups)
        scene.version+=1
    def undo(self,scene):
        data,existed,images,layers,selection=self.before
        if existed:
            scene.plugin_data[self.key]=copy.deepcopy(data)
        else:
            scene.plugin_data.pop(self.key,None)
        scene.image_planes[:]=images
        scene.layers[:]=layers
        for group in self.groups:
            if group in scene.groups:
                scene.groups.remove(group)
        scene.selection.clear()
        scene.selection.update(selection)
        scene.version+=1


def traced_group(engine,ways,edges=False):
    from core.group import Group
    from core.mesh import Mesh
    mesh=Mesh()
    for way in ways:
        points=way['points']
        if not edges:
            for a,b in zip(points,points[1:]):
                mesh.add_edge(QVector3D(*a),QVector3D(*b))
        else:
            tags=way['tags']
            try:
                width=float(str(tags.get('width','')).split()[0])
            except (ValueError,IndexError):
                try:
                    width=float(tags.get('lanes','2'))*3.
                except ValueError:
                    width=6.
            width=min(40.,max(2.,width))
            normals=engine.frames(points)
            for side in (-1,1):
                shifted=[QVector3D(pt[0]+n[0]*width/2*side,pt[1]+n[1]*width/2*side,pt[2]) for pt,n in zip(points,normals)]
                for a,b in zip(shifted,shifted[1:]):
                    mesh.add_edge(a,b)
    group=Group(mesh,name='TerraRoad — OSM '+('estimated road edges' if edges else 'road centerlines'))
    group.ext={engine.KEY+'_trace':{'source':'© OpenStreetMap contributors','estimated_edges':edges}}
    return group


def traced_groups(engine,ways,edges=False):
    result=[]
    for i,way in enumerate(ways):
        group=traced_group(engine,[way],edges)
        tags=way.get('tags',{})
        group.name='TerraRoad trace — '+str(tags.get('name') or tags.get('ref') or tags.get('highway') or 'Road')+f' {i+1}'
        group.ext[engine.KEY+'_trace']['tags']=copy.deepcopy(tags)
        for edge in group.mesh.edges:
            edge.curve=i+1
        result.append(group)
    return result
