import time
import uiautomation as auto
from PIL import ImageGrab

def is_valid_app_button(elem):
    """Filters out known system tray buttons and non-app items."""
    if not elem.Name:
        return False
    # Exclude Win11 default system buttons
    excluded_names = ['Start', 'Search', 'Task View', 'Widgets', 'Chat', 'Copilot']
    if elem.Name in excluded_names:
        return False
    # Exclude system tray items and "phantom" duplicate wrappers
    if elem.ClassName.startswith('SystemTray') or 'Tray' in elem.ClassName or elem.ClassName == '':
        return False
    # General sanity check for size
    rect = elem.BoundingRectangle
    if not rect or rect.width() <= 0 or rect.height() <= 0:
        return False
    return True

def get_taskbar_buttons(elem, buttons_list):
    """Recursively finds valid app buttons within a UIA element."""
    if elem.ControlType in [auto.ControlType.ButtonControl, auto.ControlType.ListItemControl]:
        if is_valid_app_button(elem):
            # Try to grab the exact taskbar icon screenshot
            icon_img = None
            try:
                # To prevent squeezing and text capture, grab the inner ImageControl
                img_controls = [c for c in elem.GetChildren() if c.ControlType == auto.ControlType.ImageControl]
                if img_controls:
                    c_rect = img_controls[0].BoundingRectangle
                    if c_rect and c_rect.width() > 0 and c_rect.height() > 0:
                        icon_img = ImageGrab.grab(bbox=(c_rect.left, c_rect.top, c_rect.right, c_rect.bottom), all_screens=True)
                
                # Fallback to the full button rect if no ImageControl exists
                if not icon_img:
                    rect = elem.BoundingRectangle
                    if rect and rect.width() > 0 and rect.height() > 0:
                        icon_img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True)

            except Exception as e:
                print(f"DEBUG: Failed to grab image for {elem.Name}: {e}")
            
            buttons_list.append({
                'name': elem.Name,
                'uia_control': elem,
                'icon': icon_img
            })
            return # Buttons don't usually contain other buttons we care about
            
    for child in elem.GetChildren():
        get_taskbar_buttons(child, buttons_list)

def get_open_windows():
    """Returns a list of dictionaries representing the exact taskbar items from all taskbars."""
    import pythoncom
    pythoncom.CoInitialize()
    
    buttons = []
    try:
        desktop = auto.GetRootControl()
        taskbars = []
        
        # Gather all taskbars
        primary_taskbar = auto.PaneControl(ClassName="Shell_TrayWnd")
        if primary_taskbar.Exists(0, 0):
            taskbars.append(primary_taskbar)
            
        for child in desktop.GetChildren():
            if child.ClassName == "Shell_SecondaryTrayWnd":
                taskbars.append(child)

        # Sort taskbars by their physical left coordinate (leftmost monitor to rightmost)
        taskbars.sort(key=lambda t: t.BoundingRectangle.left if t.BoundingRectangle else 0)

        # Extract buttons in the correct physical order
        for tb in taskbars:
            get_taskbar_buttons(tb, buttons)

        return buttons
    finally:
        pythoncom.CoUninitialize()

def find_hwnd_by_tooltip(tooltip):
    """Finds the HWND of a window whose title matches the taskbar tooltip."""
    import win32gui
    matched_hwnds = []
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            title = win32gui.GetWindowText(hwnd)
            # Match if the window title is in the tooltip or the tooltip is in the window title
            if title in tooltip or tooltip.startswith(title) or title.startswith(tooltip):
                matched_hwnds.append(hwnd)
    win32gui.EnumWindows(callback, None)
    # If multiple matched, return the first one (often the most recently used/z-ordered)
    return matched_hwnds[0] if matched_hwnds else None

def toggle_window_state(tooltip_name):
    """Restores original win32gui non-mouse-modifying toggle behavior."""
    import win32gui
    import win32con
    
    hwnd = find_hwnd_by_tooltip(tooltip_name)
    if not hwnd or not win32gui.IsWindow(hwnd):
        print(f"DEBUG: Could not find valid HWND for tooltip: {tooltip_name}")
        return

    placement = win32gui.GetWindowPlacement(hwnd)
    state = placement[1]
    
    try:
        if state == win32con.SW_SHOWMAXIMIZED:
            print(f"DEBUG: Minimizing window {hwnd}")
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        else:
            print(f"DEBUG: Maximizing/Restoring window {hwnd}")
            # Ensure it's not minimized first
            if state == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
            
            # Force focus
            try:
                import win32api
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                print(f"DEBUG: Focus error: {e}")
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except: pass
    except Exception as e:
        print(f"DEBUG: Error in toggle_window_state for {hwnd}: {e}")
