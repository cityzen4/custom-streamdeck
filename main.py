import time
import threading
import os
import libusb_package
import pystray
from pystray import MenuItem as item
from streamdeck_manager import get_deck, update_deck_buttons
from window_manager import get_open_windows, toggle_window_state
from PIL import Image

# Help StreamDeck find libusb on Windows
try:
    lib_path = libusb_package.get_library_path()
    if lib_path:
        os.add_dll_directory(os.path.dirname(lib_path))
except Exception as e:
    print(f"Warning: Could not add libusb DLL directory: {e}")

# Global state to keep track of current windows on keys
current_windows = []
update_lock = threading.Lock()
should_exit = False
deck_obj = None

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
                current_windows = [] # Force a full refresh next loop
        except Exception as e:
            print(f"Error resetting deck: {e}")

def setup_tray():
    icon_path = r"c:\projects\streamdeck\app_icon.ico"
    try:
        image = Image.open(icon_path)
    except:
        image = Image.new('RGB', (64, 64), color=(0, 120, 215))
    
    menu = (
        item('Reset Deck', on_reset),
        item('Quit', on_quit),
    )
    icon = pystray.Icon("StreamDeckSwitcher", image, "StreamDeck Switcher", menu)
    icon.run()

def refresh_loop(deck):
    global current_windows, should_exit
    while not should_exit:
        try:
            # We fetch exactly what is on the taskbars, in exact order, with exact pixel icons.
            new_windows = get_open_windows()
            
            with update_lock:
                changed = False
                
                # Hard array comparison guarantees we catch all drags
                if len(new_windows) != len(current_windows):
                    changed = True
                else:
                    for i, win in enumerate(new_windows):
                        if win['name'] != current_windows[i].get('name'):
                            changed = True
                            print(f"DEBUG: Taskbar change detected at index {i} ({current_windows[i].get('name', '')} -> {win['name']})")
                            break

                if changed:
                    # Rename 'name' to 'title' to match streamdeck_manager's expectations
                    for w in new_windows:
                        if 'name' in w and 'title' not in w:
                            w['title'] = w['name']

                    current_windows = new_windows
                    update_deck_buttons(deck, current_windows)
                
        except Exception as e:
            print(f"CRITICAL: Error in refresh loop: {e}")
            import traceback
            traceback.print_exc()
            
        time.sleep(1)

def key_change_callback(deck, key, state):
    global current_windows
    if state: # Key pressed
        with update_lock:
            if key < len(current_windows):
                win = current_windows[key]
                print(f"Toggling window taskbar button: {win.get('title', win.get('name', 'Unknown'))}")
                
                # Use hybrid toggle logic
                try:
                    toggle_window_state(win.get('title', win.get('name')))
                except Exception as e:
                    print(f"Error toggling window: {e}")
            else:
                print(f"DEBUG: Key {key} pressed but no window mapped.")

if __name__ == "__main__":
    deck_obj = None
    try:
        deck_obj = get_deck()
    except Exception as e:
        print(f"CRITICAL ERROR initializing StreamDeck: {e}")
        time.sleep(5)
        exit(1)

    if not deck_obj:
        print("No StreamDeck found. Exiting.")
        exit(1)

    print("StreamDeck Window Switcher started.")
    print("System Tray icon active.")
    
    deck_obj.set_key_callback(key_change_callback)

    threading.Thread(target=setup_tray, daemon=True).start()
    threading.Thread(target=refresh_loop, args=(deck_obj,), daemon=True).start()

    try:
        while not should_exit:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    print("\nExiting...")
    if deck_obj:
        deck_obj.reset()
        deck_obj.close()
