import time
import uiautomation as auto
from PIL import ImageGrab
import pythoncom
import win32gui
import win32con
import win32api

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
                'title': elem.Name,
                'uia_control': elem,
                'icon': icon_img
            })
            return # Buttons don't usually contain other buttons we care about
            
    for child in elem.GetChildren():
        get_taskbar_buttons(child, buttons_list)

def get_open_windows():
    """Returns a list of dictionaries representing the exact taskbar items from all taskbars."""
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

_HWND_CACHE = {} # tooltip -> hwnd

def find_hwnd_by_tooltip(tooltip):
    """Finds the HWND of a window whose title matches the taskbar tooltip."""
    # Check cache first
    cached_hwnd = _HWND_CACHE.get(tooltip)
    if cached_hwnd and win32gui.IsWindow(cached_hwnd) and win32gui.IsWindowVisible(cached_hwnd):
        title = win32gui.GetWindowText(cached_hwnd)
        if title and (title in tooltip or tooltip.startswith(title) or title.startswith(tooltip)):
            return cached_hwnd

    matched_hwnds = []
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            title = win32gui.GetWindowText(hwnd)
            # Match if the window title is in the tooltip or the tooltip is in the window title
            if title in tooltip or tooltip.startswith(title) or title.startswith(tooltip):
                matched_hwnds.append(hwnd)
    
    win32gui.EnumWindows(callback, None)
    
    if matched_hwnds:
        # If multiple matched, return the first one (often the most recently used/z-ordered)
        hwnd = matched_hwnds[0]
        _HWND_CACHE[tooltip] = hwnd
        return hwnd
    
    return None

def toggle_window_state(tooltip_name):
    """Restores original win32gui non-mouse-modifying toggle behavior."""
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
            
            # Show and bring to front
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
            
            # Robust focus
            try:
                # Alt-key tap to bypass focus restrictions
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
            except Exception as e:
                print(f"DEBUG: Focus error: {e}")
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except: pass
    except Exception as e:
        print(f"DEBUG: Error in toggle_window_state for {hwnd}: {e}")

class BrowserTabTracker:
    def __init__(self):
        self.history = {} # hwnd -> (current_tab_name, previous_tab_name)

    def update(self):
        """Polls the active window and updates tab history for Chrome/Vivaldi."""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return

        title = win32gui.GetWindowText(hwnd).lower()
        if "chrome" not in title and "vivaldi" not in title:
            return

        try:
            # We use uiautomation to find the selected tab
            pythoncom.CoInitialize()
            try:
                browser_win = auto.ControlFromHandle(hwnd)
                
                # Find all TabItemControls recursively
                tabs = []
                def find_tabs(ctrl, depth=0):
                    if depth > 8: return
                    if ctrl.ControlType == auto.ControlType.TabItemControl:
                        tabs.append(ctrl)
                    for child in ctrl.GetChildren():
                        find_tabs(child, depth + 1)
                
                find_tabs(browser_win)
                
                current_tab = None
                for tab in tabs:
                    try:
                        if tab.GetSelectionItemPattern().IsSelected:
                            current_tab = tab.Name
                            break
                    except: continue

                if current_tab:
                    prev_state = self.history.get(hwnd, (None, None))
                    if current_tab != prev_state[0]:
                        # Record history: (new_current, old_current)
                        self.history[hwnd] = (current_tab, prev_state[0])
                        print(f"DEBUG: Tab history updated for HWND {hwnd}: {current_tab} (previous: {prev_state[0]})")
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            print(f"DEBUG: BrowserTabTracker update error: {e}")

    def toggle_active_tab(self):
        """Switches to the previous tab in the active browser window."""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd: return

        state = self.history.get(hwnd)
        if not state or not state[1]:
            print(f"DEBUG: No previous tab recorded for HWND {hwnd}")
            return

        previous_tab_name = state[1]
        print(f"DEBUG: Attempting to toggle to previous tab: {previous_tab_name}")

        pythoncom.CoInitialize()
        try:
            browser_win = auto.ControlFromHandle(hwnd)
            target_tab = browser_win.TabItemControl(searchDepth=8, Name=previous_tab_name)
            if target_tab.Exists(0, 0):
                target_tab.GetSelectionItemPattern().Select()
                return True
            else:
                print(f"DEBUG: Could not find tab '{previous_tab_name}' to toggle back.")
        except Exception as e:
            print(f"DEBUG: toggle_active_tab error: {e}")
        finally:
            pythoncom.CoUninitialize()
        return False

# Global instance
browser_tracker = BrowserTabTracker()
