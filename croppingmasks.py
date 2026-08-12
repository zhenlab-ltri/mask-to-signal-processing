import os
import re
import time
import numpy as np
from PIL import Image
import cv2
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def keep_largest_blob(binary):
    bw = (binary * 255).astype('uint8')
    _, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    if labels.max() == 0:
        return bw
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest_lbl = areas.argmax() + 1
    return (labels == largest_lbl).astype('uint8') * 255

def split_img(img, side):
    # split img in half vertically
    h, w = img.shape
    if side == 'left':
        return img[:, :w//2]
    else:
        return img[:, w//2:]

# ==========================================
# MAIN PROCESSING LOGIC
# ==========================================
def process_masks(input_dir, output_dir, chosen_side):
    start_time = time.time()
    
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory '{input_dir}' does not exist.")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nScanning directory: {input_dir}")

    # 1. Filter and extract the index only for files that actually start with numbers
    valid_files = []
    for f in os.listdir(input_dir):
        match = re.search(r'^(\d+)', f)
        if match and f.endswith('.png'):
            valid_files.append((int(match.group(1)), f))

    if not valid_files:
        raise ValueError(f"No valid PNG masks starting with a number were found in {input_dir}.")

    # 2. Sort safely by the integer frame index
    valid_files.sort(key=lambda x: x[0])

    # 3. Clean up: extract JUST the filename strings
    png_files = [item[1] for item in valid_files]

    print(f"Found {len(png_files)} masks (Frames {png_files[0]} to {png_files[-1]}). Starting crop...")

    processed_count = 0

    for filename in tqdm(png_files, desc="Cropping Masks"):
        try:
            # Open and convert to grayscale
            img_pil = Image.open(os.path.join(input_dir, filename)).convert('L')
            img_gray = np.array(img_pil)

            # Apply binary threshold (> 10) to clean up PNG artifacts
            binary_mask = (img_gray > 10).astype(np.uint8)
            binary_mask = keep_largest_blob(binary_mask)
            binary_mask = split_img(binary_mask, side=chosen_side)  # take chosen half

            # Get the frame index from filename (e.g., "2001.png" -> "2001")
            frame_index = filename.replace('.png', '')

            # Save as PNG to output folder
            output_filename = f"{frame_index}.png"
            output_path = os.path.join(output_dir, output_filename)

            Image.fromarray(binary_mask, mode='L').save(output_path)
            processed_count += 1
        except Exception as e:
            tqdm.write(f"Error processing {filename}: {e}")

    total_time = time.time() - start_time
    return processed_count, total_time


# ==========================================
# GUI SETUP
# ==========================================
def browse_directory(entry_widget):
    """Helper to open a directory selection dialog and update an Entry widget."""
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def run_script():
    """Gathers paths from GUI and runs the processing logic."""
    input_dir = input_entry.get()
    output_dir = output_entry.get()
    chosen_side = side_combobox.get()

    if not input_dir or not output_dir:
        messagebox.showerror("Error", "Please select both the input and output directories.")
        return
        
    if chosen_side not in ['left', 'right']:
        messagebox.showerror("Error", "Please select a valid side to crop ('left' or 'right').")
        return

    # Disable button to prevent multiple clicks
    run_btn.config(state=tk.DISABLED, text="Processing...")
    root.update()

    try:
        count, elapsed_time = process_masks(input_dir, output_dir, chosen_side)
        messagebox.showinfo(
            "Success", 
            f"Done! Processed {count} masks successfully.\n\n"
            f"Saved to:\n{output_dir}\n\n"
            f"Total time: {elapsed_time:.2f} seconds."
        )
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
    finally:
        # Re-enable button
        run_btn.config(state=tk.NORMAL, text="Crop & Convert Masks")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Mask Cropper")
    root.geometry("550x220")
    root.resizable(False, False)

    padx = 10
    pady = 10

    # Input Directory
    tk.Label(root, text="Input Masks Folder (PNGs):").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    input_entry = tk.Entry(root, width=42)
    input_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(input_entry)).grid(row=0, column=2, padx=padx)

    # Output Directory
    tk.Label(root, text="Output Folder (PNGs):").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    output_entry = tk.Entry(root, width=42)
    output_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(output_entry)).grid(row=1, column=2, padx=padx)

    # Side Selection
    tk.Label(root, text="Crop Half:").grid(row=2, column=0, padx=padx, pady=pady, sticky="e")
    side_combobox = ttk.Combobox(root, values=["left", "right"], state="readonly", width=15)
    side_combobox.set("left")  # Set default value
    side_combobox.grid(row=2, column=1, sticky="w", padx=padx, pady=pady)

    # Run Button
    run_btn = tk.Button(root, text="Crop & Convert Masks", command=run_script, bg="#2196F3", fg="white", font=("Arial", 10, "bold"))
    run_btn.grid(row=3, column=0, columnspan=3, pady=10)

    root.mainloop()