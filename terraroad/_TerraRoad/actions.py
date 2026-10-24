# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Model editing operations shared by TerraRoad's panel and spatial tools."""
import copy
import math
from PySide6.QtGui import QVector3D,QMatrix4x4
from PySide6.QtWidgets import QInputDialog


class Editor:
    def __init__(self,panel):
        self.panel=panel
    def __getattr__(self,name):
        return getattr(self.panel,name)
    def require(self,face=None):
        old=self.selected()
        if old is None:
            raise ValueError('Select one TerraRoad road or junction first.')
        data=old.ext[self.engine.KEY]
        if face is True and not data.get('face_road'):
            raise ValueError('This action needs a converted face road.')
        if face is False and (data.get('face_road') or data.get('network')):
            raise ValueError('Select an individual centerline road for this action.')
        return old,data
    def execute(self,command):
        self.app.viewport.history.execute(command)
        if self.app.viewport.history.last_error:
            raise ValueError(self.app.viewport.history.last_error)
        self.app.viewport.notify_scene_changed()
        self.app.viewport.update()
        self.refresh_selection()
    def batch(self,pairs):
        from core.history import Command
        prepared=[(old,self.engine.support('model').members(self.engine,new)) for old,new in pairs]
        class Batch(Command):
            def __init__(self):
                self.before=None
            def do(self,scene):
                if self.before is None:
                    self.before=(list(scene.groups),set(scene.selection))
                for old,news in prepared:
                    i=scene.groups.index(old)
                    scene.groups[i:i+1]=news
                scene.selection.clear()
                scene.selection.update(g for old,news in prepared for g in news)
                scene.version+=1
            def undo(self,scene):
                scene.groups[:]=self.before[0]
                scene.selection.clear()
                scene.selection.update(self.before[1])
                scene.version+=1
        self.execute(Batch())
    def rebuilt(self,old,values):
        new=self.engine.support('model').rebuild(self.engine,self.section,old.ext[self.engine.KEY],values,old.name)
        self.preserve(new,old)
        self.apply_materials(new,values)
        return new
    def draw(self,seed=None):
        api=self.engine.support('tools')
        api.start(self.panel,api.RoadDraw(self.panel),seed)
    def pick(self,name,count,callback):
        api=self.engine.support('tools')
        if name.startswith('Click two opposite corners of the map crop'):
            prefix=self.engine.support('site').PREFIX
            plane=next((p for p in self.app.scene.image_planes if p.name.startswith(prefix)),None)
            if plane is not None:
                return api.start(self.panel,api.CropWindow(self.panel,name,count,callback,plane))
        return api.start(self.panel,api.PickPoints(self.panel,name,count,callback))
    def restore(self):
        old,data=self.require()
        values=copy.deepcopy((self.app.document_data(default={}) or {}).get('values') or self.section.DEFAULTS)
        self.execute(self.engine.support('model').Replace(self.engine,self.rebuilt(old,values),old))
        self.apply(values)
    def branch(self):
        old,data=self.require(False)
        self.load_selected()
        # Ask for the connection point, then start the ordinary line tool there.
        def begin(points):
            from PySide6.QtCore import QTimer
            seed=points[0].toTuple()
            QTimer.singleShot(0,lambda:self.draw(seed))
        self.pick('Click the connection point, then draw the new road',1,begin)
    def move_point(self):
        old,data=self.require(False)
        def move(points):
            inverse=(old.xform or QMatrix4x4()).inverted()[0]
            at=inverse.map(points[0])
            route=copy.deepcopy(data['points'])
            index=min(range(len(route)),key=lambda i:(QVector3D(*route[i])-at).lengthSquared())
            route[index]=list(inverse.map(points[1]).toTuple())
            new=self.engine.make_detailed_road(route,data['values'],old.name)
            self.preserve(new,old)
            self.apply_materials(new,data['values'])
            self.execute(self.engine.support('model').Replace(self.engine,new,old))
        self.pick('Click a centerline vertex, then its new position',2,move)
    def mirror_copy(self):
        old,data=self.require()
        def mirror(points):
            a,b=points
            dx,dy=b.x()-a.x(),b.y()-a.y()
            length=math.hypot(dx,dy)
            if length<1e-5:
                raise ValueError('Pick two different points on the mirror line.')
            ux,uy=dx/length,dy/length
            xx,xy,yy=2*ux*ux-1,2*ux*uy,2*uy*uy-1
            reflection=QMatrix4x4(xx,xy,0,a.x()-xx*a.x()-xy*a.y(),xy,yy,0,a.y()-xy*a.x()-yy*a.y(),0,0,1,0,0,0,0,1)
            new=self.rebuilt(old,data['values'])
            from core.group import new_uid
            new.uid=new_uid()
            for key in ('network_source','network_frame','member_frame','design_id','member_name'):
                new.ext[self.engine.KEY].pop(key,None)
            new.name=old.name+' mirrored'
            new.xform=reflection*(old.xform or QMatrix4x4())
            self.execute(self.engine.support('model').Replace(self.engine,new))
        self.pick('Click two points defining the line of symmetry',2,mirror)
    def network(self):
        from core.mesh import Edge
        chosen=[g for g in self.roads() if g in self.app.scene.selection]
        segments=[(e.a.toTuple(),e.b.toTuple()) for e in self.app.scene.selection if isinstance(e,Edge)]
        for group in self.app.scene.selection:
            if self.engine.KEY+'_trace' in (getattr(group,'ext',None) or {}):
                matrix=group.xform or QMatrix4x4()
                segments.extend((matrix.map(e.a).toTuple(),matrix.map(e.b).toTuple()) for e in group.mesh.edges)
        if not chosen and not segments:
            chosen=[g for g in self.roads() if not g.ext[self.engine.KEY].get('face_road') or g.ext[self.engine.KEY].get('network_source')]
        done=set()
        for old in chosen:
            data=old.ext[self.engine.KEY]
            matrix=old.xform or QMatrix4x4()
            if data.get('network_source'):
                # Recover the untrimmed source graph once per network. Derive
                # the original network frame from this member's recorded frame.
                design=data['design_id']
                if design in done:
                    continue
                done.add(design)
                source=data['network_source']
                frame=QMatrix4x4(*data['network_frame']) if 'network_frame' in data else QMatrix4x4()
                if 'member_frame' in data:
                    frame=matrix*QMatrix4x4(*data['member_frame']).inverted()[0]*frame
                segments.extend((frame.map(QVector3D(*a)).toTuple(),frame.map(QVector3D(*b)).toTuple()) for a,b in source['segments'])
            elif data.get('network'):
                segments.extend((matrix.map(QVector3D(*a)).toTuple(),matrix.map(QVector3D(*b)).toTuple()) for a,b in data['segments'])
            elif not data.get('face_road'):
                pts=[matrix.map(QVector3D(*p)).toTuple() for p in data['points']]
                segments.extend(zip(pts,pts[1:]))
        # Replacing one network also replaces its existing junctions, avoiding
        # overlapping stale returns and boxes after switching to roundabouts.
        chosen=list(dict.fromkeys(chosen+[g for g in self.roads() if g.ext[self.engine.KEY].get('design_id') in done]))
        values=self.collect()
        root=self.engine.support('network').make_network(self.engine,self.section,segments,values,'TerraRoad network')
        self.apply_materials(root,values)
        self.execute(self.engine.support('model').ReplaceSelection(self.engine,root,chosen))
        self.result.setPlainText('Built separate road and junction groups. Double-click a group to edit its component parts. Undo restores the previous layout.')
    def face_mark(self,kind):
        old,data=self.require(True)
        if data.get('kind')=='junction':
            raise ValueError('Use the yellow box setting for a junction; arrows and crossings need a face road.')
        def place(points):
            local=(old.xform or QMatrix4x4()).inverted()[0].map(points[0])
            values=copy.deepcopy(data['values'])
            values.setdefault('_face_marks',[]).append(dict(type=kind,point=list(local.toTuple())))
            self.update_face(old,values)
        self.pick('Click where to place the '+kind,1,place)
    def clear_marks(self):
        old,data=self.require(True)
        values=copy.deepcopy(data['values'])
        values.pop('_face_marks',None)
        self.update_face(old,values)
    def spine(self,clear=False):
        old,data=self.require(True)
        values=copy.deepcopy(data['values'])
        if clear:
            values.pop('_face_spine',None)
        else:
            points=self.selected_points()
            if len(points)!=2:
                raise ValueError('Select one straight direction line together with the face road. Curved face spines are not supported yet.')
            inverse=(old.xform or QMatrix4x4()).inverted()[0]
            values['_face_spine']=[list(inverse.map(QVector3D(*p)).toTuple()) for p in points]
        self.update_face(old,values)
    def components(self):
        old,data=self.require()
        from core.group import copy_group
        new=copy_group(old)
        new.ext=copy.deepcopy(old.ext)
        self.engine.support('model').components(new)
        self.execute(self.engine.support('model').Replace(self.engine,new,old))
    def lighten(self):
        choice,ok=QInputDialog.getItem(self.panel,'Make model lighter','Apply to every TerraRoad group:',
            ['Use 3 m curb paint blocks','Remove curb paint blocks','Remove lamp posts','Remove parking paint'],0,False)
        if not ok:
            return
        pairs=[]
        for old in self.roads():
            values=copy.deepcopy(old.ext[self.engine.KEY]['values'])
            if choice.startswith('Use'):
                values['curb_block_length']='3m'
            elif 'curb' in choice:
                values['curb_paint']=False
            elif 'lamp' in choice:
                values['pole_placement']='none'
            else:
                values['parking_marks']=False
            pairs.append((old,self.rebuilt(old,values)))
        self.batch(pairs)
    def connect(self):
        faces=[g for g in self.roads() if g.ext[self.engine.KEY].get('face_road') and not g.ext[self.engine.KEY].get('network_source')]
        if len(faces)<2:
            raise ValueError('Create at least two face roads sharing a boundary edge first.')
        api=self.engine.support('face_edit')
        self.batch(api.connected(self.panel,faces))
        self.result.setPlainText('Rebuilt adjoining face roads with open mouths. Curb and walkway stop across each shared edge; asphalt fills the connection.')
    def split(self):
        self.engine.support('face_edit').split(self.panel)
    def feature(self,kind,from_line=False):
        old,data=self.require(False)
        controls=self.section.parameters(self.collect())
        if kind=='uturn' and not self.section.divided(self.section.parameters(data['values'])):
            raise ValueError('A U-turn opening needs a divided road with a median.')
        if kind=='bridge' and controls['bridge_type']!='deck':
            raise ValueError('The native bridge tool currently builds deck bridges. Choose Deck above; arches and culvert variants are still being ported.')
        def place(points):
            local=(old.xform or QMatrix4x4()).inverted()[0].map(points[0])
            api=self.engine.support('features')
            # Use the same rounded alignment as the road builder.
            t=self.section.build(self.section.parameters(data['values']))
            route,axes,_=self.engine.prepare(data['points'],self.engine.Parameters(lanes=1,lane_width=1,
                thickness=.1,crown=0,sidewalk=0,curb_width=0,markings=False,radius=t.params['corner_radius'],
                station_interval=max(.0254,t.params['station_interval']),offset=0,elevation=0),
                [(part.name,part.points,(.5,.5,.5)) for part in t.parts])
            stations=self.engine.station_lengths(route)
            station=api.nearest(local,route,stations)[0]
            p=controls
            item=dict(type=kind,station=station)
            if kind in ('grade','bridge'):
                span=p['bridge_span']
                ramp=p['bridge_ramp']
                rise=p['bridge_rise'] if kind=='grade' else p['bridge_headroom']+p['bridge_depth']+p['thickness']
                item.update(length=span,taper=ramp,rise=rise)
                if kind=='bridge':
                    item.update(width=p['bridge_deck_width'] or t.kerb_faces['right'][0]-t.kerb_faces['left'][0],
                        depth=p['bridge_depth'],parapet=p['bridge_parapet'],parapet_height=p['bridge_parapet_height'],spans=p['bridge_arches'])
                if span<=0 or ramp<=0 or station-span/2-ramp<0 or station+span/2+ramp>stations[-1]:
                    raise ValueError('The span and both approach ramps must fit inside this road. Reduce their lengths or pick farther from the ends.')
            elif kind=='widen':
                item.update(length=p['widen_length'],taper=p['widen_taper'],road=p['widen_by'],median=p['widen_median'],side=p['widen_side'])
                if item['length']<=0 or item['taper']<=0:
                    raise ValueError('Widening length and taper must be positive.')
                if station-item['length']/2-item['taper']<0 or station+item['length']/2+item['taper']>stations[-1]:
                    raise ValueError('The widened section and its tapers must fit inside the road.')
            else:
                item['length']=p['u_turn_length'] if kind=='uturn' else p['crossing_length']
                if item['length']<=0:
                    raise ValueError('The opening/crossing length must be positive.')
            values=copy.deepcopy(data['values'])
            values.setdefault('_features',[]).append(item)
            # Crossing and median cap dimensions are the visible controls.
            for field in ('crossing_length','crossing_bar_width','crossing_bar_gap','stripe_lift','u_turn_marks'):
                values[field]=self.collect()[field]
            self.execute(self.engine.support('model').Replace(self.engine,self.rebuilt(old,values),old))
            self.result.setPlainText('Added '+kind+'. The feature is saved with this road and returns on rebuild; Undo removes it.')
        if from_line:
            points=self.selected_points()
            if len(points)<2:
                raise ValueError('Select a line crossing the selected road first.')
            a,b=QVector3D(*points[0]),QVector3D(*points[-1])
            return place([(a+b)/2])
        self.pick('Click the road at the center of the '+kind,1,place)
