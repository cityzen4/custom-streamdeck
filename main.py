import time
import threading
import os
import sys
import ctypes
import libusb_package
import pystray
from pystray import MenuItem as item
from streamdeck_manager import get_deck, update_deck_buttons
from window_manager import get_open_windows, toggle_window_state, browser_tracker
from PIL import Image
import pythoncom
import logging
import datetime
import json
import win32gui
import win32con
from window_manager import _HIDDEN_TRAY_WINDOWS, find_hwnd_by_tooltip

# ── Logging Setup ──
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streamdeck.log")

def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        filemode='a'
    )
    # Redirect print to log
    class LogWriter:
        def write(self, message):
            if message.strip():
                logging.info(message.strip())
        def flush(self):
            pass
    sys.stdout = LogWriter()
    sys.stderr = LogWriter()

setup_logging()
print(f"--- StreamDeck Switcher Started at {datetime.datetime.now()} ---")

# Help StreamDeck find libusb on Windows
try:
    lib_path = libusb_package.get_library_path()
    if lib_path:
        os.add_dll_directory(os.path.dirname(lib_path))
except Exception as e:
    print(f"Warning: Could not add libusb DLL directory: {e}")

# ── Single-instance guard via Windows named mutex ──
MUTEX_NAME = "Global\\StreamDeckSwitcher_SingleInstance"
_mutex_handle = None

def acquire_single_instance():
    """Returns True if this is the only running instance, False otherwise."""
    global _mutex_handle
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
    last_error = ctypes.windll.kernel32.GetLastError()
    
    if not _mutex_handle or last_error == 183: # ERROR_ALREADY_EXISTS
        if _mutex_handle:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
        return False
    return True

def release_single_instance():
    global _mutex_handle
    if _mutex_handle:
        ctypes.windll.kernel32.ReleaseMutex(_mutex_handle)
        ctypes.windll.kernel32.CloseHandle(_mutex_handle)
        _mutex_handle = None

# ── Global state ──
current_windows = []
update_lock = threading.Lock()
should_exit = False
deck_obj = None
LOWER_LEFT_INDEX = -1
RESET_DECK_INDEX = -1
MAX_WINDOW_KEYS = -1

# ── Tray icon ──
def on_quit(icon, item):
    global should_exit
    print("Quitting from tray...")
    should_exit = True
    icon.stop()

def restart_app():
    print("Restarting app completely...")
    global should_exit
    should_exit = True
    release_single_instance()
    vbs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_streamdeck_invisible.vbs")
    os.startfile(vbs_path)
    os._exit(0)

def on_reset(icon, item):
    print("Resetting StreamDeck from tray (now restarting app)...")
    icon.stop()
    restart_app()

def setup_tray():
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
    try:
        image = Image.open(icon_path)
    except:
        image = Image.new('RGB', (64, 64), color=(0, 120, 215))

    menu = (
        item('Reset Deck', on_reset),
        item('Quit', on_quit),
    )
    tray = pystray.Icon("StreamDeckSwitcher", image, "StreamDeck Switcher", menu)
    tray.run()

# ── Refresh loop ──
def refresh_loop(deck):
    global current_windows, should_exit
    
    # Force initial update
    new_windows = get_open_windows()
    with update_lock:
        current_windows = new_windows
        update_deck_buttons(deck, current_windows, LOWER_LEFT_INDEX, RESET_DECK_INDEX, MAX_WINDOW_KEYS)

    while not should_exit:
        try:
            new_windows = get_open_windows()

            with update_lock:
                changed = False
                if len(new_windows) != len(current_windows):
                    changed = True
                else:
                    for i, win in enumerate(new_windows):
                        if win['name'] != current_windows[i].get('name'):
                            changed = True
                            break

                if changed:
                    current_windows = new_windows
                    update_deck_buttons(deck, current_windows, LOWER_LEFT_INDEX, RESET_DECK_INDEX, MAX_WINDOW_KEYS)

        except Exception as e:
            print(f"Error in refresh loop: {e}")

        # Update browser tab tracking
        browser_tracker.update()
        time.sleep(1)

def tray_monitor_loop():
    global should_exit, current_windows
    previous_placements = {}
    
    while not should_exit:
        try:
            config_path = r'c:\projects\commander\config.json'
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                tray_windows = config.get('tray_windows', [])
                for target_rule in tray_windows:
                    clean_rule = target_rule.strip('"').strip("'")
                    matched_hwnds = []
                    win32gui.EnumWindows(lambda h, extra: matched_hwnds.append(h) if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) and clean_rule in win32gui.GetWindowText(h) else None, None)
                    
                    for hwnd in matched_hwnds:
                        actual_title = win32gui.GetWindowText(hwnd)
                        placement = win32gui.GetWindowPlacement(hwnd)[1]
                        prev_placement = previous_placements.get(hwnd)
                        
                        if placement == win32con.SW_SHOWMINIMIZED and prev_placement != win32con.SW_SHOWMINIMIZED and prev_placement is not None:
                            print(f"Detected flagged window minimized: {actual_title} ({hwnd}) matching rule: {clean_rule}")
                            
                            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                            
                            icon_image = None
                            for w in current_windows:
                                if w.get('name') == actual_title or w.get('title') == actual_title:
                                    if w.get('icon'):
                                        icon_image = w['icon']
                                    break
                            
                            if not icon_image:
                                try:
                                    icon_image = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico"))
                                except:
                                    icon_image = Image.new('RGB', (64, 64), color=(0, 120, 215))

                            def create_restore_func(t_arg):
                                def on_restore(icon, item):
                                    toggle_window_state(t_arg)
                                return on_restore

                            menu = pystray.Menu(
                                pystray.MenuItem('Restore Window', create_restore_func(actual_title), default=True)
                            )
                            tray = pystray.Icon(f"hidden_{hwnd}", icon_image, actual_title, menu)
                            
                            import window_manager
                            window_manager._HIDDEN_TRAY_WINDOWS.append({
                                'name': actual_title,
                                'title': actual_title,
                                'hwnd': hwnd,
                                'icon': icon_image,
                                'tray_icon': tray
                            })
                            
                            threading.Thread(target=tray.run, daemon=True).start()
                            
                        # Update previous placement
                        if win32gui.IsWindowVisible(hwnd):
                            previous_placements[hwnd] = placement
                            
        except Exception as e:
            pass # ignore transient reading errors
        time.sleep(1.5)

# ── Key callback ──
def key_change_callback(deck, key, state):
    if not state:
        return

    def action():
        pythoncom.CoInitialize()
        try:
            global current_windows, LOWER_LEFT_INDEX, RESET_DECK_INDEX, MAX_WINDOW_KEYS
            if key == LOWER_LEFT_INDEX:
                print("Special Key: Browser Tab Toggle")
                browser_tracker.toggle_active_tab()
                return
            if key == RESET_DECK_INDEX:
                print("Special Key: Reset App")
                restart_app()
                return

            target_title = None
            with update_lock:
                if key < MAX_WINDOW_KEYS:
                    win_idx = key
                    if win_idx < len(current_windows):
                        win = current_windows[win_idx]
                        target_title = win.get('title', win.get('name'))

            if target_title:
                print(f"Toggling window: {target_title}")
                try:
                    toggle_window_state(target_title)
                except Exception as e:
                    print(f"Error toggling window: {e}")
        finally:
            pythoncom.CoUninitialize()

    threading.Thread(target=action, daemon=True).start()

# ── Main ──
if __name__ == "__main__":
    if not acquire_single_instance():
        print("StreamDeck Switcher is already running. Exiting.")
        sys.exit(0)

    # Write PID to file for auto-reboot script
    try:
        pid_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streamdeck.pid")
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        print(f"Failed to write PID file: {e}")

    threading.Thread(target=setup_tray, daemon=True).start()
    threading.Thread(target=tray_monitor_loop, daemon=True).start()

    try:
        while not should_exit:
            deck_obj = None
            current_windows = []
            
            print("Waiting for Stream Deck XL...")
            while not should_exit:
                try:
                    # Specific filter for XL to avoid conflicts with Neo/others
                    deck_obj = get_deck(model_filter="Stream Deck XL")
                    if deck_obj:
                        break
                except Exception as e:
                    print(f"Error finding deck: {e}")
                time.sleep(3)

            if should_exit: break

            rows, cols = deck_obj.key_layout()
            LOWER_LEFT_INDEX = (rows - 1) * cols
            RESET_DECK_INDEX = rows * cols - 1
            MAX_WINDOW_KEYS = 3 * cols
            print(f"Connected. Lower-left index: {LOWER_LEFT_INDEX}, Reset index: {RESET_DECK_INDEX}, Max windows: {MAX_WINDOW_KEYS}")
            
            deck_obj.set_key_callback(key_change_callback)
            refresh_loop(deck_obj)

            try:
                deck_obj.reset()
                deck_obj.close()
            except: pass
            print("Deck disconnected.")
            time.sleep(2)

    except KeyboardInterrupt: pass
    finally:
        print("Exiting...")
        release_single_instance()
