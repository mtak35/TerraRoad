# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Editable component parts and independent road/junction scene groups."""
import copy
from PySide6.QtGui import QMatrix4x4
from core.history import Command


def components(group):
    """Containers remain groups; physical parts become unique components."""
    group.component=None
    if group.children and group.xform is None:
        group.xform=QMatrix4x4()
    def part(item):
        if item.xform is None:
            item.xform=QMatrix4x4()
        item.component='TerraRoad '+item.name+' '+item.uid
        for child in item.children:
            part(child)
    for item in group.children:
        part(item)
    return group


def members(engine,root):
    data=root.ext[engine.KEY]
    if not data.get('network'):
        return [components(root)]
    result=[]
    junction=None
    # Network builder emits each junction followed by its roadside parts.
    for child in root.children:
        record=(child.ext or {}).get(engine.KEY)
        if record:
            child.xform=root.xform*child.xform if child.xform is not None else QMatrix4x4(root.xform)
            record['network_frame']=list(root.xform.copyDataTo())
            record['member_frame']=list(child.xform.copyDataTo())
            record['design_id']=root.uid
            record['network_source']=copy.deepcopy(data)
            record['member_name']=child.name
            child.name=root.name+' — '+child.name
            result.append(child)
            junction=child if record.get('kind')=='junction' else None
        elif junction is not None:
            # Parts were generated in the network's frame; rebase them into
            # their junction without moving a vertex in the model.
            matrix=junction.xform.inverted()[0]*root.xform
            child.xform=matrix*child.xform if child.xform is not None else matrix
            junction.children.append(child)
    return [components(group) for group in result]


def rebuild(engine,section,data,values,name):
    if data.get('network_source') and data.get('kind')=='junction':
        source=data['network_source']
        root=engine.support('network').make_network(engine,section,source['segments'],values,'Network')
        # A junction edit changes its own accessories, retaining its stored
        # network geometry and the independently edited approach roads.
        part=next(g for g in members(engine,root) if g.ext[engine.KEY].get('member_name')==data['member_name'])
        part.name=name
        for key in ('network_source','design_id','member_name','network_frame','member_frame'):
            if key in data:
                part.ext[engine.KEY][key]=copy.deepcopy(data[key])
        return part
    if data.get('face_road'):
        return engine.support('faces').from_loops(engine,section,data['loops'],values,name,data.get('kind','road'))
    if data.get('network'):
        return engine.support('network').make_network(engine,section,data['segments'],values,name)
    new=engine.make_detailed_road(data['points'],values,name)
    for key in ('network_source','design_id','member_name','network_frame','member_frame'):
        if key in data:
            new.ext[engine.KEY][key]=copy.deepcopy(data[key])
    return new


class Replace(Command):
    def __init__(self,engine,new,old=None):
        self.engine,self.new,self.old=engine,new,old
        self.before=None
        self.after_groups=members(engine,new)
    def do(self,scene):
        if self.before is None:
            self.before=(list(scene.groups),set(scene.selection),copy.deepcopy(scene.plugin_data))
        if self.old is not None:
            if self.old not in scene.groups:
                raise ValueError('The selected road is no longer in this document.')
            index=scene.groups.index(self.old)
            scene.groups[index:index+1]=self.after_groups
        else:
            scene.groups.extend(self.after_groups)
        scene.selection.clear()
        scene.selection.update(self.after_groups)
        values=self.new.ext[self.engine.KEY].get('values')
        if values is not None:
            data=copy.deepcopy(scene.plugin_data.get(self.engine.KEY) or {})
            data['values']=copy.deepcopy(values)
            scene.plugin_data[self.engine.KEY]=data
        scene.version+=1

    def undo(self,scene):
        groups,selection,data=self.before
        scene.groups[:]=groups
        scene.selection.clear()
        scene.selection.update(selection)
        scene.plugin_data.clear()
        scene.plugin_data.update(copy.deepcopy(data))
        scene.version+=1


class ReplaceSelection(Replace):
    def __init__(self,engine,new,old_groups):
        super().__init__(engine,new)
        self.old_groups=list(old_groups)
    def do(self,scene):
        if self.before is None:
            self.before=(list(scene.groups),set(scene.selection),copy.deepcopy(scene.plugin_data))
        for group in self.old_groups:
            if group in scene.groups:
                scene.groups.remove(group)
        super().do(scene)
