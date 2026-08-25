"""Test script for audiogame_libs form library"""

import pygame
import sys
import os

# Add parent directory to path to import the library
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audiogame_libs import (
    Form, Button, Label, TextBox, CheckBox, RadioButton, 
    ComboBox, ListBox, Slider, ProgressBar, GroupBox,
    TabControl, MenuBar, StatusBar, AccessibilityOutput,
    OutputMode
)


def create_test_form():
    """Create a test form with all widget types"""
    
    # Create the main form
    form = Form(800, 600, "Audiogame Libs - Widget Test")
    
    # Setup accessibility
    form.accessibility_enabled = True
    
    # Create widgets
    
    # 1. Label
    label = Label(form, "Welcome to Audiogame Libs Test Form")
    label.set_position(20, 20)
    label.set_size(400, 30)
    label.accessibility_description = "Main title label"
    form.add_widget(label)
    
    # 2. Button
    button = Button(form, "Click Me!")
    button.set_position(20, 60)
    button.set_size(120, 35)
    button.is_default = True
    button.accessibility_description = "Primary action button"
    
    def on_button_click(widget):
        print(f"[EVENT] Button clicked!")
        form._announce("Button was clicked")
        status_bar.set_text("Button clicked!")
    
    button.on_click = on_button_click
    form.add_widget(button)
    
    # 3. TextBox
    textbox = TextBox(form, "Type something here...")
    textbox.set_position(20, 110)
    textbox.set_size(300, 35)
    textbox.accessibility_description = "Text input field"
    
    def on_text_changed(widget):
        print(f"[EVENT] Text changed: {widget.get_value()}")
        status_bar.set_text(f"Text: {widget.get_value()}")
    
    textbox.on_value_changed = on_text_changed
    form.add_widget(textbox)
    
    # 4. CheckBox
    checkbox = CheckBox(form, "Enable feature")
    checkbox.set_position(20, 160)
    checkbox.set_size(150, 30)
    checkbox.accessibility_description = "Toggle feature on/off"
    
    def on_check_changed(widget):
        print(f"[EVENT] Checkbox: {widget.get_value()}")
        status_bar.set_text(f"Checkbox: {widget.get_value()}")
    
    checkbox.on_value_changed = on_check_changed
    form.add_widget(checkbox)
    
    # 5. Radio Buttons
    group_box = GroupBox(form, "Choose Option")
    group_box.set_position(20, 210)
    group_box.set_size(200, 120)
    form.add_widget(group_box)
    
    radio1 = RadioButton(form, "Option A", "options")
    radio1.set_position(30, 240)
    radio1.set_size(150, 25)
    radio1.accessibility_description = "Option A"
    
    def on_radio_changed(widget):
        print(f"[EVENT] Radio selected: {widget.text}")
        status_bar.set_text(f"Selected: {widget.text}")
    
    radio1.on_value_changed = on_radio_changed
    form.add_widget(radio1)
    
    radio2 = RadioButton(form, "Option B", "options")
    radio2.set_position(30, 275)
    radio2.set_size(150, 25)
    radio2.accessibility_description = "Option B"
    radio2.on_value_changed = on_radio_changed
    form.add_widget(radio2)
    
    radio3 = RadioButton(form, "Option C", "options")
    radio3.set_position(30, 300)
    radio3.set_size(150, 25)
    radio3.accessibility_description = "Option C"
    radio3.on_value_changed = on_radio_changed
    form.add_widget(radio3)
    
    # Select default
    radio2.select()
    
    # 6. ComboBox
    combobox = ComboBox(form, ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"])
    combobox.set_position(250, 110)
    combobox.set_size(200, 35)
    combobox.accessibility_description = "Drop-down selection"
    
    def on_combobox_changed(widget):
        print(f"[EVENT] ComboBox selected: {widget.get_value()}")
        status_bar.set_text(f"Selected: {widget.get_value()}")
    
    combobox.on_value_changed = on_combobox_changed
    form.add_widget(combobox)
    
    # 7. ListBox
    listbox = ListBox(form, ["Apple", "Banana", "Orange", "Grape", "Watermelon"])
    listbox.set_position(250, 160)
    listbox.set_size(200, 120)
    listbox.multi_select = True
    listbox.visible_items = 5
    listbox.accessibility_description = "List of fruits"
    
    def on_listbox_changed(widget):
        value = widget.get_value()
        print(f"[EVENT] ListBox selected: {value}")
        status_bar.set_text(f"Fruits: {value}")
    
    listbox.on_value_changed = on_listbox_changed
    form.add_widget(listbox)
    
    # 8. Slider
    slider = Slider(form, 0, 100, 50)
    slider.set_position(250, 300)
    slider.set_size(200, 40)
    slider.step = 5
    slider.accessibility_description = "Volume control"
    
    def on_slider_changed(widget):
        print(f"[EVENT] Slider: {widget.get_value()}")
        progress_bar.set_value(widget.get_value())
        status_bar.set_text(f"Volume: {widget.get_value()}%")
    
    slider.on_value_changed = on_slider_changed
    form.add_widget(slider)
    
    # 9. ProgressBar
    progress_bar = ProgressBar(form, 0, 100, 0)
    progress_bar.set_position(250, 350)
    progress_bar.set_size(200, 25)
    progress_bar.show_text = True
    progress_bar.accessibility_description = "Progress indicator"
    form.add_widget(progress_bar)
    
    # 10. TabControl
    tab_control = TabControl(form)
    tab_control.set_position(480, 60)
    tab_control.set_size(300, 300)
    tab_control.accessibility_description = "Tabbed interface"
    
    # Add tabs
    tab1_idx = tab_control.add_tab("Settings")
    tab2_idx = tab_control.add_tab("Advanced")
    tab3_idx = tab_control.add_tab("About")
    
    # Add widgets to tabs
    tab_label1 = Label(form, "Settings Tab Content")
    tab_label1.set_position(490, 110)
    tab_label1.set_size(200, 30)
    tab_control.add_widget_to_tab(tab1_idx, tab_label1)
    
    tab_check = CheckBox(form, "Auto-save")
    tab_check.set_position(490, 150)
    tab_check.set_size(150, 30)
    tab_control.add_widget_to_tab(tab1_idx, tab_check)
    
    tab_button = Button(form, "Apply Settings")
    tab_button.set_position(490, 200)
    tab_button.set_size(120, 35)
    tab_control.add_widget_to_tab(tab1_idx, tab_button)
    
    tab_label2 = Label(form, "Advanced Settings")
    tab_label2.set_position(490, 110)
    tab_label2.set_size(200, 30)
    tab_control.add_widget_to_tab(tab2_idx, tab_label2)
    
    tab_label3 = Label(form, "Audiogame Libs v1.0.0")
    tab_label3.set_position(490, 110)
    tab_label3.set_size(200, 30)
    tab_control.add_widget_to_tab(tab3_idx, tab_label3)
    
    form.add_widget(tab_control)
    
    # 11. MenuBar
    menu_bar = MenuBar(form)
    
    # File menu
    file_menu = [
        {"text": "New", "shortcut": "Ctrl+N", "enabled": True},
        {"text": "Open...", "shortcut": "Ctrl+O", "enabled": True},
        {"text": "Save", "shortcut": "Ctrl+S", "enabled": True},
        {"text": "-", "separator": True},
        {"text": "Exit", "shortcut": "Alt+F4", "enabled": True}
    ]
    menu_bar.add_menu("File", file_menu)
    
    # Edit menu
    edit_menu = [
        {"text": "Undo", "shortcut": "Ctrl+Z", "enabled": True},
        {"text": "Redo", "shortcut": "Ctrl+Y", "enabled": True},
        {"text": "-", "separator": True},
        {"text": "Cut", "shortcut": "Ctrl+X", "enabled": True},
        {"text": "Copy", "shortcut": "Ctrl+C", "enabled": True},
        {"text": "Paste", "shortcut": "Ctrl+V", "enabled": True}
    ]
    menu_bar.add_menu("Edit", edit_menu)
    
    # Help menu
    help_menu = [
        {"text": "Documentation", "shortcut": "F1", "enabled": True},
        {"text": "About", "shortcut": "", "enabled": True}
    ]
    menu_bar.add_menu("Help", help_menu)
    
    # 12. StatusBar
    status_bar = StatusBar(form)
    status_bar.set_text("Ready - Press TAB to navigate")
    
    # Store references for later use
    form._menu_bar = menu_bar
    form._status_bar = status_bar
    
    # Add a few more sample widgets for variety
    
    # Sample buttons in a row
    button2 = Button(form, "Cancel")
    button2.set_position(160, 60)
    button2.set_size(100, 35)
    button2.is_cancel = True
    
    def on_cancel_click(widget):
        print("[EVENT] Cancel clicked - exiting")
        form._announce("Exiting application")
        form.close()
    
    button2.on_click = on_cancel_click
    form.add_widget(button2)
    
    # A small info label
    info_label = Label(form, "Tab to navigate | Space/Enter to activate")
    info_label.set_position(20, 570)
    info_label.set_size(400, 20)
    info_label.accessibility_description = "Navigation help"
    form.add_widget(info_label)
    
    return form


def main():
    """Main test function"""
    print("=" * 60)
    print("Audiogame Libs - Test Application")
    print("=" * 60)
    print("\nControls:")
    print("  TAB          - Next widget")
    print("  Shift+TAB    - Previous widget")
    print("  Space/Enter  - Activate button/checkbox")
    print("  ESC          - Exit")
    print("  Arrow keys   - Navigate sliders and lists")
    print("\nAccessibility output enabled - check console for speech text")
    print("=" * 60)
    print()
    
    # Setup accessibility with console output (for testing)
    a11y = AccessibilityOutput(OutputMode.CONSOLE)
    a11y.speak("Audiogame Libs test application started")
    
    # Create and run the form
    form = create_test_form()
    
    # Run the form
    try:
        form.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pygame.quit()
        print("\nApplication closed")


if __name__ == "__main__":
    main()
