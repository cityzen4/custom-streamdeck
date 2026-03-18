from PIL import Image
import sys
import os

def convert_to_ico(input_path, output_path):
    img = Image.open(input_path)
    # Windows icons usually include several sizes
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(output_path, sizes=icon_sizes)
    print(f"Successfully converted {input_path} to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_icon.py <input_png> <output_ico>")
        sys.exit(1)
    
    convert_to_ico(sys.argv[1], sys.argv[2])
