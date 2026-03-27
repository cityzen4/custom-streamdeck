import os
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from PIL import Image, ImageDraw, ImageFont

# Global cache for performance
_RESOURCE_CACHE = {
    'font': None,
    'tab_icon': None,
    'last_keys': {} # deck_id -> {key_index: image_hash}
}

def _get_font():
    if _RESOURCE_CACHE['font'] is None:
        try:
            _RESOURCE_CACHE['font'] = ImageFont.truetype("arial.ttf", 10)
        except:
            _RESOURCE_CACHE['font'] = ImageFont.load_default()
    return _RESOURCE_CACHE['font']

def _get_tab_icon():
    if _RESOURCE_CACHE['tab_icon'] is None:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tab_switcher_icon.png")
        if os.path.exists(icon_path):
            try:
                _RESOURCE_CACHE['tab_icon'] = Image.open(icon_path)
            except: pass
    return _RESOURCE_CACHE['tab_icon']

def get_deck(model_filter=None, serial_filter=None):
    """
    Initializes and returns the first StreamDeck found that matches the filters.
    :param model_filter: Partial or full model name (e.g. "Stream Deck XL")
    :param serial_filter: Exact serial number
    """
    streamdecks = DeviceManager().enumerate()
    
    for deck in streamdecks:
        # Check model filter
        if model_filter and model_filter.lower() not in deck.deck_type().lower():
            continue
            
        # Check serial filter (requires opening the deck briefly)
        if serial_filter:
            try:
                deck.open()
                serial = deck.get_serial_number()
                deck.close()
                if serial != serial_filter:
                    continue
            except:
                continue
                
        # If we get here, it matches
        try:
            deck.open()
            deck.reset()
            return deck
        except Exception as e:
            print(f"Error opening deck: {e}")
            continue

    print("No matching StreamDeck found.")
    return None

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
    font = _get_font()
        
    try:
        # Newer pillow use textbbox
        if hasattr(draw, 'textbbox'):
            bbox = draw.textbbox((0, 0), label, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        else:
            w, h = draw.textsize(label)
    except:
        w, h = 0, 0

    draw.text(((image.width - w) // 2, image.height - h - 5), label, font=font, fill="white")
    
    return PILHelper.to_native_key_format(deck, image)

def update_deck_buttons(deck, windows, special_key_index=-1, reset_key_index=-1, max_window_keys=24):
    """Updates the deck buttons based on the current window list, reserving one for a special action."""
    num_keys = deck.key_count()
    deck_id = deck.id()
    
    if deck_id not in _RESOURCE_CACHE['last_keys']:
        _RESOURCE_CACHE['last_keys'][deck_id] = {}

    tab_icon = _get_tab_icon()
    last_keys = _RESOURCE_CACHE['last_keys'][deck_id]

    for key_idx in range(num_keys):
        image = None
        key_content_id = None # Used for caching

        if key_idx == special_key_index:
            key_content_id = f"special_{special_key_index}"
            if last_keys.get(key_idx) != key_content_id:
                image = render_key_image(deck, tab_icon, "Tab Toggle")
        
        elif key_idx == reset_key_index:
            key_content_id = f"reset_{reset_key_index}"
            if last_keys.get(key_idx) != key_content_id:
                red_icon = Image.new("RGBA", (100, 100), (180, 0, 0, 255))
                image = render_key_image(deck, red_icon, "Reset App")
        
        elif key_idx < max_window_keys:
            win_idx = key_idx
            if win_idx < len(windows):
                win = windows[win_idx]
                title = win.get('title', win.get('name', 'Unknown'))
                # Content ID includes title and whether icon exists (approximate for performance)
                key_content_id = f"win_{win_idx}_{title}"
                if last_keys.get(key_idx) != key_content_id:
                    icon = win.get('icon')
                    label = title[:10] + "..." if len(title) > 10 else title
                    image = render_key_image(deck, icon, label)
            else:
                key_content_id = "blank_win"
                if last_keys.get(key_idx) != key_content_id:
                    image = PILHelper.to_native_key_format(deck, PILHelper.create_key_image(deck))
        else:
            key_content_id = "blank_other"
            if last_keys.get(key_idx) != key_content_id:
                image = PILHelper.to_native_key_format(deck, PILHelper.create_key_image(deck))

        # Only update if image was rendered (meaning content ID changed)
        if image:
            deck.set_key_image(key_idx, image)
            last_keys[key_idx] = key_content_id
