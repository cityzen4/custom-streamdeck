import os
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from PIL import Image, ImageDraw, ImageFont

def get_deck():
    """Initializes and returns the first StreamDeck found."""
    streamdecks = DeviceManager().enumerate()
    if not streamdecks:
        print("No StreamDeck found.")
        return None
    
    deck = streamdecks[0]
    deck.open()
    deck.reset()
    return deck

def render_key_image(deck, icon_img, label):
    """Creates a button image with an icon and label."""
    image = PILHelper.create_key_image(deck)
    draw = ImageDraw.Draw(image)
    
    full_width, full_height = image.size
    
    # Resize icon to fit partly in the button
    icon_size = (int(full_width * 0.7), int(full_height * 0.7))
    if icon_img:
        # If the icon has alpha, we need to handle it
        if icon_img.mode != 'RGBA':
            icon_img = icon_img.convert('RGBA')
        icon_img = icon_img.resize(icon_size, Image.LANCZOS)
    else:
        # Placeholder if no icon
        icon_img = Image.new("RGBA", icon_size, (30, 30, 30, 255))

    # Draw icon centered in the upper part
    paste_x = (full_width - icon_size[0]) // 2
    paste_y = (full_height - icon_size[1]) // 2 - 5 # Shift up slightly for label
    image.paste(icon_img, (paste_x, paste_y), icon_img)
    
    # Draw label at the bottom
    try:
        font = ImageFont.truetype("arial.ttf", 10)
    except:
        font = ImageFont.load_default()
        
    w, h = draw.textsize(label) if hasattr(draw, 'textsize') else (0, 0) # Fallback for newer Pillow
    # Newer pillow use textbbox
    if hasattr(draw, 'textbbox'):
        bbox = draw.textbbox((0, 0), label, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    draw.text(((image.width - w) // 2, image.height - h - 5), label, font=font, fill="white")
    
    return PILHelper.to_native_key_format(deck, image)

def update_deck_buttons(deck, windows, special_key_index=-1):
    """Updates the deck buttons based on the current window list, reserving one for a special action."""
    num_keys = deck.key_count()
    
    # Load special icon once
    tab_icon = None
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tab_switcher_icon.png")
    if os.path.exists(icon_path):
        try:
            tab_icon = Image.open(icon_path)
        except: pass

    for key_idx in range(num_keys):
        if key_idx == special_key_index:
            # Render the special Tab Toggle button
            image = render_key_image(deck, tab_icon, "Tab Toggle")
            deck.set_key_image(key_idx, image)
            continue

        # Adjust window index if we're past the special key
        win_idx = key_idx
        if special_key_index != -1 and key_idx > special_key_index:
            win_idx = key_idx - 1
            
        if win_idx < len(windows):
            win = windows[win_idx]
            icon = win.get('icon')
            label = win['title'][:10] + "..." if len(win['title']) > 10 else win['title']
            image = render_key_image(deck, icon, label)
            deck.set_key_image(key_idx, image)
        else:
            # Clear unused keys
            deck.set_key_image(key_idx, PILHelper.to_native_key_format(deck, PILHelper.create_key_image(deck)))
