import os
import re
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox

def convert_centerline_to_angles(input_csv, output_csv):
    """
    Reads a centerline points CSV file and calculates directional segment angles.
    Preserves missing values (NaNs) exactly as required for the kymograph.
    """
    print(f"Loading centerline data from: {input_csv}")
    df = pd.read_csv(input_csv)
    
    # 1. Dynamically extract all unique point indices from the column names
    pt_indices = []
    for col in df.columns:
        match = re.match(r'pt_(-?\d+)_x', col)
        if match:
            pt_indices.append(int(match.group(1)))
            
    # Sort indices to guarantee correct head-to-tail spatial sequence
    pt_indices = sorted(pt_indices)
    print(f"Found point indices ranging from {min(pt_indices)} to {max(pt_indices)}")
    
    # 2. Initialize the output DataFrame with the frame numbers
    angles_df = pd.DataFrame()
    if 'frame' in df.columns:
        angles_df['frame'] = df['frame']
    else:
        angles_df['frame'] = df.index
        
    # 3. Calculate tangent angles between adjacent centerline points
    # Segment i is defined by point i and point i + 1
    for i in range(len(pt_indices) - 1):
        p_curr = pt_indices[i]
        p_next = pt_indices[i + 1]
        
        # Verify that the points are spatially continuous
        if p_next == p_curr + 1:
            x_curr = df[f'pt_{p_curr}_x']
            y_curr = df[f'pt_{p_curr}_y']
            x_next = df[f'pt_{p_next}_x']
            y_next = df[f'pt_{p_next}_y']
            
            # Calculate the segment angle in radians
            # Note: np.arctan2 automatically handles NaNs where points are missing
            angle = np.arctan2(y_next - y_curr, x_next - x_curr)
            
            # Store with the exact column naming syntax expected by the kymograph script
            angles_df[f'angle_seg_{p_curr}'] = angle

    # 4. Save to CSV
    angles_df.to_csv(output_csv, index=False)
    print(f"Successfully saved segment angles to: {output_csv}\n")
    return angles_df

# =========================
# GUI SETUP
# =========================
def select_input_file():
    """Opens dialog to select the input centerline CSV."""
    path = filedialog.askopenfilename(
        title="Select Centerline Points CSV",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
    )
    if path:
        input_entry.delete(0, tk.END)
        input_entry.insert(0, path)
        
        # Auto-generate an output path based on the input path
        base_name, ext = os.path.splitext(path)
        default_output = f"{base_name}_angles{ext}"
        output_entry.delete(0, tk.END)
        output_entry.insert(0, default_output)

def select_output_file():
    """Opens dialog to choose where to save the output angles CSV."""
    path = filedialog.asksaveasfilename(
        title="Save Angles CSV",
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
    )
    if path:
        output_entry.delete(0, tk.END)
        output_entry.insert(0, path)

def run_conversion():
    """Runs the conversion with the paths from the GUI."""
    input_csv = input_entry.get()
    output_csv = output_entry.get()

    if not input_csv or not os.path.exists(input_csv):
        messagebox.showerror("Error", "Please select a valid input CSV file.")
        return
        
    if not output_csv:
        messagebox.showerror("Error", "Please specify an output file path.")
        return

    try:
        convert_centerline_to_angles(input_csv, output_csv)
        messagebox.showinfo("Success", f"Conversion complete!\nAngles saved to:\n{output_csv}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during conversion:\n{str(e)}")

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Centerline to Angles Converter")
    root.geometry("550x160")
    root.resizable(False, False)

    padx = 10
    pady = 10

    # Input File Row
    tk.Label(root, text="Input Centerline CSV:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    input_entry = tk.Entry(root, width=40)
    input_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=select_input_file).grid(row=0, column=2, padx=padx, pady=pady)

    # Output File Row
    tk.Label(root, text="Output Angles CSV:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    output_entry = tk.Entry(root, width=40)
    output_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=select_output_file).grid(row=1, column=2, padx=padx, pady=pady)

    # Convert Button
    convert_btn = tk.Button(root, text="Convert to Angles", command=run_conversion, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
    convert_btn.grid(row=2, column=0, columnspan=3, pady=10)

    root.mainloop()