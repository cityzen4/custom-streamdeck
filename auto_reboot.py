import tkinter as tk
import time
import os
import signal

def main():
    # 1. Show countdown UI
    root = tk.Tk()
    root.title("Antigravity - Rebooting App")
    
    # Hide the root window border for a cleaner look
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    
    window_width = 450
    window_height = 100
    
    # Center the window
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width / 2) - (window_width / 2))
    y = int((screen_height / 2) - (window_height / 2))
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    # Styling
    root.configure(bg='#282a36')
    
    label = tk.Label(
        root, 
        text="Finished making changes.\nRebooting Stream Deck app in 2 seconds...", 
        font=("Segoe UI", 12, "bold"),
        fg="#f8f8f2",
        bg="#282a36"
    )
    label.pack(expand=True, fill='both', padx=20, pady=20)
    
    root.update()
    time.sleep(2)
    root.destroy()
    
    # 2. Kill the existing process
    pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streamdeck.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid_str = f.read().strip()
                if pid_str:
                    pid = int(pid_str)
                    print(f"Killing Stream Deck app with PID {pid}...")
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        # Process might already be dead
                        pass
                    time.sleep(1) # Wait for it to die and release single-instance mutex
        except Exception as e:
            print(f"Error reading or killing PID: {e}")
    else:
        print("PID file not found. Attempting to restart anyway.")
        
    # 3. Start the process again
    vbs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_streamdeck_invisible.vbs")
    print(f"Relaunching {vbs_path}...")
    os.startfile(vbs_path)

if __name__ == "__main__":
    main()
