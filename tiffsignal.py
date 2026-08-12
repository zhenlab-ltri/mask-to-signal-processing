import os
import glob
import re
import numpy as np
import tifffile
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
import tkinter as tk
from tkinter import filedialog, messagebox

def extract_frame_num(filepath):
    """
    Finds all numbers in the filename and grabs the LAST one.
    This prevents dates in the folder/file name (like 11122024) from ruining the sort.
    """
    basename = os.path.basename(filepath)
    numbers = re.findall(r'\d+', basename)
    return int(numbers[-1]) if numbers else -1

def summarize_mask_pixels(pixels):
    """
    Return the total signal inside the mask and the total signal from the
    brightest 95% of pixels in that masked region.
    """
    if pixels.size == 0:
        return 0.0, 0.0

    total_intensity = float(np.sum(pixels))

    # Keep the brightest 95% of pixels by intensity.
    keep_count = max(1, int(np.floor(0.95 * pixels.size)))
    sorted_pixels = np.sort(pixels)
    top95_intensity = float(np.sum(sorted_pixels[-keep_count:]))

    return total_intensity, top95_intensity


def process_single_frame(raw_path, mask_path, frame_num):
    """
    Worker function to process a single pair of files. 
    Designed to run in parallel across multiple CPU cores.
    """
    try:
        # Load the mask
        mask = tifffile.imread(mask_path)
        
        # Use memmap for lazy loading (drastically speeds up reading if TIFFs are uncompressed)
        # If your TIFFs are compressed, tifffile will automatically fall back to standard reading
        try:
            frame = np.squeeze(tifffile.memmap(raw_path, mode='r'))
        except ValueError:
            frame = np.squeeze(tifffile.imread(raw_path))

        # Check dimensions
        if frame.shape != mask.shape:
            return frame_num, None, None, None, None, f"Shape mismatch: Raw {frame.shape} vs Mask {mask.shape}"
            
        # Extract Green signal (Right side, where mask == 2)
        green_pixels = frame[mask == 2]
        green_total, green_top95 = summarize_mask_pixels(green_pixels)
        
        # Extract Red signal (Left side, where mask == 1)
        red_pixels = frame[mask == 1]
        red_total, red_top95 = summarize_mask_pixels(red_pixels)
        
        return frame_num, red_total, green_total, red_top95, green_top95, None

    except Exception as e:
        return frame_num, None, None, None, None, str(e)

def extract_signals_parallel(raw_folder, mask_folder, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    # Grab files
    raw_files = glob.glob(os.path.join(raw_folder, "*.tif*"))
    mask_files = glob.glob(os.path.join(mask_folder, "*_full_mask.tif"))
    
    # Map them strictly by frame number
    raw_dict = {extract_frame_num(f): f for f in raw_files if extract_frame_num(f) != -1}
    mask_dict = {extract_frame_num(f): f for f in mask_files if extract_frame_num(f) != -1}
    
    # Find frames that exist in BOTH folders
    common_frames = sorted(list(set(raw_dict.keys()).intersection(set(mask_dict.keys()))))
    
    print(f"Found {len(raw_files)} raw TIFFs and {len(mask_files)} mask files.")
    print(f"Successfully matched {len(common_frames)} pairs. Starting parallel extraction...")
    
    if not common_frames:
        raise ValueError("No matching frames found between raw TIFFs and mask files.")

    results = []
    
    # Run the extraction across multiple CPU cores
    with ProcessPoolExecutor() as executor:
        # Submit all tasks to the processor pool
        futures = {
            executor.submit(process_single_frame, raw_dict[f_num], mask_dict[f_num], f_num): f_num 
            for f_num in common_frames
        }
        
        completed_count = 0
        total_frames = len(common_frames)
        
        # Gather results as they finish
        for future in as_completed(futures):
            frame_num, red_total, green_total, red_top95, green_top95, error = future.result()
            
            if error:
                print(f"Error on Frame {frame_num}: {error}")
            else:
                results.append((frame_num, red_total, green_total, red_top95, green_top95))
                
            completed_count += 1
            if completed_count % 100 == 0 or completed_count == total_frames:
                print(f"Processed {completed_count}/{total_frames} frames...")
                
    # The parallel processor finishes tasks out of order, so we sort the final list
    results = sorted(results, key=lambda x: x[0])
    
    # Split the tuples back into columns
    frames = [r[0] for r in results]
    reds = [r[1] for r in results]
    greens = [r[2] for r in results]
    red_top95s = [r[3] for r in results]
    green_top95s = [r[4] for r in results]
    
    # Save total-intensity results to CSV
    df = pd.DataFrame({
        'Frame': frames,
        'Red_Intensity': reds,
        'Green_Intensity': greens
    })
    
    csv_path = os.path.join(output_dir, "extracted_signals_total.csv")
    df.to_csv(csv_path, index=False)

    # Save the brightest-95% results to a separate CSV
    top95_df = pd.DataFrame({
        'Frame': frames,
        'Red_Intensity': red_top95s,
        'Green_Intensity': green_top95s
    })

    top95_csv_path = os.path.join(output_dir, "extracted_signals_top95.csv")
    top95_df.to_csv(top95_csv_path, index=False)
    
    print(f"\nExtraction complete! Saved total-intensity data for {len(results)} frames to {csv_path}")
    print(f"Saved brightest-95% data for {len(results)} frames to {top95_csv_path}")
    
    # Return metrics for the GUI message box
    return len(results), csv_path, top95_csv_path

# =========================
# GUI SETUP
# =========================
def browse_directory(entry_widget):
    """Helper to open a directory selection dialog and update an Entry widget."""
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def run_extraction():
    """Gathers paths from the GUI, validates them, and runs the parallel extraction script."""
    raw_folder = raw_entry.get()
    mask_folder = mask_entry.get()
    output_dir = output_entry.get()

    if not all([raw_folder, mask_folder, output_dir]):
        messagebox.showerror("Error", "Please select all three directories.")
        return
        
    if not os.path.exists(raw_folder) or not os.path.exists(mask_folder):
        messagebox.showerror("Error", "One or both input folders do not exist.")
        return

    # Disable button to prevent multiple clicks
    run_btn.config(state=tk.DISABLED, text="Processing...")
    root.update()

    try:
        count, path_total, path_top95 = extract_signals_parallel(raw_folder, mask_folder, output_dir)
        messagebox.showinfo(
            "Success", 
            f"Extraction complete for {count} frames!\n\n"
            f"Total Intensity CSV:\n{path_total}\n\n"
            f"Top 95% Intensity CSV:\n{path_top95}"
        )
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during extraction:\n{str(e)}")
    finally:
        # Re-enable button
        run_btn.config(state=tk.NORMAL, text="Extract Signals")


if __name__ == "__main__":
    # The __main__ block is strictly required on Windows when using ProcessPoolExecutor
    # to prevent child processes from endlessly spawning new GUIs.
    root = tk.Tk()
    root.title("TIFF Signal Extractor")
    root.geometry("600x180")
    root.resizable(False, False)

    padx = 10
    pady = 10

    # Raw TIFF Folder
    tk.Label(root, text="Raw TIFF Folder:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    raw_entry = tk.Entry(root, width=50)
    raw_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(raw_entry)).grid(row=0, column=2, padx=padx, pady=pady)

    # Mask Folder
    tk.Label(root, text="Mask TIFF Folder:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    mask_entry = tk.Entry(root, width=50)
    mask_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(mask_entry)).grid(row=1, column=2, padx=padx, pady=pady)

    # Output Folder
    tk.Label(root, text="Output Folder:").grid(row=2, column=0, padx=padx, pady=pady, sticky="e")
    output_entry = tk.Entry(root, width=50)
    output_entry.grid(row=2, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(output_entry)).grid(row=2, column=2, padx=padx, pady=pady)

    # Extract Button
    run_btn = tk.Button(root, text="Extract Signals", command=run_extraction, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
    run_btn.grid(row=3, column=0, columnspan=3, pady=5)

    root.mainloop()