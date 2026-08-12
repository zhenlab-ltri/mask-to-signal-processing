import os
import glob
import re
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox

# ==========================================
# PROCESSING LOGIC
# ==========================================
def extract_frame_num(filepath):
    """Extracts the first integer found in the filename to identify the frame."""
    basename = os.path.basename(filepath)
    numbers = re.findall(r'\d+', basename)
    return int(numbers[0]) if numbers else -1

def combine_mask_folders(folder_a, folder_b, output_dir):
    """Finds matching masks in two folders, combines them, and saves the output."""
    os.makedirs(output_dir, exist_ok=True)

    # Grab PNG files from both folders
    files_a = glob.glob(os.path.join(folder_a, "*.png"))
    files_b = glob.glob(os.path.join(folder_b, "*.png"))

    if not files_a or not files_b:
        raise ValueError("One or both input folders do not contain any PNG files.")

    # Map them strictly by frame number
    dict_a = {extract_frame_num(f): f for f in files_a if extract_frame_num(f) != -1}
    dict_b = {extract_frame_num(f): f for f in files_b if extract_frame_num(f) != -1}

    # Find frames that exist in BOTH folders
    common_frames = sorted(list(set(dict_a.keys()).intersection(set(dict_b.keys()))))

    if not common_frames:
        raise ValueError("No matching frame numbers found between the two folders.")

    print(f"Found {len(common_frames)} matching mask pairs. Starting combination...")

    processed_count = 0
    error_count = 0

    for f_num in common_frames:
        path_a = dict_a[f_num]
        path_b = dict_b[f_num]

        # Read images in grayscale
        img_a = cv2.imread(path_a, cv2.IMREAD_GRAYSCALE)
        img_b = cv2.imread(path_b, cv2.IMREAD_GRAYSCALE)

        if img_a is None or img_b is None:
            print(f"Warning: Failed to read frame {f_num}. Skipping.")
            error_count += 1
            continue

        # Check if dimensions match
        if img_a.shape != img_b.shape:
            print(f"Warning: Shape mismatch on frame {f_num} ({img_a.shape} vs {img_b.shape}). Skipping.")
            error_count += 1
            continue

        # Combine masks: bitwise_or keeps white pixels from both masks
        combined_mask = cv2.bitwise_or(img_a, img_b)

        # Ensure it remains strictly binary (0 or 255)
        _, binary_mask = cv2.threshold(combined_mask, 127, 255, cv2.THRESH_BINARY)

        # Save to output folder maintaining the original naming convention
        out_name = f"{f_num}_mask.png"
        out_path = os.path.join(output_dir, out_name)
        cv2.imwrite(out_path, binary_mask)
        
        processed_count += 1

    return processed_count, error_count

# ==========================================
# GUI SETUP
# ==========================================
def browse_directory(entry_widget):
    """Helper to open a directory selection dialog and update an Entry widget."""
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def run_combination():
    """Gathers paths from the GUI, validates them, and runs the combination logic."""
    folder_a = folder_a_entry.get()
    folder_b = folder_b_entry.get()
    output_dir = output_entry.get()

    # Validate inputs
    if not all([folder_a, folder_b, output_dir]):
        messagebox.showerror("Error", "Please select all three directories.")
        return

    if not os.path.exists(folder_a) or not os.path.exists(folder_b):
        messagebox.showerror("Error", "One or both of the selected input folders do not exist.")
        return

    # Disable button to prevent multiple clicks
    run_btn.config(state=tk.DISABLED, text="Processing...")
    root.update()

    try:
        processed, errors = combine_mask_folders(folder_a, folder_b, output_dir)
        
        msg = f"Combination complete!\n\nSuccessfully combined: {processed} pairs."
        if errors > 0:
            msg += f"\nSkipped due to errors: {errors} pairs (check console)."
            
        messagebox.showinfo("Success", msg)
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
    finally:
        # Re-enable button
        run_btn.config(state=tk.NORMAL, text="Combine Masks")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Mask Combiner")
    root.geometry("550x200")
    root.resizable(False, False)

    padx = 10
    pady = 10

    # Folder A Row
    tk.Label(root, text="Input Folder A:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    folder_a_entry = tk.Entry(root, width=45)
    folder_a_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(folder_a_entry)).grid(row=0, column=2, padx=padx)

    # Folder B Row
    tk.Label(root, text="Input Folder B:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    folder_b_entry = tk.Entry(root, width=45)
    folder_b_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(folder_b_entry)).grid(row=1, column=2, padx=padx)

    # Output Folder Row
    tk.Label(root, text="Output Folder:").grid(row=2, column=0, padx=padx, pady=pady, sticky="e")
    output_entry = tk.Entry(root, width=45)
    output_entry.grid(row=2, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(output_entry)).grid(row=2, column=2, padx=padx)

    # Combine Button
    run_btn = tk.Button(root, text="Combine Masks", command=run_combination, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
    run_btn.grid(row=3, column=0, columnspan=3, pady=15)

    root.mainloop()