# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Apply the same material identities from both menu and panel rebuilds."""
import re

COLOR_FIELDS={'mat_pavement':'pavement','mat_gutter':'gutter','mat_shoulder':'shoulder',
              'mat_curb':'curb','mat_sidewalk':'sidewalk','mat_green':'green','mat_parking':'parking'}


def apply(engine,scene,road,values):
    values={**engine.support('section').DEFAULTS,**values}
    parts=(road.ext or {}).get(engine.KEY,{}).get('section',{}).get('parts',[])
    for child in road.children:
        if engine.KEY in (child.ext or {}):
            apply(engine,scene,child,values)
        key=next((part['key'] for part in parts if child.name==part['name'] or child.name.startswith(part['name']+' ')),None)
        if child.name=='Pavement':
            key='pavement'
        data=(child.ext or {}).get(engine.KEY+'_part',{})
        key=data.get('key',key)
        field=next((field for field,part_key in COLOR_FIELDS.items() if part_key==key),None)
        if key=='curb' and engine.support('section').truth(values.get('curb_paint')):
            index=data.get('paint_index')
            if index is None:
                number=re.search(r' (\d+)$',child.name)
                index=int(number[1])-1 if number else None
            if index is not None:
                field='mat_curb_dark' if index%2==0 else 'mat_curb_light'
        if child.name.startswith(('Edge line','Junction Edge line')):
            field='mat_edge'
        elif child.name.startswith('Centre line'):
            field='mat_stripe_ctr'
        elif child.name.startswith(('Lane divider','Parking marking')):
            field='mat_stripe'
        elif child.name.startswith('Zebra crossing'):
            field='mat_crossing'
        elif key=='box':
            field='mat_box'
        elif key=='stripe':
            field='mat_stripe'
        elif key=='parking_marking':
            field='mat_stripe'
        elif key=='crossing':
            field='mat_crossing'
        if not field:
            if child.children and engine.KEY not in (child.ext or {}):
                apply(engine,scene,child,values)
            continue
        name=values.get(field,'')
        material=scene.materials.get(name)
        if material is None:
            if child.children and engine.KEY not in (child.ext or {}):
                apply(engine,scene,child,values)
            continue
        def paint(group):
            for face in group.mesh.faces:
                face.attrs['mat']=name
                face.attrs.update(material.face_attrs())
            for part in group.children:
                paint(part)
        paint(child)
