"""Audiogame Libs - Accessibility-first GUI library for pygame"""

from .form import Form, Widget
from .widgets import (
    Button, Label, TextBox, CheckBox, RadioButton, ComboBox,
    ListBox, Slider, ProgressBar, TabControl, GroupBox,
    MenuBar, StatusBar, TreeView, DataGridView
)
from .accessibility import AccessibilityOutput

__version__ = "1.0.0"
__all__ = [
    "Form", "Widget",
    "Button", "Label", "TextBox", "CheckBox", "RadioButton",
    "ComboBox", "ListBox", "Slider", "ProgressBar", "TabControl",
    "GroupBox", "MenuBar", "StatusBar",
    "TreeView", "DataGridView", "AccessibilityOutput"
]
