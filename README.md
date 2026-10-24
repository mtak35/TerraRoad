# TerraRoad for IngeTrazo

Python road-design extension for **IngeTrazo 0.5.9**, published by
[mtak35](https://github.com/mtak35). Licensed under GPL-3.0-or-later.

**0.8.0-dev is a development preview.** This is a native Python port of the
author's TerraRoad SketchUp extension. Full feature parity remains incomplete.

![TerraRoad road junction with curbs, sidewalks, lighting and keep-clear markings](screenshots/terraroad-junction.png)

## New to TerraRoad?

Read the **[beginner's usage guide](USER_GUIDE.md)** for installation, your first
road, branches, face conversion, roundabouts, editing, units, maps and quantities.

![TerraRoad designer and live cross-section preview](screenshots/terraroad-designer.png)

## Features

- Continuous centerline road drawing and branches with generated junctions.
- Road-face conversion, editable road/junction groups and component parts.
- Curbs with alternating colors, sidewalks, medians, parking and lane markings.
- Roundabouts, road lighting, traffic signals and quantity CSV export.
- Metric/imperial input and a ten-language interface with English fallbacks.
- Reference maps, cropping, OSM centerlines and manual road tracing.

## Install

Download **TerraRoad-IngeTrazo-0.8.0-dev-catalog.zip** from Releases.
The ZIP contains one `terraroad/` folder with `__init__.py` and its helpers.
Install through IngeTrazo's extension manager when listed in the catalog, or
extract that complete folder into your IngeTrazo plugins folder and restart.
Open **Extensions → TerraRoad** or the **TerraRoad** toolbar button.

If you already installed the loose development version (`TerraRoad.py` plus
`_TerraRoad/`), back up preferences and remove that older installation before
installing the package, to avoid loading TerraRoad twice. Keep your saved models.

## Current limits

Automatic tracing imports OpenStreetMap centerlines and estimated widths; it
does not recognize road boundaries from Google/satellite image pixels. Local
screenshots need accurate site coordinates, physical width and north rotation.
Manual tracing is available for roads missing from, or displaced in, OSM.

Rebuilding regenerates parts from saved parameters and replaces manual geometry
edits. Some advanced variants, including arch/culvert bridges and movable
feature handles, remain unfinished. Branched face layouts require separate
road/junction pieces. See `PORT_STATUS.md` for additional port limitations.

## Source and licensing

All runtime source is in `terraroad/`. No extra pip dependencies are required:
the extension uses Python, Qt/PySide6 and IngeTrazo's own APIs.
Original TerraRoad: Copyright 2026 The Court Group. GitHub publisher: mtak35.
You may redistribute and modify this code under GPL version 3 or any later
version. See `LICENSE`. The software is provided without warranty.

Map providers retain their own attribution and usage terms. On-demand map/road
requests use network access; cached maps, settings, user styles and exports are
written locally. Optional Cesium credentials belong in the user's settings and
are not distributed with this package.
