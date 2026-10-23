# TerraRoad for IngeTrazo — 0.8.0-dev

Target: IngeTrazo 0.5.9. Original: TerraRoad 172.0.0, copyright 2026 The Court Group. This is a native Python port with the same name. **Full original feature parity remains in progress.**

## Current behavior

0.8 corrects texture UV orientation, repairs earlier map frames on opening the designer, retains geographic crop references after map placement transforms, removes unrequested splitter islands, and adds painted central-island curb blocks. Tracing uses OSM data rather than image segmentation.

0.7 fixes continuous click/length road drawing, automatic branches from existing roads, default open ends on identifiable road-strip faces (including L-shaped strips), true rectangle crop previews, and map-frame-based tracing with individual road picking and manual tracing. Roundabouts now have tangent entry returns, a circular annulus, island curb/planting/apron, yield lines, circular lane dashes and circulation arrows. They do not receive yellow keep-clear boxes. Automatic sizing can enlarge the central island to fit the approaches; manual sizing rejects overlapping entry curves. Starting a branch rebuilds the connected network in the clicked road's inherited style; generated manual edits are not retained by this rebuild.

All 241 original row controls, 244 defaults, 19 presets and six saved user styles remain in the source inventory. The two original junction sections are combined, giving 19 visible panel sections. The TerraRoad toolbar opens the complete designer with sections collapsed. Search restores the full view; Show all active options expands working controls and hides pending ones. Metric/imperial input, diagrams, exports and 11 local language choices are retained. Long technical notes and newer diagnostics may remain English.

Centerline roads use the original static section profile for carriageways, medians, separate median curb sizes, parking, shoulders, channels/grating, service roads, curbs, planting, walks, lane paint and parking paint. Placement settings generate street lights, traffic signals and zebra crossings. Lattice road poles carry sagging conductors. Model-level standalone high-tension layouts remain pending.

Road and junction containers are independent scene groups. Their parts are nested components with distinct identities. Save/open and undo/redo retain that structure. Rebuild migrates an older single-container network. Manual component editing is available through IngeTrazo group/component editing; a TerraRoad parameter rebuild replaces generated geometry, including manual edits.

The native Draw a road tool follows the host line tool's snaps and length entry, creates the road after each segment, and supports history. Draw / edit road actions include settings, apply/reset-to-design, line conversion, branching, point movement, mirrored copies and deletion. Branches can be connected by rebuilding selected roads through Junctions & roundabouts.

Selected centerlines or existing road groups build T/X junctions and roundabouts. Road mouths stay open, with continuous curb/walk/planting returns and optional return accessories. Median noses at approach ends have semicircular curbs and asphalt infill. Yellow keep-clear diagonal crosshatching is controlled under Traffic signals, including spacing/inset/width/material. Switching a network to a roundabout replaces the old groups in one undo step.

Converted planar faces support concavity, holes, slope, reserve/asphalt semantics, roadside bands, fitted carriageways/lanes, parking/service/shoulder strips, parking paint, rounded medians and perimeter lights. Arrow and zebra click tools, straight direction spines, clearing marks, restyling, repair, offset resizing, road/junction switching and component conversion are active. Adjoining coplanar faces sharing straight edges can be connected: roadside bands stop across the shared mouth and asphalt fills the reserved strip. Rectangular branched layouts, including rotated layouts, can be partitioned into separate named road/turn/junction groups with open shared mouths.

Lane-marking actions also provide station-based U-turn openings, zebra crossings, smooth local widening/narrowing, raised/lowered spans and deck bridges with decks, parapets, abutments and intermediate piers. These are saved with their road and return on rebuild. Width/level changes move the generated section and its accessories. Span and ramp lengths must fit inside the road. Undo removes the edit.

Site/map supports full coordinates/links, anchored/rotated map images, OSM/Esri imagery, compatible flat-template Cesium assets, local reference pictures, source switching, OSM centerline/estimated-edge imports, selected-window or two-corner cropping, and Street View at a selected location. Cropped bounds drive tracing and returned ways are clipped. Small patches use the public OSM map API with filtered Overpass fallback. Image work runs in background threads, attribution is retained, and IGZ embeds pictures. Services can refuse/time out. A live public 300 m London test returned 133 road chains / 493 segments.

## Limits still requiring original algorithms

- Network junctions need level cross-sections, zero lateral offset and sufficiently long approach segments. Complex mixed-width network rules, design-speed checks, turning heads, spiral roundabouts and variable lane-count entries remain unfinished. Closed centerline cycles must be opened before network building.
- Face lane/parking layout follows one principal straight axis, clipped to the actual face. It does not yet follow curved spines or adapt lane widths continuously around curved/irregular layouts. Nonrectangular automatic decomposition remains pending. Face signals need defined approaches; use centerline networks for automatic signals. Perimeter poles are not culled at manually connected mouths yet.
- Deck bridges are implemented. Arches, culvert variants, automatic grade-separated crossing detection and draggable original feature markers remain unfinished. Curved local transitions can differ from the original adaptive builders. Terrain drape, terrain cut/fill and terrain trimming are not implemented by the local raised/lowered-span tool.
- Standalone high-tension layouts, road studs, speed breakers, detailed grating slots and some original placement options remain pending. Their retained fields are marked accordingly.
- Source SketchUp model/attribute migration is not implemented. The Ruby extension itself is not changed.
- Quantities are design estimates using section dimensions/plan lengths and face regions. Junction-return estimates travel with their separate junction. Local widening, complex deformation, scaling and manual part edits need measured take-off; these estimates are not engineering cut/fill quantities.
- IngeTrazo's separate global GIS datum, short map-link resolution and incompatible Cesium asset types are not handled by this extension.

## Verification

Tests use the actual IngeTrazo 0.5.9 geometry, history and IGZ classes and Qt controls. Coverage includes closed solids/positive volumes, separate editable groups/components, world-coordinate preservation, undo/redo, save/open, face accessories, semicircular median ends, keep-clear markings, local road edits, bridge solids, face decomposition/connections, map crop picking and clipped tracing. Native GUI verification uses a separate demo document, preserving the user's model.
