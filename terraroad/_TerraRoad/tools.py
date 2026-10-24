# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Spatial TerraRoad tools using the host's native snaps and line controls."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QVector3D
from tools.base import Tool
from tools.line import LineTool


class RoadDraw(LineTool):
    name='TerraRoad — draw a road'
    shortcut=None
    description='Click a centerline; each segment updates its road. Esc starts another road.'
    def __init__(self,panel):
        super().__init__()
        self.panel=panel
        self.values=panel.collect()
        self.current_uid=None
        self.current_groups=[]
        self.base_groups=[]
        self.base_segments=[]
        self.states=[]
    def _reset(self):
        super()._reset()
        self.current_uid=None
        self.current_groups=[]
        self.base_groups=[]
        self.base_segments=[]
        self.states=[]
    def _commit_edge(self,viewport,start,end):
        engine=self.panel.engine
        points=[v.toTuple() for v in self.chain_vertices]+[end.toTuple()]
        segments=self.base_segments+list(zip(points,points[1:]))
        values=self.values.copy()
        # The native tool must remain usable with a wide style and a tight
        # clicked corner. A miter is an explicit, persisted fallback.
        try:
            new=engine.support('network').make_network(engine,self.panel.section,segments,values,'TerraRoad')
        except ValueError as exc:
            if not any(text in str(exc) for text in ('corner radius','wider than this bend')):
                raise
            profile=self.panel.section.build(self.panel.section.parameters(values))
            radius=max(abs(profile.left_extent),abs(profile.right_extent))*1.05+.05
            values['corner_radius']=f'{radius}m'
            new=engine.support('network').make_network(engine,self.panel.section,segments,values,'TerraRoad')
            viewport.flash_status('The corner radius was enlarged to fit this road width.',5000)
        self.panel.apply_materials(new,self.values)
        old=[g for g in self.current_groups+self.base_groups if g in viewport.scene.groups]
        command=engine.support('model').ReplaceSelection(engine,new,list(dict.fromkeys(old)))
        self.pending_groups=command.after_groups
        return command
    def begin(self,viewport,point):
        point,group=self.snap_point(viewport,point)
        self.start_point=point
        self.chain_first_point=point
        self.chain_vertices=[point]
        self.work_plane=(QVector3D(point),QVector3D(0,0,1))
        if group is not None:
            # A branch inherits the existing road's physical style; opening
            # the drawing tool with another preset must not resize its trunk.
            import copy
            self.values=copy.deepcopy(group.ext[self.panel.engine.KEY]['values'])
            self.base_segments,self.base_groups=self.panel.engine.support('drawing').sources(self.panel.engine,viewport.scene,[group])
        return point
    def snap_point(self,viewport,point):
        return self.panel.engine.support('drawing').snap(self.panel.engine,viewport.scene,point,self.current_groups+self.base_groups)
    def commit_point(self,viewport,point):
        point,group=self.snap_point(viewport,point)
        if (point-self.start_point).length()<1e-5:
            return False
        before=(list(self.current_groups),list(self.base_groups),list(self.base_segments))
        if group is not None:
            extra,groups=self.panel.engine.support('drawing').sources(self.panel.engine,viewport.scene,[group])
            self.base_segments+=extra
            self.base_groups+=groups
        try:
            command=self._commit_edge(viewport,self.start_point,point)
            viewport.history.execute(command)
            if viewport.history.last_error:
                raise ValueError(viewport.history.last_error)
        except Exception:
            self.current_groups,self.base_groups,self.base_segments=before
            raise
        self.states.append(before)
        self.current_groups=self.pending_groups
        self.current_uid=self.current_groups[0].uid
        self.chain_vertices.append(point)
        self.start_point=point
        self.hover_point=point
        viewport.notify_scene_changed()
        viewport.update()
        return True
    def on_click(self,ctx):
        try:
            if self.start_point is None:
                self.begin(ctx.viewport,ctx.world)
            else:
                self.commit_point(ctx.viewport,QVector3D(ctx.world))
        except Exception as exc:
            ctx.viewport.flash_status(str(exc),6000)
            self.panel.result.setPlainText(str(exc))
    def on_value(self,viewport,value):
        try:
            if self.start_point is None:
                return False
            if isinstance(value,tuple):
                end=self.start_point+QVector3D(*value)
            elif self.hover_point is not None:
                end=self.start_point+(self.hover_point-self.start_point).normalized()*value
            else:
                return False
            return self.commit_point(viewport,end)
        except Exception as exc:
            viewport.flash_status(str(exc),6000)
            return False
    def on_undo(self,viewport):
        if self.states:
            if viewport.history.undo():
                self.current_groups,self.base_groups,self.base_segments=self.states.pop()
                self.chain_vertices.pop()
                self.start_point=self.chain_vertices[-1]
                viewport.notify_scene_changed()
                viewport.update()
                return True
        self._reset()
        viewport.update()
        return False
    def on_key(self,viewport,key,modifiers):
        if key in (Qt.Key_Return,Qt.Key_Enter):
            self._reset()
            viewport.update()
            viewport.flash_status('Click to start another road or a branch on an existing road.',4000)
            return True
        return False
    def on_double_click(self,ctx):
        if self.start_point is not None and (ctx.world-self.start_point).length()>.001:
            self.on_click(ctx)
        self._reset()
        ctx.viewport.update()


class ManualTrace(RoadDraw):
    name='TerraRoad — trace roads on map'
    description='Click along the visible road. Enter starts another trace; Esc cancels the unfinished segment.'
    def snap_point(self,viewport,point):
        return QVector3D(point),None
    def _commit_edge(self,viewport,start,end):
        from core.history import Command
        engine=self.panel.engine
        points=[v.toTuple() for v in self.chain_vertices]+[end.toTuple()]
        new=engine.support('site').traced_group(engine,[{'points':points,'tags':{'highway':'manual'}}])
        new.name='TerraRoad — manual map trace'
        new.ext[engine.KEY+'_trace']['source']='Manually traced from reference image'
        old=list(self.current_groups)
        self.pending_groups=[new]
        class TraceCommand(Command):
            def __init__(self):
                self.before=None
            def do(self,scene):
                if self.before is None:
                    self.before=list(scene.groups),set(scene.selection)
                scene.groups[:]=[g for g in scene.groups if g not in old]+[new]
                scene.selection.clear()
                scene.selection.add(new)
                scene.version+=1
            def undo(self,scene):
                scene.groups[:]=self.before[0]
                scene.selection.clear()
                scene.selection.update(self.before[1])
                scene.version+=1
        return TraceCommand()


class PickPoints(Tool):
    shortcut=None
    def __init__(self,panel,name,count,callback):
        self.panel,self.name,self.count,self.callback=panel,name,count,callback
        self.points=[]
        self.start_point=None
        self.hover_point=None
    def on_activate(self,viewport):
        self.points=[]
        viewport.flash_status(self.name,5000)
    def on_deactivate(self,viewport):
        pass
    def on_hover(self,ctx):
        self.hover_point=ctx.world
        ctx.viewport.update()
    def on_click(self,ctx):
        self.points.append(QVector3D(ctx.world))
        self.start_point=ctx.world
        if len(self.points)>=self.count:
            try:
                self.callback(self.points)
            except Exception as exc:
                self.panel.result.setPlainText(str(exc))
                ctx.viewport.flash_status(str(exc),6000)
            from tools.select import SelectTool
            ctx.viewport.set_active_tool(SelectTool())
            self.panel.show()
            self.panel.raise_()
    def on_cancel(self,viewport):
        from tools.select import SelectTool
        viewport.set_active_tool(SelectTool())
        self.panel.show()
    def rubber_band_lines(self):
        return [(self.start_point,self.hover_point)] if self.start_point is not None and self.hover_point is not None else []


class CropWindow(PickPoints):
    description='Click two opposite corners of the rectangular crop window.'
    def __init__(self,panel,name,count,callback,plane):
        super().__init__(panel,name,count,callback)
        self.plane=plane
        self.work_plane=plane.plane()
    def rubber_band_lines(self):
        if self.start_point is None or self.hover_point is None:
            return []
        a,b=self.plane.project(self.start_point),self.plane.project(self.hover_point)
        points=[self.plane.origin+self.plane.u*u+self.plane.v*v for u,v in ((a[0],a[1]),(b[0],a[1]),(b[0],b[1]),(a[0],b[1]))]
        return list(zip(points,points[1:]+points[:1]))


class TraceSelect(Tool):
    name='TerraRoad — select traced map roads'
    description='Click a road on the map; Shift adds roads. Enter returns to TerraRoad.'
    def __init__(self,panel,groups,tolerance):
        self.panel,self.groups,self.tolerance=panel,groups,tolerance
        self.hover=None
    def on_activate(self,viewport):
        viewport.flash_status(self.description,7000)
        if self.groups:
            # Use the map/trace plane for cursor rays, including tilted maps.
            maps=[p for p in self.panel.app.scene.image_planes if p.name.startswith(self.panel.engine.support('site').PREFIX)]
            if maps:
                self.work_plane=maps[0].plane()
    def on_deactivate(self,viewport):
        self.hover=None
    def near(self,point):
        best=None
        for group in self.groups:
            if group not in self.panel.app.scene.groups:
                continue
            for edge in group.mesh.edges:
                a,b=edge.a,edge.b
                delta=b-a
                t=max(0.,min(1.,QVector3D.dotProduct(point-a,delta)/max(delta.lengthSquared(),1e-8)))
                distance=(point-(a+delta*t)).lengthSquared()
                if distance<self.tolerance**2 and (best is None or distance<best[0]):
                    best=distance,group
        return best[1] if best else None
    def on_hover(self,ctx):
        self.hover=self.near(ctx.world)
        ctx.viewport.update()
    def on_click(self,ctx):
        group=self.near(ctx.world)
        if group is None:
            ctx.viewport.flash_status('No mapped road here. OSM can differ from aerial imagery; use manual trace for unmapped roads.',6000)
            return
        if not ctx.modifiers & Qt.ShiftModifier:
            ctx.viewport.scene.selection.clear()
        ctx.viewport.scene.selection.add(group)
        self.panel.refresh_selection()
        ctx.viewport.update()
    def rubber_band_lines(self):
        return [(e.a,e.b) for e in self.hover.mesh.edges] if self.hover else []
    def on_cancel(self,viewport):
        from tools.select import SelectTool
        viewport.set_active_tool(SelectTool())
        self.panel.show()
        self.panel.refresh_selection()
    def on_key(self,viewport,key,modifiers):
        if key in (Qt.Key_Enter,Qt.Key_Return):
            self.on_cancel(viewport)
            return True
        return False


def start(panel,tool,seed=None):
    if panel.app.scene.edit_group is not None:
        raise ValueError('Exit group editing before using a TerraRoad drawing tool.')
    panel.hide()
    panel.app.viewport.set_active_tool(tool)
    if seed is not None:
        if isinstance(tool,RoadDraw):
            tool.begin(panel.app.viewport,QVector3D(*seed))
        else:
            tool.start_point=QVector3D(*seed)
            tool.chain_first_point=QVector3D(*seed)
            tool.chain_vertices=[QVector3D(*seed)]
    panel.app.viewport.setFocus()
    return tool
