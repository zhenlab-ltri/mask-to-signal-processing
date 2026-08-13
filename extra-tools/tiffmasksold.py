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

# ==========================================
# CORE PROCESSING LOGIC
# ==========================================
def generate_masks_from_folders(raw_folder, unshifted_folder, shifted_folder, output_folder, output_folder2, alignment, neuron_positions, roi_padding, status_label, root):
    # Ensure output directories exist
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(output_folder2, exist_ok=True)

    def extract_frame_num(filepath):
        basename = os.path.basename(filepath)
        try:
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
    p_left = roi_padding['left']
    p_right = roi_padding['right']
    p_top = roi_padding['top']
    p_bottom = roi_padding['bottom']
    
    max_frames = min(len(raw_files), len(neuron_positions), len(unshifted_files), len(shifted_files))

    if max_frames == 0:
        raise ValueError("No frames to process. Please check if your folders contain files and your CSV is correct.")

    for i in range(max_frames):
        # Update GUI Status
        status_label.config(text=f"Processing frame {i+1} / {max_frames}...")
        root.update()

        print(f"Processing frame {i+1}/{max_frames}...")
        unshifted_worm_mask = np.array(Image.open(unshifted_files[i]).convert('L')) > 0
        shifted_worm_mask = np.array(Image.open(shifted_files[i]).convert('L')) > 0
        
        H, half_w = unshifted_worm_mask.shape
        # ---------------------------------------------------------
        # PADDING DEFINITIONS FOR THE UNCROPPED 2048 CANVAS
        # ---------------------------------------------------------
        W_original = 2048
        half_original = 1024
        pad_width = 108  # The x=0 to 108 crop

        full_mask = np.zeros((H, W_original), dtype=np.uint8)
        x_t, y_t = neuron_positions[i]
        
        if np.isnan(x_t) or np.isnan(y_t):
            print(f"Frame {i}: Missing tracking coordinates (NaN). Outputting blank mask.")
            output_path = os.path.join(output_folder, f"{i}_full_mask.tif")
            tifffile.imwrite(output_path, full_mask)
            continue

        # ---------------------------------------------------------
        # 1. Right side (Green Channel) -> value 2
        # Asymmetric bounds using the tracking coordinate
        # ---------------------------------------------------------
        g_x_min = max(0, int(np.round(x_t - p_left)))
        g_x_max = min(half_w, int(np.round(x_t + p_right)))
        g_y_min = max(0, int(np.round(y_t - p_top)))
        g_y_max = min(H, int(np.round(y_t + p_bottom)))
        
        green_local_roi = np.zeros((H, half_w), dtype=np.uint8)
        
        if g_y_min < g_y_max and g_x_min < g_x_max:
            green_local_roi[g_y_min:g_y_max, g_x_min:g_x_max] = 2
            
        full_mask[:, half_original + pad_width : W_original] = green_local_roi
        
        # ---------------------------------------------------------
        # 2. Left side (Red Channel) -> value 1
        # Asymmetric bounds using the unshifted coordinate
        # ---------------------------------------------------------
        r_x_local = x_t - dx
        r_y_local = y_t - dy
        
        r_x_min = int(np.round(r_x_local - p_left))
        r_x_max = int(np.round(r_x_local + p_right))
        r_y_min = int(np.round(r_y_local - p_top))
        r_y_max = int(np.round(r_y_local + p_bottom))
        
        red_local_roi = np.zeros((H, half_w), dtype=np.uint8)
        
        y_start = max(0, r_y_min)
        y_end = min(H, r_y_max)
        x_start = max(0, r_x_min)
        x_end = min(half_w, r_x_max)
        
        if y_start < y_end and x_start < x_end:
            red_local_roi[y_start:y_end, x_start:x_end] = 1
            
        red_local_final = np.where(unshifted_worm_mask, red_local_roi, 0)
        full_mask[:, pad_width:half_original] = red_local_final
        
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


# ==========================================
# GUI SETUP
# ==========================================
def browse_folder(entry_widget):
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def browse_file(entry_widget):
    filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
    if filepath:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, filepath)

def run_process():
    # Gather Directory Inputs
    raw_folder = entry_raw.get()
    unshifted_folder = entry_unshifted.get()
    shifted_folder = entry_shifted.get()
    output_folder = entry_out_tif.get()
    output_folder2 = entry_out_png.get()
    csv_path = entry_csv.get()

    if not all([raw_folder, unshifted_folder, shifted_folder, output_folder, output_folder2, csv_path]):
        messagebox.showerror("Error", "Please fill out all file and directory paths.")
        return

    # Gather Alignment Inputs
    try:
        dx = float(entry_dx.get())
        dy = float(entry_dy.get())
        alignment = (dx, dy)
    except ValueError:
        messagebox.showerror("Error", "Alignment dx and dy must be numbers.")
        return

    # Gather Padding Inputs
    try:
        roi_padding = {
            'left': float(entry_left.get()),
            'right': float(entry_right.get()),
            'top': float(entry_top.get()),
            'bottom': float(entry_bottom.get())
        }
    except ValueError:
        messagebox.showerror("Error", "ROI padding values must be numbers.")
        return

    # Load CSV
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
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read CSV:\n{e}")
        return

    # Lock button and start
    btn_run.config(state=tk.DISABLED, text="Processing...")
    lbl_status.config(text="Starting...", fg="blue")
    root.update()

    try:
        generate_masks_from_folders(
            raw_folder, unshifted_folder, shifted_folder, 
            output_folder, output_folder2, alignment, 
            neuron_coords, roi_padding, lbl_status, root
        )
        lbl_status.config(text="Finished successfully!", fg="green")
        messagebox.showinfo("Success", "Mask generation complete!")
    except Exception as e:
        lbl_status.config(text="Error occurred.", fg="red")
        messagebox.showerror("Error", f"An error occurred during processing:\n{e}")
    finally:
        btn_run.config(state=tk.NORMAL, text="Generate Masks")


# Build Window
root = tk.Tk()
root.title("Full Frame Mask Generator")
root.geometry("680x480")
root.resizable(False, False)

padx, pady = 10, 5

# --- Frame 1: Paths ---
frame_paths = tk.LabelFrame(root, text="Directories & Files", padx=10, pady=10)
frame_paths.pack(fill="x", padx=10, pady=5)

paths_info = [
    ("Raw TIFF Folder:", "entry_raw"),
    ("Unshifted PNG Folder:", "entry_unshifted"),
    ("Shifted PNG Folder:", "entry_shifted"),
    ("Output TIFF Folder:", "entry_out_tif"),
    ("Output PNG (Debug):", "entry_out_png"),
    ("Neuron CSV Path:", "entry_csv")
]

entries = {}
for i, (label_text, var_name) in enumerate(paths_info):
    tk.Label(frame_paths, text=label_text).grid(row=i, column=0, sticky="e", pady=2)
    entry = tk.Entry(frame_paths, width=60)
    entry.grid(row=i, column=1, padx=5, pady=2)
    
    if "CSV" in label_text:
        btn = tk.Button(frame_paths, text="Browse", command=lambda e=entry: browse_file(e))
    else:
        btn = tk.Button(frame_paths, text="Browse", command=lambda e=entry: browse_folder(e))
    btn.grid(row=i, column=2, pady=2)
    entries[var_name] = entry

# Assign dynamically created entries to global variables for easy access
entry_raw = entries["entry_raw"]
entry_unshifted = entries["entry_unshifted"]
entry_shifted = entries["entry_shifted"]
entry_out_tif = entries["entry_out_tif"]
entry_out_png = entries["entry_out_png"]
entry_csv = entries["entry_csv"]

# --- Frame 2: Settings (Alignment & Padding) ---
frame_settings = tk.Frame(root)
frame_settings.pack(fill="x", padx=10, pady=5)

# Alignment Box
frame_align = tk.LabelFrame(frame_settings, text="Alignment (dx, dy)", padx=10, pady=10)
frame_align.pack(side="left", fill="both", expand=True, padx=(0, 5))

tk.Label(frame_align, text="dx:").grid(row=0, column=0, sticky="e")
entry_dx = tk.Entry(frame_align, width=10)
entry_dx.insert(0, "-20")
entry_dx.grid(row=0, column=1, padx=5)

tk.Label(frame_align, text="dy:").grid(row=1, column=0, sticky="e", pady=5)
entry_dy = tk.Entry(frame_align, width=10)
entry_dy.insert(0, "-15")
entry_dy.grid(row=1, column=1, padx=5, pady=5)

# Padding Box
frame_pad = tk.LabelFrame(frame_settings, text="ROI Padding", padx=10, pady=10)
frame_pad.pack(side="right", fill="both", expand=True, padx=(5, 0))

tk.Label(frame_pad, text="Left:").grid(row=0, column=0, sticky="e")
entry_left = tk.Entry(frame_pad, width=8)
entry_left.insert(0, "28.22")
entry_left.grid(row=0, column=1, padx=5)

tk.Label(frame_pad, text="Right:").grid(row=0, column=2, sticky="e")
entry_right = tk.Entry(frame_pad, width=8)
entry_right.insert(0, "25.82")
entry_right.grid(row=0, column=3, padx=5)

tk.Label(frame_pad, text="Top:").grid(row=1, column=0, sticky="e", pady=5)
entry_top = tk.Entry(frame_pad, width=8)
entry_top.insert(0, "19.87")
entry_top.grid(row=1, column=1, padx=5, pady=5)

tk.Label(frame_pad, text="Bottom:").grid(row=1, column=2, sticky="e", pady=5)
entry_bottom = tk.Entry(frame_pad, width=8)
entry_bottom.insert(0, "29.82")
entry_bottom.grid(row=1, column=3, padx=5, pady=5)

# --- Frame 3: Run & Status ---
frame_run = tk.Frame(root)
frame_run.pack(fill="x", padx=10, pady=10)

btn_run = tk.Button(frame_run, text="Generate Masks", command=run_process, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=20)
btn_run.pack(pady=5)

lbl_status = tk.Label(frame_run, text="Waiting for input...", font=("Arial", 10))
lbl_status.pack()

root.mainloop()