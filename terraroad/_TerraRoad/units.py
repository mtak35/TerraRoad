# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The Court Group. Published by mtak35.
"""Display/input units. Geometry is always stored in IngeTrazo metres."""
from fractions import Fraction
import math
import os
from pathlib import Path


def settings():
    """Per-user plugin preferences, portable across packaged Qt installations."""
    from PySide6.QtCore import QSettings
    target=Path(os.environ.get('TERRAROAD_SETTINGS_FILE') or Path(__file__).with_name('preferences.ini'))
    target.parent.mkdir(parents=True,exist_ok=True)
    return QSettings(str(target.resolve()),QSettings.IniFormat)

SYSTEMS={'metric':('Metric','m'),'imperial':('Imperial','ft')}


def format_length(metres,system='metric',precision=3):
    if system=='imperial':
        sign='-' if metres<0 else ''
        # Nearest 1/64 inch keeps repeat switching well below mesh tolerance.
        ticks=round(abs(metres)/.0254*64)
        feet,ticks=divmod(ticks,12*64)
        inches,numerator=divmod(ticks,64)
        fraction=str(Fraction(numerator,64)) if numerator else ''
        text=str(inches)+((' '+fraction) if fraction else '')
        return f'{sign}{feet}\' {text}"'
    return f'{metres:.{precision}f} m'


def input_length(metres,system='metric'):
    # Keep exact-enough explicit units in editable controls; formatted feet and
    # inches are for display. Switching never rounds underlying dimensions.
    value=metres/.3048 if system=='imperial' else metres
    number=f'{value:.12f}'.rstrip('0').rstrip('.') or '0'
    return number+(' ft' if system=='imperial' else ' m')


def area(value,system='metric'):
    return (value/.3048**2,'ft²') if system=='imperial' else (value,'m²')


def volume(value,system='metric'):
    return (value/.3048**3,'ft³') if system=='imperial' else (value,'m³')
