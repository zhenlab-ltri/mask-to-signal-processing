import os
import glob
import pandas as pd
import numpy as np
import tifffile
from PIL import Image
from pathlib import Path
from ast import literal_eval
import tkinter as tk
from tkinter import filedialog, messagebox

def generate_masks_from_folders(raw_folder, unshifted_folder, shifted_folder, output_folder, output_folder2, alignment, neuron_positions, roi_padding):
    """
    Reads raw TIFFs, unshifted PNG masks, and shifted PNG masks from their respective folders.
    Generates full-frame masks using asymmetric ROI padding from the neuron's center.
    
    Args:
        roi_padding: Dictionary with keys 'left', 'right', 'top', 'bottom' containing float padding values.
    """
    # Helper function to extract the integer before '_mask.png' for numeric sorting
    def extract_frame_num(filepath):
        basename = os.path.basename(filepath)
        try:
            # Splits '10_mask.png' into '10' and converts it to an integer
            return int(basename.split('_')[0])
        except ValueError:
            return 0
    
    # Sort masks numerically using the helper function
    unshifted_files = sorted(glob.glob(os.path.join(unshifted_folder, "*.png")), key=extract_frame_num)
    shifted_files = sorted(glob.glob(os.path.join(shifted_folder, "*.png")), key=extract_frame_num)
    
    # Assuming TIFF files are properly zero-padded (e.g. frame_0001.tif). 
    raw_files = sorted(glob.glob(os.path.join(raw_folder, "*.tif*")))
    
    if len(raw_files) != len(neuron_positions) or len(raw_files) != len(unshifted_files):
        print("Warning: File counts do not match position counts.")
    
    dx, dy = alignment
    
    # Extract padding values
    p_left = roi_padding['left']
    p_right = roi_padding['right']
    p_top = roi_padding['top']
    p_bottom = roi_padding['bottom']
    
    max_frames = min(len(raw_files), len(neuron_positions), len(unshifted_files), len(shifted_files))

    for i in range(max_frames):
        print(f"Processing frame {i+1}/{max_frames}...")
        unshifted_worm_mask = np.array(Image.open(unshifted_files[i]).convert('L')) > 0
        shifted_worm_mask = np.array(Image.open(shifted_files[i]).convert('L')) > 0
        
        H, half_w = unshifted_worm_mask.shape
        
        # ---------------------------------------------------------
        # CANVAS SIZING
        # ---------------------------------------------------------
        # Assumes half_w is 1024, creating exactly a 2048-width canvas
        W_original = half_w * 2

        full_mask = np.zeros((H, W_original), dtype=np.uint8)
        x_t, y_t = neuron_positions[i]
        
        if np.isnan(x_t) or np.isnan(y_t):
            print(f"Frame {i}: Missing tracking coordinates (NaN). Outputting blank mask.")
            output_path = os.path.join(output_folder, f"{i}_full_mask.tif")
            tifffile.imwrite(output_path, full_mask)
            continue

        # ---------------------------------------------------------
        # 1. Left side (Red Channel) -> value 1
        # Uses raw [x,y] coordinates and checks against unshifted worm mask
        # ---------------------------------------------------------
        r_x_min = int(np.round(x_t - p_left))
        r_x_max = int(np.round(x_t + p_right))
        r_y_min = int(np.round(y_t - p_top))
        r_y_max = int(np.round(y_t + p_bottom))
        
        red_local_roi = np.zeros((H, half_w), dtype=np.uint8)
        
        y_start = max(0, r_y_min)
        y_end = min(H, r_y_max)
        x_start = max(0, r_x_min)
        x_end = min(half_w, r_x_max)
        
        if y_start < y_end and x_start < x_end:
            red_local_roi[y_start:y_end, x_start:x_end] = 1
            
        red_local_final = np.where(unshifted_worm_mask, red_local_roi, 0)
        
        # Place red mask in the 0 to 1024 bounds
        full_mask[:, 0:half_w] = red_local_final
        
        # ---------------------------------------------------------
        # 2. Right side (Green Channel) -> value 2
        # Subtracts alignment offset (dx, dy) to draw bounding box
        # ---------------------------------------------------------
        g_x_local = x_t - dx
        g_y_local = y_t - dy
        
        g_x_min = int(np.round(g_x_local - p_left))
        g_x_max = int(np.round(g_x_local + p_right))
        g_y_min = int(np.round(g_y_local - p_top))
        g_y_max = int(np.round(g_y_local + p_bottom))
        
        green_local_roi = np.zeros((H, half_w), dtype=np.uint8)
        
        gy_start = max(0, g_y_min)
        gy_end = min(H, g_y_max)
        gx_start = max(0, g_x_min)
        gx_end = min(half_w, g_x_max)
        
        if gy_start < gy_end and gx_start < gx_end:
            green_local_roi[gy_start:gy_end, gx_start:gx_end] = 2
            
        # Place green mask in the 1024 to 2048 bounds
        full_mask[:, half_w:W_original] = green_local_roi
        
        # ---------------------------------------------------------
        # 3. Save the generated mask
        # ---------------------------------------------------------
        output_path = os.path.join(output_folder, f"{i}_full_mask.tif")
        tifffile.imwrite(output_path, full_mask)
        
        # Create a bright visual copy for debugging
        visual_mask = full_mask.copy()
        visual_mask[full_mask == 1] = 127  # Make the Red ROI gray
        visual_mask[full_mask == 2] = 255  # Make the Green ROI white
        
        visual_path = os.path.join(output_folder2, f"{i}_VISUAL_DEBUG.png")
        Image.fromarray(visual_mask).save(visual_path)


# =========================
# GUI SETUP
# =========================
def browse_directory(entry_widget):
    """Helper to open a directory selection dialog and update an Entry widget."""
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def browse_file(entry_widget):
    """Helper to open a file selection dialog and update an Entry widget."""
    file = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    if file:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, file)

def run_processing():
    """Gathers all inputs, parses the CSV, creates output folders, and runs the mask generation."""
    raw_folder = raw_entry.get()
    unshifted_folder = unshifted_entry.get()
    shifted_folder = shifted_entry.get()
    output_folder = output_tif_entry.get()
    output_folder2 = output_png_entry.get()
    csv_path = csv_entry.get()

    # Validate Paths
    if not all([raw_folder, unshifted_folder, shifted_folder, output_folder, output_folder2, csv_path]):
        messagebox.showerror("Error", "Please fill out all folder and file paths.")
        return
        
    if not os.path.exists(csv_path):
        messagebox.showerror("Error", "The selected CSV file does not exist.")
        return

    # Validate and Parse Parameters
    try:
        dx = float(align_dx_entry.get())
        dy = float(align_dy_entry.get())
        alignment = (dx, dy)
        
        roi_padding = {
            'left': float(pad_l_entry.get()),
            'right': float(pad_r_entry.get()),
            'top': float(pad_t_entry.get()),
            'bottom': float(pad_b_entry.get())
        }
    except ValueError:
        messagebox.showerror("Error", "Alignment and Padding values must be numbers.")
        return

    # Ensure output directories exist
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(output_folder2, exist_ok=True)

    # Load neuron positions from CSV
    try:
        df = pd.read_csv(csv_path)
        neuron_coords = []
        for row in df.iloc[:, 0]:
            try:
                if isinstance(row, str) and ("nan" in row or row.strip().lower() == "nan"):
                    neuron_coords.append(np.array([np.nan, np.nan]))
                else:
                    neuron_coords.append(np.array(literal_eval(row)))
            except Exception:
                neuron_coords.append(np.array([np.nan, np.nan]))
        neuron_positions = neuron_coords
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read CSV file:\n{str(e)}")
        return

    # Run the main generation script
    try:
        generate_masks_from_folders(
            raw_folder, unshifted_folder, shifted_folder, 
            output_folder, output_folder2, 
            alignment, neuron_positions, roi_padding
        )
        messagebox.showinfo("Success", "Mask generation complete!")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during processing:\n{str(e)}")


if __name__ == '__main__':
    root = tk.Tk()
    root.title("Full-Frame Mask Generator")
    root.geometry("650x450")
    root.resizable(False, False)

    padx = 10
    pady = 5

    # --- Path Selection Rows ---
    tk.Label(root, text="Raw TIFF Folder:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    raw_entry = tk.Entry(root, width=50)
    raw_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(raw_entry)).grid(row=0, column=2, padx=padx)

    tk.Label(root, text="Unshifted Masks Folder:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    unshifted_entry = tk.Entry(root, width=50)
    unshifted_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(unshifted_entry)).grid(row=1, column=2, padx=padx)

    tk.Label(root, text="Shifted Masks Folder:").grid(row=2, column=0, padx=padx, pady=pady, sticky="e")
    shifted_entry = tk.Entry(root, width=50)
    shifted_entry.grid(row=2, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(shifted_entry)).grid(row=2, column=2, padx=padx)

    tk.Label(root, text="Output TIF Folder:").grid(row=3, column=0, padx=padx, pady=pady, sticky="e")
    output_tif_entry = tk.Entry(root, width=50)
    output_tif_entry.grid(row=3, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(output_tif_entry)).grid(row=3, column=2, padx=padx)

    tk.Label(root, text="Output PNG (Debug) Folder:").grid(row=4, column=0, padx=padx, pady=pady, sticky="e")
    output_png_entry = tk.Entry(root, width=50)
    output_png_entry.grid(row=4, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(output_png_entry)).grid(row=4, column=2, padx=padx)

    tk.Label(root, text="Positions CSV File:").grid(row=5, column=0, padx=padx, pady=pady, sticky="e")
    csv_entry = tk.Entry(root, width=50)
    csv_entry.grid(row=5, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_file(csv_entry)).grid(row=5, column=2, padx=padx)

    # --- Parameters Frame ---
    param_frame = tk.LabelFrame(root, text="Parameters")
    param_frame.grid(row=6, column=0, columnspan=3, padx=padx, pady=15, sticky="ew")

    # Alignment
    tk.Label(param_frame, text="Alignment (dx, dy):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
    align_dx_entry = tk.Entry(param_frame, width=8)
    align_dx_entry.insert(0, "-20")
    align_dx_entry.grid(row=0, column=1, padx=2, pady=5)
    
    align_dy_entry = tk.Entry(param_frame, width=8)
    align_dy_entry.insert(0, "-15")
    align_dy_entry.grid(row=0, column=2, padx=2, pady=5)

    # Padding
    tk.Label(param_frame, text="Padding (L, R, T, B):").grid(row=0, column=3, padx=(20, 5), pady=5, sticky="e")
    
    pad_l_entry = tk.Entry(param_frame, width=6)
    pad_l_entry.insert(0, "28.22")
    pad_l_entry.grid(row=0, column=4, padx=2)
    
    pad_r_entry = tk.Entry(param_frame, width=6)
    pad_r_entry.insert(0, "25.82")
    pad_r_entry.grid(row=0, column=5, padx=2)
    
    pad_t_entry = tk.Entry(param_frame, width=6)
    pad_t_entry.insert(0, "19.87")
    pad_t_entry.grid(row=0, column=6, padx=2)
    
    pad_b_entry = tk.Entry(param_frame, width=6)
    pad_b_entry.insert(0, "29.82")
    pad_b_entry.grid(row=0, column=7, padx=2)

    # --- Run Button ---
    run_btn = tk.Button(root, text="Generate Masks", command=run_processing, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"))
    run_btn.grid(row=7, column=0, columnspan=3, pady=10)

    root.mainloop()