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

# ── Tray icon ──
def on_quit(icon, item):
    global should_exit
    print("Quitting from tray...")
    should_exit = True
    icon.stop()

def on_reset(icon, item):
    global current_windows, deck_obj
    print("Resetting StreamDeck from tray...")
    with update_lock:
        try:
            if deck_obj:
                deck_obj.reset()
                current_windows = []
        except Exception as e:
            print(f"Error resetting deck: {e}")

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
                    for w in new_windows:
                        if 'name' in w and 'title' not in w:
                            w['title'] = w['name']
                    current_windows = new_windows
                    update_deck_buttons(deck, current_windows, LOWER_LEFT_INDEX)

        except Exception as e:
            print(f"Error in refresh loop: {e}")

        # Update browser tab tracking
        browser_tracker.update()
        time.sleep(1)

# ── Key callback ──
def key_change_callback(deck, key, state):
    pythoncom.CoInitialize()
    try:
        global current_windows, LOWER_LEFT_INDEX
        if state:  # Key pressed
            if key == LOWER_LEFT_INDEX:
                print("Special Key: Browser Tab Toggle")
                browser_tracker.toggle_active_tab()
                return

            with update_lock:
                win_idx = key
                if LOWER_LEFT_INDEX != -1 and key > LOWER_LEFT_INDEX:
                    win_idx = key - 1

                if win_idx < len(current_windows):
                    win = current_windows[win_idx]
                    print(f"Toggling window: {win.get('title', win.get('name', 'Unknown'))}")
                    try:
                        toggle_window_state(win.get('title', win.get('name')))
                    except Exception as e:
                        print(f"Error toggling window: {e}")
    finally:
        pythoncom.CoUninitialize()

# ── Main ──
if __name__ == "__main__":
    if not acquire_single_instance():
        print("StreamDeck Switcher is already running. Exiting.")
        sys.exit(0)

    threading.Thread(target=setup_tray, daemon=True).start()

    try:
        while not should_exit:
            deck_obj = None
            current_windows = []
            
            print("Waiting for StreamDeck...")
            while not should_exit:
                try:
                    from StreamDeck.DeviceManager import DeviceManager
                    decks = DeviceManager().enumerate()
                    if decks:
                        deck_obj = decks[0]
                        deck_obj.open()
                        deck_obj.reset()
                        break
                except Exception: pass
                time.sleep(3)

            if should_exit: break

            rows, cols = deck_obj.key_layout()
            LOWER_LEFT_INDEX = (rows - 1) * cols
            print(f"Connected. Lower-left index: {LOWER_LEFT_INDEX}")
            
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
