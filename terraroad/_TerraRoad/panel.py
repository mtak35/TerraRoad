# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Original TerraRoad sections and controls, rendered as a native Qt designer."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import re

from PySide6.QtCore import Qt,QPointF,QRectF,QTimer,QSettings
from PySide6.QtGui import QColor,QFont,QPainter,QPainterPath,QPen,QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,QComboBox,QDialog,QFileDialog,QFormLayout,QFrame,QGroupBox,QHBoxLayout,
    QLabel,QLineEdit,QMessageBox,QPushButton,QScrollArea,QSplitter,QTextBrowser,
    QToolButton,QTreeWidget,QTreeWidgetItem,QVBoxLayout,QWidget,QToolTip,QSizePolicy,
)

# These settings affect the static section / sweep now. Other original controls
# remain visible and persist, but must not suggest their builders exist yet.
SECTION_FIELDS=set('''width_mode lanes lane_width total_width thickness offset line_side line_edge mirror_section crown level_section surface_type gutter_width divided median_width median_type median_curb median_curb_height median_curb_width median_curb_depth median_curb_batter median_curb_type median_soil_drop green_depth shoulder_mode shoulder_width shoulder_slope shoulder_thickness service_side service_width service_slope service_thickness service_lanes service_divider_width service_divider_type service_divider_curb parking_side parking_angle parking_stall_width parking_stall_length parking_parallel_length parking_auto_width parking_width parking_slope parking_flat parking_thickness curb_type curb_side curb_height curb_width curb_depth curb_batter curb_extend_bottom curb_additional_depth curb_paint curb_block_length sidewalk walk_width walk_thickness walk_slope verge_width verge_side verge_green outer_belt_width center_line_count center_line_type center_line_width center_line_spacing center_dash_length center_gap_length lane_divider_type lane_divider_width divider_dash_length divider_gap_length edge_lines edge_line_at_parking edge_line_width edge_inset stripe_lift mark_lanes storm_channel channel_width channel_depth channel_wall grill_thickness corner_radius station_interval adjust_height'''.split())
PREVIEW_FIELDS=set('pole_placement pole_offset pole_height'.split())
FURNITURE_FIELDS=set('''pole_placement pole_spacing pole_stand pole_offset pole_height pole_arm pole_diameter pole_arms pole_type share_furniture signal_placement signal_side signal_height signal_arm signal_offset signal_setback crossing_placement crossing_spacing crossing_length crossing_bar_width crossing_bar_gap crossing_setback junction_mode crossing_type junction_radius junction_radius_auto radius_scale junction_gap island_radius circulatory_width level_section'''.split())
SECTION_FIELDS.update(FURNITURE_FIELDS)
SECTION_FIELDS.update('parking_marks parking_line_width parking_line_lift parking_line_setback'.split())
SITE_FIELDS=set('site_place site_north site_map_width map_source cesium_token cesium_asset'.split())
SECTION_FIELDS.update(SITE_FIELDS)
SECTION_FIELDS.update('box_junction box_line_width box_spacing box_inset mat_box junction_shoulders junction_edge_lines junction_poles median_junction_setback face_fit face_means'.split())
SECTION_FIELDS.update('bridge_type bridge_span bridge_headroom bridge_deck_width bridge_depth bridge_parapet_height bridge_parapet bridge_arches bridge_rise bridge_ramp widen_by widen_median widen_length widen_taper widen_side u_turn_length u_turn_marks'.split())
MATERIAL_EXTRA={'mat_crossing','mat_box'}
COLOR_FIELDS={'mat_pavement':'pavement','mat_gutter':'gutter','mat_shoulder':'shoulder',
              'mat_curb':'curb','mat_sidewalk':'sidewalk','mat_green':'green','mat_parking':'parking'}
MATERIAL_FIELDS=set(COLOR_FIELDS)|{'mat_stripe','mat_stripe_ctr','mat_edge','mat_curb_dark','mat_curb_light'}|MATERIAL_EXTRA


class CrossSection(QWidget):
    def __init__(self,section,parent=None):
        super().__init__(parent)
        self.section=section
        self.template=None
        self.error=''
        self.regions=[]
        self.colors={}
        self.unit_system='metric'
        self.format_length=lambda value:f'{value:.3f} m'
        self.translate=lambda text:text
        self.setMinimumSize(360,300)
        self.setMouseTracking(True)
    def set_template(self,template,error='',colors=None):
        self.template,self.error=template,error
        self.colors=colors or {}
        self.update()
    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(),QColor('#ffffff'))
        painter.setPen(QColor('#565c65'))
        painter.drawText(14,20,self.translate('Cross-section (vertical scale exaggerated)'))
        self.regions=[]
        t=self.template
        if t is None:
            painter.setPen(QColor('#b63d34'))
            painter.drawText(self.rect().adjusted(16,38,-16,-16),Qt.TextWordWrap,self.error or 'Set road dimensions to see its section.')
            return
        pts=[(x,z) for part in t.parts for x,z in part.points]
        if not pts:
            return
        min_x,max_x=min(x for x,z in pts),max(x for x,z in pts)
        min_z,max_z=min(z for x,z in pts),max(z for x,z in pts)
        w,h=self.width(),self.height()
        sx=(w-60)/max(max_x-min_x,0.01)
        sz=min(sx*6,(h-110)/max(max_z-min_z,0.1))
        ox=30-min_x*sx
        oz=h-70+min_z*sz
        xy=lambda x,z:QPointF(ox+x*sx,oz-z*sz)
        painter.setPen(QPen(QColor('#dedfd8'),1))
        painter.drawLine(xy(min_x,0),xy(max_x,0))
        for part in t.parts:
            polygon=QPolygonF([xy(x,z) for x,z in part.points])
            painter.setPen(QPen(QColor('#333a40'),0.8))
            painter.setBrush(QColor(self.colors.get(part.key,self.section.COLORS.get(part.key,'#999999'))))
            painter.drawPolygon(polygon)
            self.regions.append((polygon,part))
        for stripe in t.stripes:
            at=xy(stripe.offset,stripe.z)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor('#e7bc35') if stripe.edge else QColor('#ece6b3'))
            painter.drawRect(QRectF(at.x()-max(stripe.width*sx,2)/2,at.y()-2,max(stripe.width*sx,2),3))
        for side,(x,z) in t.pole_anchors.items():
            at=xy(x,z)
            top=at-QPointF(0,min(t.params['pole_height']*sz,h*0.32))
            reach=14 if side=='left' else -14
            painter.setPen(QPen(QColor('#414a45'),2))
            painter.drawLine(at,top)
            painter.drawLine(top,top+QPointF(reach,-3))
            painter.setBrush(QColor('#f1d25a'))
            painter.drawEllipse(top+QPointF(reach,-3),3,3)
        painter.setPen(QPen(QColor('#3a6ea5'),1,Qt.DashLine))
        painter.drawLine(QPointF(ox,30),QPointF(ox,h-42))
        painter.setPen(QColor('#3a6ea5'))
        painter.drawText(max(4,min(w-95,int(ox+5))),39,self.translate('drawn line'))
        y=h-43
        painter.setPen(QPen(QColor('#59616b'),1))
        painter.drawLine(QPointF(30,y),QPointF(w-30,y))
        for x in (30,w-30):
            painter.drawLine(QPointF(x,y-5),QPointF(x,y+5))
        caption=self.translate('Overall')+' '+self.format_length(max_x-min_x)
        painter.drawText(QRectF(30,y+6,w-60,22),Qt.AlignCenter,caption)
        painter.setPen(QColor('#757b81'))
        painter.drawText(14,h-7,'Hover a part for dimensions. Preview and build share the same profile.')
    def mouseMoveEvent(self,event):
        for polygon,part in reversed(self.regions):
            if polygon.containsPoint(event.position(),Qt.OddEvenFill):
                xs=[x for x,z in part.points]
                zs=[z for x,z in part.points]
                QToolTip.showText(event.globalPosition().toPoint(),
                    f'{self.translate(part.name)}\n{self.translate("Width")} {self.format_length(max(xs)-min(xs))}\n{self.translate("Height")} {self.format_length(max(zs)-min(zs))}',self)
                return
        QToolTip.hideText()


class Designer(QDialog):
    def showEvent(self,event):
        super().showEvent(event)
        self.repair_map_orientation()

    def repair_map_orientation(self):
        api=self.engine.support('site')
        saved=(self.app.document_data(default={}) or {}).get('site')
        repaired=api.corrected_maps(self.app.scene,saved)
        if repaired:
            self.site_command(api.ChangeSite(self.engine.KEY,repaired[0],repaired[1]))

    def __init__(self,app,engine,section,commit,preserve,export):
        super().__init__(app.window)
        self.app,self.engine,self.section=app,engine,section
        self.commit,self.preserve,self.export=commit,preserve,export
        self.fields={}
        self.groups=[]
        self.loading=False
        self.base=copy.deepcopy(section.DEFAULTS)
        self.base['_face_open_ends']=True
        self.last_values=None
        self.last_selection=None
        self.template=None
        self.callbacks={}
        self.active_only=False
        self.form_rows=[]
        self.settings=engine.support('units').settings()
        self.locale_api=engine.support('i18n')
        self.language=self.settings.value('language','en')
        if self.language not in dict(self.locale_api.LANGUAGES):
            self.language='en'
        self.unit_api=engine.support('units')
        self.unit_system=self.settings.value('system','metric')
        if self.unit_system not in ('metric','imperial'):
            self.unit_system='metric'
        self.setFont(QFont('Segoe UI',10))
        self.setWindowTitle(f'TerraRoad {engine.VERSION} — Road designer')
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose,False)
        self.resize(1380,900)
        screen=app.window.screen()
        if screen is not None:
            available=screen.availableGeometry()
            self.resize(min(1380,max(900,available.width()-60)),min(900,max(600,available.height()-70)))
        self.setStyleSheet('QGroupBox { font-weight:600; margin-top:10px; } QGroupBox::title { color:#b96e63; } QLineEdit,QComboBox { min-height:23px; } QLineEdit[portPending="true"],QComboBox[portPending="true"] { border:1px dashed #b78c53; } QCheckBox[portPending="true"] { color:#b78c53; }')
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.preview)
        outer=QVBoxLayout(self)
        heading=QHBoxLayout()
        title=QLabel('TERRAROAD  •  Road designer')
        title.setStyleSheet('font-size:17px;font-weight:700')
        heading.addWidget(title)
        heading.addStretch()
        self.selection_label=QLabel()
        heading.addWidget(self.selection_label)
        recheck=QPushButton('Recheck selection')
        recheck.clicked.connect(lambda:self.refresh_selection(load_settings=True))
        heading.addWidget(recheck)
        outer.addLayout(heading)
        preferences=QHBoxLayout()
        preferences.addWidget(QLabel('Measurement system'))
        self.system_combo=QComboBox()
        self.system_combo.addItem('Metric (m, m², m³)','metric')
        self.system_combo.addItem('Imperial (ft/in, ft², ft³)','imperial')
        self.system_combo.setCurrentIndex(self.system_combo.findData(self.unit_system))
        preferences.addWidget(self.system_combo)
        preferences.addStretch()
        preferences.addWidget(QLabel('Language'))
        self.language_combo=QComboBox()
        for code,name in self.locale_api.LANGUAGES:
            self.language_combo.addItem(name,code)
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language))
        preferences.addWidget(self.language_combo)
        outer.addLayout(preferences)
        self.language_note=QLabel('Technical notes may remain in English.')
        self.language_note.setWordWrap(True)
        outer.addWidget(self.language_note)
        scope=QLabel('Original sections and detailed cross-section port. Amber / dashed controls mark settings whose native builders are still being ported; these settings are retained.')
        scope.setWordWrap(True)
        scope.setStyleSheet('color:#c99765')
        outer.addWidget(scope)
        bar=QHBoxLayout()
        bar.addWidget(QLabel('Style'))
        self.library=QComboBox()
        for name in ('Presets','User','In Model'):
            self.library.addItem(name,name)
        self.styles=QComboBox()
        self.styles.setMinimumWidth(220)
        bar.addWidget(self.library)
        bar.addWidget(self.styles,1)
        for label,callback in [('Apply',self.load_style),('Save as…',self.save_style),('Delete',self.delete_style)]:
            button=QPushButton(label)
            button.clicked.connect(self.guard(callback))
            bar.addWidget(button)
        bar.addWidget(QLabel('Bare lengths'))
        self.units=QComboBox()
        for text,key in [('Metres','m'),('Feet','ft'),('Millimetres','mm'),('Inches','in')]:
            self.units.addItem(text,key)
        self.units.setCurrentIndex(1 if self.unit_system=='imperial' else 0)
        self.input_unit=self.units.currentData()
        self.units.currentIndexChanged.connect(self.bare_unit_changed)
        self.system_combo.currentIndexChanged.connect(self.change_system)
        bar.addWidget(self.units)
        outer.addLayout(bar)
        split=QSplitter(Qt.Horizontal)
        outer.addWidget(split,1)
        left=QWidget()
        left_layout=QVBoxLayout(left)
        left_layout.setContentsMargins(0,0,0,0)
        search_row=QHBoxLayout()
        search=QLineEdit()
        self.search=search
        search.setClearButtonEnabled(True)
        search.setPlaceholderText('Find a section or setting…')
        search.textChanged.connect(self.filter_sections)
        search_row.addWidget(search,1)
        show_all=QPushButton('Show all active options')
        show_all.clicked.connect(self.show_all_options)
        search_row.addWidget(show_all)
        expand=QPushButton('Expand all')
        expand.clicked.connect(lambda:self.fold_all(True))
        search_row.addWidget(expand)
        collapse=QPushButton('Collapse all')
        collapse.clicked.connect(lambda:self.fold_all(False))
        search_row.addWidget(collapse)
        left_layout.addLayout(search_row)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        left_layout.addWidget(scroll)
        form=QWidget()
        form_layout=QVBoxLayout(form)
        form_layout.setContentsMargins(2,0,7,10)
        scroll.setWidget(form)
        self._register_actions()
        definitions=copy.deepcopy(section.DATA['sections'])
        junction_extra=next(d for d in definitions if d['name']=='Junctions')
        for definition in definitions:
            if definition['name']=='Junctions':
                continue
            if definition['name']=='Edit a road':
                definition['name']='Draw / edit road'
            if definition['name']=='Junctions & roundabouts':
                definition['rows'].extend(junction_extra['rows'])
                definition['buttons'].extend(junction_extra['buttons'])
            self.add_section(form_layout,definition)
        form_layout.addStretch()
        split.addWidget(left)
        right=QWidget()
        right_layout=QVBoxLayout(right)
        self.diagram=CrossSection(section)
        self.diagram.format_length=self.fmt_length
        self.diagram.translate=self.tr_text
        right_layout.addWidget(self.diagram,2)
        self.dimensions=QLabel()
        self.dimensions.setWordWrap(True)
        right_layout.addWidget(self.dimensions)
        legend=QHBoxLayout()
        for key,label in [('pavement','Pavement'),('curb','Curb'),('parking','Parking'),('green','Planting'),('sidewalk','Walk')]:
            chip=QLabel('■ '+label)
            chip.setStyleSheet('color:'+section.COLORS[key])
            legend.addWidget(chip)
        right_layout.addLayout(legend)
        self.parts=QTreeWidget()
        self.parts.setHeaderLabels(['Section part','Width (m)','Area (m²)'])
        self.parts.setRootIsDecorated(False)
        self.parts.setMaximumHeight(210)
        right_layout.addWidget(self.parts)
        self.result=QTextBrowser()
        self.result.setMinimumHeight(100)
        self.result.setPlainText('Choose a saved style or change the original settings. The section updates live.\nSelect an open centerline in the model, then press Create.')
        right_layout.addWidget(self.result,1)
        split.addWidget(right)
        split.setSizes([540,790])
        footer=QHBoxLayout()
        for label,callback in [('Reset defaults',self.reset),('Load design settings',self.load_design),('Export take-off',export)]:
            button=QPushButton(label)
            button.clicked.connect(self.guard(callback))
            footer.addWidget(button)
        button=QPushButton('Draw a road')
        button.clicked.connect(self.guard(self.actions.draw))
        button.setToolTip('Draw centerline segments with native snapping and length input; each segment automatically builds the road.')
        footer.addWidget(button)
        footer.addStretch()
        outline=QPushButton('Preview outline')
        outline.setEnabled(False)
        outline.setToolTip('Original model-space outline tool — native action not yet ported. The cross-section preview above is live.')
        footer.addWidget(outline)
        attached=QPushButton('Update attached part only')
        attached.setEnabled(False)
        attached.setToolTip('Original connected-network updater — native action not yet ported.')
        footer.addWidget(attached)
        self.create_button=QPushButton('Create')
        self.create_button.setStyleSheet('background:#3a6ea5;color:white;padding:8px 22px;font-weight:600')
        self.create_button.clicked.connect(self.guard(self.build_road))
        footer.addWidget(self.create_button)
        close=QPushButton('Close')
        close.clicked.connect(self.close)
        footer.addWidget(close)
        outer.addLayout(footer)
        self.library.currentTextChanged.connect(self.fill_styles)
        self.styles.activated.connect(self.guard(self.load_style))
        self.fill_styles()
        saved=self.app.document_data(default={}) or {}
        self.apply(saved.get('values',{}))
        picked=saved.get('values',{})
        if picked.get('style_library') in ('Presets','User','In Model'):
            self.library.setCurrentText(picked['style_library'])
            self.styles.setCurrentText(picked.get('style_name_picked',''))
        self.poll=QTimer(self)
        self.poll.setInterval(650)
        self.poll.timeout.connect(self.poll_selection)
        self.poll.start()
        for dynamic in (self.selection_label,self.dimensions):
            dynamic.setProperty('noTranslate',True)
        self.language_combo.currentIndexChanged.connect(self.change_language)
        self.retranslate()

    def guard(self,callback):
        def run(*args):
            try:
                return callback()
            except Exception as exc:
                self.result.setPlainText(str(exc))
                QMessageBox.warning(self,'TerraRoad',str(exc))
        return run

    def _register_actions(self):
        self.actions=self.engine.support('actions').Editor(self)
        self.callbacks={
            'editRoad':self.load_selected,'saveRoad':self.build_road,'roadFromLines':self.build_new,
            'clearPick':self.clear_pick,'renameRoad':self.rename_road,
            'saveReport':self.save_report,'rebuildAll':self.rebuild_all,
            'editDesign':self.load_selected,
            'roadFromFace':lambda:self.convert_faces('road'),
            'junctionFromFace':lambda:self.convert_faces('junction'),
            'changeFaceRoad':self.build_road,'repairFaceRoads':self.repair_face,
            'swapFaceKind':self.swap_face_kind,'resizeFaceRoad':self.resize_face,
            'deleteRoad':self.delete_road,
            'setSite':self.place_map,'placeMap':self.place_map,'swapMap':self.swap_map,
            'traceMap':lambda:self.start_site_job('trace'),
            'traceMapEdges':lambda:self.start_site_job('edges'),
            'streetView':self.street_view,'cropMap':self.crop_map,
            'clearRoad':self.actions.restore,'branchRoad':self.actions.branch,
            'branchFromLines':self.build_new,'stretchRoad':self.actions.move_point,
            'mirrorRoad':self.actions.mirror_copy,'breakIntoComponents':self.actions.components,
            'lightenModel':self.actions.lighten,'connectFaceRoads':self.actions.connect,
            'splitFaceRoad':self.actions.split,
            'addLaneArrow':lambda:self.actions.face_mark('arrow'),
            'addFaceCrossing':lambda:self.actions.face_mark('crossing'),
            'clearFaceMarks':self.actions.clear_marks,
            'setFaceSpine':self.actions.spine,'clearFaceSpine':lambda:self.actions.spine(True),
            'pickBridge':lambda:self.actions.feature('bridge'),
            'addBridge':lambda:self.actions.feature('bridge',True),
            'addGrade':lambda:self.actions.feature('grade'),
            'addUturn':lambda:self.actions.feature('uturn'),
            'addCrossing':lambda:self.actions.feature('crossing'),
            'addWidening':lambda:self.actions.feature('widen'),
        }

    def add_section(self,parent,definition):
        box=QGroupBox()
        box_layout=QVBoxLayout(box)
        header=QToolButton()
        header.setText(definition['name'])
        header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        header.setCheckable(True)
        opened=False
        header.setChecked(opened)
        header.setArrowType(Qt.DownArrow if opened else Qt.RightArrow)
        header.setStyleSheet('font-weight:700;font-size:13px;color:#cf8b7b;border:0;text-align:left')
        box_layout.addWidget(header)
        body=QWidget()
        body_layout=QVBoxLayout(body)
        body_layout.setContentsMargins(0,0,0,0)
        form=QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        body_layout.addLayout(form)
        if definition['name']=='Roadway':
            mode=QComboBox()
            for text,key in [('Lanes','lanes'),('Carriageway width','total'),('Overall width','overall')]:
                mode.addItem(text,key)
            mode.currentIndexChanged.connect(self.queue)
            self.fields['width_mode']=mode
            form.addRow('Width mode',mode)
        if definition['name']=='Convert face into road':
            mode=QCheckBox('Open road ends (keep curbs and sidewalks along the sides)')
            mode.setChecked(True)
            self.fields['_face_open_ends']=mode
            form.addRow(mode)
        for row in definition['rows']:
            fields=QWidget()
            field_layout=QHBoxLayout(fields)
            field_layout.setContentsMargins(0,0,0,0)
            check_only=len(row['fields'])==1 and row['fields'][0]['type']=='checkbox'
            for field in row['fields']:
                key=field['id']
                if key=='road_pick':
                    widget=QComboBox()
                    widget.currentIndexChanged.connect(self.road_picked)
                elif field['type']=='checkbox':
                    widget=QCheckBox(field['label'] if check_only else '')
                    widget.setProperty('trKeys',[key])
                    widget.toggled.connect(self.queue)
                elif field['type']=='select':
                    widget=QComboBox()
                    widget.setMinimumContentsLength(9)
                    widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                    widget.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
                    for value,text in field['options']:
                        widget.addItem(text,value)
                    widget.currentIndexChanged.connect(self.queue)
                else:
                    widget=QLineEdit()
                    if field['type']=='password':
                        widget.setEchoMode(QLineEdit.Password)
                    widget.setPlaceholderText(field['placeholder'])
                    widget.textEdited.connect(self.queue)
                widget.setObjectName('tr_'+key)
                status=('Affects the cross-section and road geometry.' if key in SECTION_FIELDS or key in MATERIAL_FIELDS
                        else 'Shown in the section preview; longitudinal placement is not yet ported.' if key in PREVIEW_FIELDS
                        else 'Original setting retained. Its native builder is not yet ported.')
                if key in SITE_FIELDS:
                    status='Used by Site & map actions. Map requests run in the background and can also use a local image.'
                widget.setToolTip(field['label']+'\n'+field['title']+'\n'+status)
                if key not in SECTION_FIELDS and key not in MATERIAL_FIELDS and key not in ('road_pick','road_name'):
                    widget.setProperty('portPending',True)
                self.fields[key]=widget
                field_layout.addWidget(widget,1)
            if row['suffix']:
                field_layout.addWidget(QLabel(row['suffix']))
            if check_only:
                form.addRow(fields)
                label=None
            else:
                label=QLabel(row['label'])
                label.setProperty('trKeys',[f['id'] for f in row['fields']])
                label.setWordWrap(True)
                label.setMaximumWidth(200)
                form.addRow(label,fields)
            self.form_rows.append((fields,label,any(f['id'] in SECTION_FIELDS or f['id'] in MATERIAL_FIELDS or f['id'] in ('road_pick','road_name') for f in row['fields'])))
        for action in definition['buttons']:
            label=action['label']
            match=re.search(r'TR\.(\w+)\(',action['handler'])
            key=match[1] if match else ''
            if key=='streetView':
                label='Street view at the selected point'
            button=QPushButton(label)
            button.setObjectName('tr_action_'+key)
            button.setToolTip(action['title'])
            if key in self.callbacks:
                button.clicked.connect(self.guard(self.callbacks[key]))
            else:
                button.setEnabled(False)
                button.setToolTip((action['title']+'\nNative action not yet ported.').strip())
            body_layout.addWidget(button)
        if definition['name']=='Junctions & roundabouts':
            build_network=QPushButton('Build junctions / roundabouts from lines or roads')
            build_network.clicked.connect(self.guard(self.actions.network))
            body_layout.addWidget(build_network)
        if definition['name']=='Site & map':
            manual=QPushButton('Trace roads manually on the map…')
            def start_trace():
                tools=self.engine.support('tools')
                tools.start(self,tools.ManualTrace(self))
            manual.clicked.connect(self.guard(start_trace))
            body_layout.addWidget(manual)
            local_map=QPushButton('Choose a local map picture…')
            local_map.clicked.connect(self.guard(self.local_map))
            body_layout.addWidget(local_map)
        if definition['help']:
            help_button=QToolButton()
            help_button.setText('Original help and notes')
            help_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            help_button.setCheckable(True)
            help_button.setArrowType(Qt.RightArrow)
            notes=QLabel('\n\n'.join(definition['help']))
            notes.setWordWrap(True)
            notes.setTextFormat(Qt.PlainText)
            notes.setStyleSheet('font-weight:400;color:#999f9e;font-size:11px')
            notes.setVisible(False)
            help_button.toggled.connect(notes.setVisible)
            help_button.toggled.connect(lambda opened,b=help_button:b.setArrowType(Qt.DownArrow if opened else Qt.RightArrow))
            body_layout.addWidget(help_button)
            body_layout.addWidget(notes)
        body.setVisible(opened)
        header.toggled.connect(body.setVisible)
        header.toggled.connect(lambda checked,b=header:b.setArrowType(Qt.DownArrow if checked else Qt.RightArrow))
        header.toggled.connect(lambda checked,name=definition['name']:self.settings.setValue('sections/'+name,checked))
        box_layout.addWidget(body)
        parent.addWidget(box)
        self.groups.append((box,header,definition))

    def collect(self):
        values=copy.deepcopy(self.base)
        for key,widget in self.fields.items():
            if key in ('road_pick','road_name'):
                continue
            if isinstance(widget,QCheckBox):
                values[key]=widget.isChecked()
            elif isinstance(widget,QComboBox):
                values[key]=widget.currentData() if widget.currentData() is not None else widget.currentText()
            else:
                values[key]=widget.text()
        values['_length_unit']=self.units.currentData()
        values['_unit_system']=self.unit_system
        values['style_library']=self.library.currentData()
        values['style_name_picked']=self.styles.currentText()
        return values

    def apply(self,values):
        self.loading=True
        self.base={**self.base,**values}
        self.base.setdefault('_face_open_ends',True)
        original_unit=self.base.get('_length_unit','m')
        for key in self.section.DATA['lengths']:
            value=self.base.get(key)
            if value is not None and str(value).strip():
                self.base[key]=self.unit_api.input_length(self.section.length(value,original_unit),self.unit_system)
        self.base['_length_unit']='ft' if self.unit_system=='imperial' else 'm'
        for key,widget in self.fields.items():
            if key in ('road_pick','road_name'):
                continue
            value=self.base.get(key,'')
            if isinstance(widget,QCheckBox):
                widget.setChecked(self.section.truth(value))
            elif isinstance(widget,QComboBox):
                if key.startswith('mat_'):
                    widget.clear()
                    widget.addItem('(default colour)','')
                    for name in sorted(self.app.scene.materials):
                        widget.addItem(name,name)
                index=widget.findData(str(value))
                if index<0 and value not in (None,''):
                    widget.addItem(str(value),str(value))
                    index=widget.count()-1
                widget.setCurrentIndex(max(0,index))
            else:
                widget.setText(str(value))
        self.units.setCurrentIndex(max(0,self.units.findData(self.base.get('_length_unit','m'))))
        self.input_unit=self.units.currentData()
        self.loading=False
        self.preview()

    def queue(self,*args):
        if not self.loading:
            self.timer.start(140)

    def preview(self):
        try:
            values=self.collect()
            self.template=self.section.build(self.section.parameters(values))
            colors={}
            for field,key in COLOR_FIELDS.items():
                material=self.app.scene.materials.get(values.get(field))
                color=getattr(material,'color',None)
                if color:
                    colors[key]=QColor.fromRgbF(*color[:3]).name()
            self.diagram.set_template(self.template,colors=colors)
            p=self.template.params
            cw=self.section.carriageway_width(p)*(2 if self.section.divided(p) else 1)
            overall=self.template.right_extent-self.template.left_extent
            self.dimensions.setText(f'{self.tr_text("Carriageway")}: {self.fmt_length(cw)}    {self.tr_text("Overall")}: {self.fmt_length(overall)}\n{self.tr_text("Thickness")}: {self.fmt_length(p["thickness"])}    {self.tr_text("Section part")}: {len(self.template.parts)}    {self.tr_text("Line")}: {len(self.template.stripes)}')
            area_unit='ft²' if self.unit_system=='imperial' else 'm²'
            self.parts.setHeaderLabels([self.tr_text('Section part'),self.tr_text('Width')+(' (ft/in)' if self.unit_system=='imperial' else ' (m)'),self.tr_text('Area')+f' ({area_unit})'])
            self.parts.clear()
            for part in self.template.parts:
                width=max(x for x,z in part.points)-min(x for x,z in part.points)
                area=self.engine._area(part.points)
                self.parts.addTopLevelItem(QTreeWidgetItem([self.tr_text(part.name),self.fmt_length(width),f'{self.unit_api.area(area,self.unit_system)[0]:.4f}']))
            self.parts.resizeColumnToContents(0)
            if self.template.warnings:
                self.result.setPlainText('\n'.join(self.template.warnings))
        except (ValueError,KeyError,TypeError,ZeroDivisionError) as exc:
            self.template=None
            self.diagram.set_template(None,str(exc))
            self.dimensions.setText(str(exc))

    def filter_sections(self,text):
        self.set_active_view(False)
        text=text.strip().casefold()
        for box,header,definition in self.groups:
            haystack=definition['name']+' '+header.text()+' '+' '.join(r['label']+' '+' '.join(f['id'] for f in r['fields']) for r in definition['rows'])
            match=not text or text in haystack.casefold()
            box.setVisible(match)
            if text and match:
                header.setChecked(True)

    def fold_all(self,open_):
        for box,header,definition in self.groups:
            header.setChecked(open_)

    def show_all_options(self):
        self.search.clear()
        self.filter_sections('')
        self.set_active_view(True)
        self.fold_all(True)

    def set_active_view(self,active):
        self.active_only=active
        for fields,label,implemented in self.form_rows:
            fields.setVisible(not active or implemented)
            if label is not None:
                label.setVisible(not active or implemented)
        for box,header,definition in self.groups:
            if active:
                live=any(f['id'] in SECTION_FIELDS or f['id'] in MATERIAL_FIELDS or f['id'] in ('road_pick','road_name') for row in definition['rows'] for f in row['fields'])
                live=live or any(b.isEnabled() for b in box.findChildren(QPushButton))
                box.setVisible(live)
            for widget in box.findChildren(QWidget):
                if widget.property('portPending'):
                    widget.setVisible(not active)
                elif isinstance(widget,QPushButton) and not widget.isEnabled():
                    widget.setVisible(not active)
        for widget in self.findChildren(QPushButton):
            if not widget.isEnabled():
                widget.setVisible(not active)

    def user_styles(self):
        file=Path(__file__).with_name('user_styles.json')
        if file.exists():
            return json.loads(file.read_text(encoding='utf-8'))
        return copy.deepcopy(self.section.DATA['user_styles'])

    def libraries(self):
        return {'Presets':self.section.DATA['presets'],'User':self.user_styles(),
                'In Model':(self.app.document_data(default={}) or {}).get('styles',{})}

    def fill_styles(self,*args):
        keep=self.styles.currentText()
        self.styles.clear()
        self.styles.addItems(sorted(self.libraries()[self.library.currentData()]))
        index=self.styles.findText(keep)
        if index>=0:
            self.styles.setCurrentIndex(index)

    def load_style(self):
        name=self.styles.currentText()
        if not name:
            return
        raw=self.libraries()[self.library.currentData()][name]
        # Styles are overlays on original defaults, as in Styles.load.
        self.base=copy.deepcopy(self.section.DEFAULTS)
        self.apply(raw)
        self.result.setPlainText(f'Loaded {self.library.currentText()}: {name}.\nThe visible section and generated road use these fields.')

    def save_style(self):
        from PySide6.QtWidgets import QInputDialog
        name,ok=QInputDialog.getText(self,'Save TerraRoad style','Style name',text=self.styles.currentText())
        if not ok or not name.strip():
            return
        library=self.library.currentData()
        if library=='Presets':
            library='User'
        values=self.collect()
        styles=self.libraries()[library]
        if name in styles:
            if QMessageBox.question(self,'TerraRoad','Replace the existing style '+name+'?')!=QMessageBox.Yes:
                return
        styles[name.strip()]=values
        self.write_library(library,styles)
        self.library.setCurrentIndex(self.library.findData(library))
        self.fill_styles()
        self.styles.setCurrentText(name.strip())
        self.result.setPlainText(f'Saved {library}: {name.strip()}')

    def write_library(self,library,styles):
        if library=='In Model':
            data=self.app.document_data(default={}) or {}
            data['styles']=styles
            self.app.set_document_data(data)
        else:
            file=Path(__file__).with_name('user_styles.json')
            temp=file.with_suffix('.json.tmp')
            temp.write_text(json.dumps(styles,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(file)

    def delete_style(self):
        library=self.library.currentData()
        name=self.styles.currentText()
        if library=='Presets':
            raise ValueError('Shipped presets are read-only. Save an editable copy in User or In Model.')
        if not name:
            return
        if QMessageBox.question(self,'TerraRoad','Delete saved style '+name+'?')!=QMessageBox.Yes:
            return
        styles=self.libraries()[library]
        styles.pop(name,None)
        self.write_library(library,styles)
        self.fill_styles()

    def roads(self):
        return [g for g in self.app.scene.groups if self.engine.KEY in (g.ext or {})]

    def selected(self):
        pick=self.fields.get('road_pick')
        uid=pick.currentData() if pick else None
        return next((g for g in self.roads() if g.uid==uid),None)

    def signature(self):
        return (id(self.app.scene),tuple(sorted(id(g) for g in self.app.scene.selection)))

    def poll_selection(self):
        if not self.isVisible():
            return
        if self.signature()!=self.last_selection:
            self.refresh_selection(load_settings=True)

    def refresh_selection(self,load_settings=False):
        from core.mesh import Edge,Face
        self.last_selection=self.signature()
        selected=self.app.scene.selection
        roads=self.roads()
        clicked=next((g for g in roads if g in selected),None)
        pick=self.fields['road_pick']
        has_source=any(isinstance(item,(Edge,Face)) or self.engine.KEY+'_trace' in (getattr(item,'ext',None) or {}) for item in selected)
        keep=clicked.uid if clicked else (None if has_source else pick.currentData() if self.selected() else None)
        pick.blockSignals(True)
        pick.clear()
        pick.addItem('— no road selected —',None)
        for road in roads:
            pick.addItem(road.name,road.uid)
        pick.setCurrentIndex(max(0,pick.findData(keep)))
        pick.blockSignals(False)
        count=sum(isinstance(g,Edge) for g in selected)
        face_count=sum(isinstance(g,Face) for g in selected)
        self.selection_label.setText(f'{count} edges  •  {face_count} faces selected  •  {len(roads)} roads')
        self.create_button.setText(self.tr_text('Update selected road' if self.selected() else 'Convert to a road' if face_count else 'Create'))
        self.fields['road_name'].setText(self.selected().name if self.selected() else '')
        if load_settings and clicked:
            self.load_selected()

    def road_picked(self,*args):
        road=self.selected()
        self.fields['road_name'].setText(road.name if road else '')
        self.create_button.setText(self.tr_text('Update selected road' if road else 'Create'))
        if road:
            self.load_selected()

    def load_selected(self):
        road=self.selected()
        if road is None:
            return
        data=road.ext[self.engine.KEY]
        if 'values' in data:
            self.base=copy.deepcopy(self.section.DEFAULTS)
            self.apply(data['values'])
        else:
            self.apply(self.legacy_values(data['parameters']))
        self.fields['road_name'].setText(road.name)

    def legacy_values(self,p):
        out=copy.deepcopy(self.section.DEFAULTS)
        mapping={'lanes':'lanes','lane_width':'lane_width','thickness':'thickness','crown':'crown',
                 'curb_width':'curb_width','curb_height':'curb_height','verge':'verge_width',
                 'sidewalk':'walk_width','sidewalk_thickness':'walk_thickness','radius':'corner_radius',
                 'station_interval':'station_interval','offset':'offset','elevation':'adjust_height'}
        for src,dst in mapping.items():
            value=p[src]
            out[dst]=str(value*100) if src=='crown' else str(value) if src=='lanes' else f'{value}m'
        out['level_section']=False
        out['divided']=p['median']>0
        out['median_width']=f'{p["median"]}m'
        out['shoulder_mode']='fixed' if p['shoulder']>0 else 'none'
        out['shoulder_width']=f'{p["shoulder"]}m'
        out['mark_lanes']='auto' if p['markings'] else 'never'
        out['curb_paint']=False
        return out

    def clear_pick(self):
        self.fields['road_pick'].setCurrentIndex(0)

    def reset(self):
        self.base=copy.deepcopy(self.section.DEFAULTS)
        self.apply({})

    def load_design(self):
        self.base=copy.deepcopy(self.section.DEFAULTS)
        self.apply((self.app.document_data(default={}) or {}).get('values',{}))

    def build_new(self):
        self.clear_pick()
        self.build_road()

    def selected_points(self):
        from core.mesh import Edge
        edges=[e for e in self.app.scene.selection if isinstance(e,Edge)]
        return self.engine.ordered_path([(e.a.toTuple(),e.b.toTuple()) for e in edges])

    def build_road(self):
        if self.app.scene.edit_group is not None:
            raise ValueError('Exit group editing before building a road.')
        values=self.collect()
        old=self.selected()
        if old is None:
            from core.mesh import Face
            if any(isinstance(item,Face) for item in self.app.scene.selection):
                return self.convert_faces('road')
        if old and old.ext[self.engine.KEY].get('face_road'):
            return self.update_face(old,values)
        name=self.fields['road_name'].text().strip() or (old.name if old else f'TerraRoad {len(self.roads())+1}')
        self.result.setPlainText('Building the visible section…')
        if old:
            data=old.ext[self.engine.KEY]
            road=self.engine.support('model').rebuild(self.engine,self.section,data,values,name)
        else:
            from core.mesh import Edge
            edges=[e for e in self.app.scene.selection if isinstance(e,Edge)]
            for group in self.app.scene.selection:
                if self.engine.KEY+'_trace' in (getattr(group,'ext',None) or {}):
                    edges.extend(group.mesh.edges)
            segments=[(e.a.toTuple(),e.b.toTuple()) for e in edges]
            road=self.engine.support('network').make_network(self.engine,self.section,segments,values,name)
        if old:
            self.preserve(road,old)
        # Material identity uses the host's existing registry and baked color.
        self.apply_materials(road,values)
        self.commit(road,old)
        self.last_values=values
        self.refresh_selection()
        # Parameters on the road are the saved truth; do not add a second undo
        # step just to save panel defaults in document_data here.
        warnings=self.remaining_features(values)
        self.result.setPlainText(f'Built {name}: {self.fmt_length(road.ext[self.engine.KEY]["centerline_length_m"])}, {len(road.children)} parts.\nThe road uses the section shown above.\n\n'+warnings)

    def apply_materials(self,road,values):
        self.engine.support('materials').apply(self.engine,self.app.scene,road,values)

    def remaining_features(self,values):
        return ('Native drawing, selected-road point/mirror edits, local width/level changes, U-turns, crossings and deck bridges are available. Feature dimensions must fit inside the chosen road.\n'
                'Junction networks require level cross-sections and zero lateral offset. Terrain cut/fill, automatic bridge crossings, arches, studs, curved face spines, adaptive face lane widths and advanced roundabout entries are still being ported.\n'
                'Rebuilding replaces manual component edits. Quantities are design estimates; local width changes and manual scaling require a measured take-off.')

    def outline(self):
        self.preview()
        if self.template is None:
            raise ValueError(self.dimensions.text())
        self.result.setPlainText('The live section preview shows the current outline. A model-space outline tool has not yet been ported.')

    def rename_road(self):
        road=self.selected()
        if road is None:
            return
        # Rebuild so the new name participates in the same reversible command.
        self.build_road()

    def delete_road(self):
        from core.history import DeleteGroupCommand
        road=self.selected()
        if road is None:
            raise ValueError('Select one TerraRoad road first.')
        self.app.viewport.history.execute(DeleteGroupCommand(road))
        if self.app.viewport.history.last_error:
            raise RuntimeError(self.app.viewport.history.last_error)
        self.app.viewport.notify_scene_changed()
        self.app.viewport.update()
        self.refresh_selection()

    def rebuild_all(self):
        roads=self.roads()
        pairs=[]
        for old in roads:
            data=old.ext[self.engine.KEY]
            values=data.get('values') or self.legacy_values(data['parameters'])
            new=self.engine.support('model').rebuild(self.engine,self.section,data,values,old.name)
            self.preserve(new,old)
            self.apply_materials(new,values)
            pairs.append((old,new))
        if not pairs:
            return
        self.actions.batch(pairs)
        self.result.setPlainText(f'Rebuilt {len(pairs)} roads using their own saved settings.\n'+self.remaining_features({}))

    def save_report(self):
        target,_=QFileDialog.getSaveFileName(self,'Save TerraRoad report','TerraRoad-report.json','JSON (*.json)')
        if target:
            Path(target).write_text(json.dumps({'version':self.engine.VERSION,'values':self.collect(),
                'roads':[{ 'name':g.name,'data':g.ext[self.engine.KEY]} for g in self.roads()]},indent=2),encoding='utf-8')

    def site_values(self):
        api=self.engine.support('site')
        values=self.collect()
        saved=(self.app.document_data(default={}) or {}).get('site',{})
        return api.site_from_values(self.section,values,self.app.scene,saved),values

    def site_command(self,command):
        self.app.viewport.history.execute(command)
        if self.app.viewport.history.last_error:
            raise RuntimeError(self.app.viewport.history.last_error)
        if hasattr(self.app.viewport,'reset_texture_cache'):
            self.app.viewport.reset_texture_cache()
        self.app.viewport.notify_scene_changed()
        self.app.viewport.update()

    def place_map(self):
        self.start_site_job('map')

    def swap_map(self):
        widget=self.fields['map_source']
        widget.setCurrentIndex(widget.findData('osm' if widget.currentData()=='satellite' else 'satellite'))
        self.place_map()

    def start_site_job(self,operation):
        self.repair_map_orientation()
        if getattr(self,'map_job',None) is not None and self.map_job.isRunning():
            raise ValueError('A map request is already running. Wait for it to finish.')
        api=self.engine.support('site')
        if operation=='map':
            site,values=self.site_values()
        else:
            values=self.collect()
            site=api.trace_site(self.app.scene,(self.app.document_data(default={}) or {}).get('site'))
        self.map_context=(self.app.scene,site,operation)
        self.map_job=api.Job('map' if operation=='map' else 'trace',site,values,self)
        self.map_job.result_ready.connect(self.site_job_ready)
        self.map_job.failed.connect(self.site_job_failed)
        # A window cannot destroy a running QThread during shutdown.
        from PySide6.QtWidgets import QApplication
        def finish_job():
            self.map_job.requestInterruption()
            self.map_job.wait()
        QApplication.instance().aboutToQuit.connect(finish_job)
        self.result.setPlainText('Fetching the requested map patch…' if operation=='map' else 'Fetching OpenStreetMap road data…')
        self.map_job.start()

    def site_job_failed(self,message):
        self.result.setPlainText(message+'\nYou can also choose a local map picture under Site & map.')

    def site_job_ready(self,result):
        scene,site,operation=self.map_context
        if self.app.scene is not scene:
            self.result.setPlainText('Map request finished after the document changed; the result was not inserted.')
            return
        api=self.engine.support('site')
        try:
            if operation=='map':
                image=api.image_plane(result)
                site={**site,'map_reference':api.map_frame(image),'map_uv_version':1}
                command=api.ChangeSite(self.engine.KEY,site,[image])
                message=f'Map placed beneath the design: {self.fmt_length(image.width())} across.\n'+result['credit']
            else:
                groups=api.traced_groups(self.engine,result,operation=='edges')
                command=api.ChangeSite(self.engine.KEY,site,group=groups)
                message=f'Imported {len(result)} mapped roads as individually selectable lines.\nClick the road on the map; Shift adds roads, Enter returns to TerraRoad.\nOSM centerlines can differ from imagery. Estimated edges are not surveyed boundaries.'
            self.site_command(command)
            self.result.setPlainText(message)
            if operation!='map':
                tools=self.engine.support('tools')
                tools.start(self,tools.TraceSelect(self,groups,max(1.,min(site['width']/200,10.))))
        except Exception as exc:
            self.site_job_failed(str(exc))

    def local_map(self):
        from PySide6.QtGui import QImage,QVector3D
        api=self.engine.support('site')
        site,values=self.site_values()
        target,_=QFileDialog.getOpenFileName(self,'Choose map picture','','Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp)')
        if not target:
            return
        image=QImage(target)
        if image.isNull():
            raise ValueError('The selected map image could not be read.')
        width=site['width']
        height=width*image.height()/image.width()
        center=QVector3D(*site['anchor'])
        theta=math.radians(site['north'])
        from core.image_plane import ImagePlane
        u=QVector3D(width*math.cos(theta),width*math.sin(theta),0)
        v=QVector3D(-height*math.sin(theta),height*math.cos(theta),0)
        origin=center-(u+v)/2-QVector3D(0,0,.05)
        plane=ImagePlane(target,origin,u,v,height/width,api.PREFIX+'local reference',layer=api.MAP_LAYER,locked=True)
        site['map_reference']=api.map_frame(plane)
        site['map_uv_version']=1
        self.site_command(api.ChangeSite(self.engine.KEY,site,[plane]))
        self.result.setPlainText('Local map picture placed under the design, centered on the site anchor. Map width and north rotation determine its scale and orientation.')

    def crop_map(self,points=None):
        from PySide6.QtGui import QImage
        from core.mesh import Face,Edge
        from core.image_plane import ImagePlane
        import uuid
        api=self.engine.support('site')
        self.repair_map_orientation()
        saved=copy.deepcopy((self.app.document_data(default={}) or {}).get('site') or self.site_values()[0])
        maps=[image for image in self.app.scene.image_planes if image.name.startswith(api.PREFIX)]
        if not maps:
            raise ValueError('Place a TerraRoad map first.')
        if points is None:
            points=[]
            for item in self.app.scene.selection:
                if isinstance(item,Face):
                    points.extend(item.vertices)
                elif isinstance(item,Edge):
                    points.extend([item.a,item.b])
        if len(points)<2:
            return self.actions.pick('Click two opposite corners of the map crop',2,self.crop_map)
        cropped=[]
        for plane in maps:
            uv=[plane.project(point) for point in points]
            a,b=max(0,min(u for u,v in uv)),max(0,min(v for u,v in uv))
            c,d=min(1,max(u for u,v in uv)),min(1,max(v for u,v in uv))
            if c<=a or d<=b:
                continue
            image=QImage(plane.path)
            if image.isNull():
                raise ValueError('The stored map image could not be read.')
            x0,y0=int(a*image.width()),int((1-d)*image.height())
            x1,y1=math.ceil(c*image.width()),math.ceil((1-b)*image.height())
            a,b,c,d=x0/image.width(),1-y1/image.height(),x1/image.width(),1-y0/image.height()
            reference=api.cropped_reference(saved.get('map_reference') or api.map_frame(plane),a,b,c,d)
            image=image.copy(x0,y0,x1-x0,y1-y0)
            api.stamp(image,plane.name[len(api.PREFIX):])
            path=api.cache_dir()/('crop-'+uuid.uuid4().hex+'.png')
            image.save(str(path),'PNG')
            u,v=plane.u*(c-a),plane.v*(d-b)
            cropped.append(ImagePlane(str(path),plane.origin+plane.u*a+plane.v*b,u,v,v.length()/u.length(),plane.name,layer=plane.layer,locked=True))
        if not cropped:
            raise ValueError('The selected crop window does not overlap the map.')
        site=(self.app.document_data(default={}) or {}).get('site')
        if site is None:
            site,_=self.site_values()
        site=copy.deepcopy(site)
        from PySide6.QtGui import QVector3D
        ro,ru,rv=(QVector3D(*reference[k]) for k in ('origin','u','v'))
        corners=[api.earth_point((ro+ru*u+rv*v).toTuple(),site)
                 for u,v in ((0,0),(0,1),(1,0),(1,1))]
        site['crop_bbox']=[min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners)]
        site['map_reference']=reference
        site['map_uv_version']=1
        site.pop('_trace_placement',None)
        self.site_command(api.ChangeSite(self.engine.KEY,site,cropped))
        self.result.setPlainText('Map cropped to the selected window. Undo restores the complete map.')

    def street_view(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from core.mesh import Face,Edge,Vertex
        api=self.engine.support('site')
        site,_=self.site_values()
        points=[]
        for item in self.app.scene.selection:
            if isinstance(item,Vertex):
                points.append(item.position.toTuple())
            elif isinstance(item,Edge):
                points.extend([item.a.toTuple(),item.b.toTuple()])
            elif isinstance(item,Face):
                points.extend(pt.toTuple() for pt in item.vertices)
        if not points:
            raise ValueError('Select a point, edge or face at the place to view, then press Street view.')
        point=tuple(sum(pt[i] for pt in points)/len(points) for i in range(3))
        lat,lon=api.earth_point(point,site)
        QDesktopServices.openUrl(QUrl(f'https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.8f},{lon:.8f}'))
        self.result.setPlainText('Opened Street View at the selected position. Imagery availability depends on the location.')

    def convert_faces(self,kind='road'):
        from core.mesh import Face
        if self.app.scene.edit_group is not None:
            raise ValueError('Exit group editing and select a loose face before converting.')
        selected=[f for f in self.app.scene.selection if isinstance(f,Face) and f in self.app.scene.mesh.faces]
        if not selected:
            raise ValueError('Select one or more ground faces in the model first, then choose Convert to a road or Convert to a junction.')
        values=self.collect()
        api=self.engine.support('faces')
        # Build all results before changing the source mesh: a bad face does
        # not leave a partially converted selection behind.
        groups=[api.from_face(self.engine,self.section,face,values,
                ('TerraRoad junction' if kind=='junction' else 'TerraRoad face road')+f' {len(self.roads())+i+1}',kind)
                for i,face in enumerate(selected)]
        for group in groups:
            self.apply_materials(group,values)
        self.app.viewport.history.execute(api.ConvertFaces(selected,groups,self.engine.KEY,values))
        if self.app.viewport.history.last_error:
            raise RuntimeError(self.app.viewport.history.last_error)
        self.app.viewport.notify_scene_changed()
        self.app.viewport.update()
        self.refresh_selection(load_settings=True)
        self.result.setPlainText(f'Converted {len(groups)} selected face(s) to '+kind+'.\nOne undo step restores the original faces.\n'+
            '\n'.join(groups[0].ext[self.engine.KEY]['warnings']))

    def update_face(self,old,values,kind=None):
        data=old.ext[self.engine.KEY]
        new=(self.engine.support('model').rebuild(self.engine,self.section,data,values,old.name)
             if data.get('network_source') and kind is None else
             self.engine.support('faces').from_loops(self.engine,self.section,data['loops'],values,old.name,kind or data.get('kind','road')))
        self.preserve(new,old)
        self.apply_materials(new,values)
        self.commit(new,old)
        self.refresh_selection()
        self.result.setPlainText('Updated the selected face road.\n'+'\n'.join(new.ext[self.engine.KEY]['warnings']))

    def repair_face(self):
        old=self.selected()
        if old is None or not old.ext[self.engine.KEY].get('face_road'):
            raise ValueError('Select a TerraRoad face road or junction first.')
        self.update_face(old,old.ext[self.engine.KEY]['values'])

    def swap_face_kind(self):
        old=self.selected()
        if old is None or not old.ext[self.engine.KEY].get('face_road'):
            raise ValueError('Select a TerraRoad face road or junction first.')
        data=old.ext[self.engine.KEY]
        self.update_face(old,data['values'],'road' if data.get('kind')=='junction' else 'junction')

    def resize_face(self):
        from PySide6.QtWidgets import QInputDialog
        from PySide6.QtGui import QVector3D,QMatrix4x4
        old=self.selected()
        if old is None or not old.ext[self.engine.KEY].get('face_road'):
            raise ValueError('Select a TerraRoad face road or junction first.')
        text,ok=QInputDialog.getText(self,'Resize face road','Boundary offset: positive widens, negative narrows. Example: 1m or 3\'.')
        if not ok:
            return
        amount=self.section.length(text,self.units.currentData())
        if abs(amount)<1e-7:
            return
        api=self.engine.support('faces')
        data=old.ext[self.engine.KEY]
        points=[[QVector3D(*v) for v in ring] for ring in data['loops']]
        from core.mesh import Face,Vertex
        n=Face([Vertex(v) for v in points[0]]).normal()
        plane=lambda v:-(n.x()*v.x()+n.y()*v.y())/n.z()
        regions=api.offset_shape(api.ccw(points[0]),[api.ccw(r) for r in points[1:]],-amount)
        if len(regions)!=1:
            raise ValueError('This offset erases or splits the face. Use a smaller offset.')
        outer,holes=regions[0]
        loops=[[[v.x(),v.y(),plane(v)] for v in loop] for loop in [outer]+holes]
        new=api.from_loops(self.engine,self.section,loops,data['values'],old.name,data.get('kind','road'))
        local_frame=QMatrix4x4(new.xform)
        self.preserve(new,old)
        new.xform=(old.xform*local_frame) if old.xform is not None else local_frame
        self.apply_materials(new,data['values'])
        self.commit(new,old)
        self.refresh_selection()

    def fmt_length(self,value):
        return self.unit_api.format_length(value,self.unit_system)

    def change_system(self,*args):
        if self.loading:
            return
        system=self.system_combo.currentData()
        if system==self.unit_system:
            return
        raw=self.collect()
        self.unit_system=system
        self.settings.setValue('system',system)
        self.apply(raw)

    def bare_unit_changed(self,*args):
        if self.loading:
            return
        new_unit=self.units.currentData()
        # Preserve the old physical meaning of bare numbers before changing
        # their input convention. Explicitly qualified values need no rewrite.
        for key,widget in self.fields.items():
            if key in self.section.DATA['lengths'] and isinstance(widget,QLineEdit):
                text=widget.text().strip()
                if text and not any(char.isalpha() or char in "'\"" for char in text):
                    metres=self.section.length(text,self.input_unit)
                    widget.setText(self.unit_api.input_length(metres,self.unit_system))
        self.input_unit=new_unit
        self.queue()

    def tr_text(self,text):
        return self.locale_api.translate(text,self.language)

    def change_language(self,*args):
        self.language=self.language_combo.currentData()
        self.settings.setValue('language',self.language)
        self.retranslate()

    def retranslate(self):
        # Stable widget/item sources make switching reversible. Never translate
        # user-entered values, material names, style names or parameter keys.
        skip=(self.styles,self.language_combo,self.fields.get('road_pick'))
        for widget in self.findChildren(QWidget):
            if widget.property('noTranslate') or widget is self.create_button:
                continue
            if isinstance(widget,QComboBox) and widget not in skip:
                widget.blockSignals(True)
                for i in range(widget.count()):
                    source=widget.itemData(i,Qt.UserRole+101)
                    if source is None:
                        source=widget.itemText(i)
                        widget.setItemData(i,source,Qt.UserRole+101)
                    widget.setItemText(i,self.tr_text(source))
                widget.blockSignals(False)
            elif isinstance(widget,(QLabel,QPushButton,QToolButton,QCheckBox)):
                source=widget.property('trSource')
                if source is None:
                    source=widget.text()
                    widget.setProperty('trSource',source)
                keys=widget.property('trKeys')
                label=(self.locale_api.field_label(keys,source,self.language) if keys else self.tr_text(source))
                widget.setText(label.replace('&','&&') if isinstance(widget,QToolButton) else label)
        self.setLayoutDirection(Qt.RightToLeft if self.language in ('ar','ur') else Qt.LeftToRight)
        self.language_note.setVisible(self.language!='en')
        self.setWindowTitle(f'TerraRoad {self.engine.VERSION} — '+self.tr_text('Road designer'))
        # Numeric road diagrams always use world left/right orientation.
        self.diagram.setLayoutDirection(Qt.LeftToRight)
        from core.mesh import Face
        has_faces=any(isinstance(item,Face) for item in self.app.scene.selection)
        self.create_button.setText(self.tr_text('Update selected road' if self.selected() else 'Convert to a road' if has_faces else 'Create'))
        self.preview()
