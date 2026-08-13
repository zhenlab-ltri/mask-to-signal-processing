import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import os

def browse_file():
    filepath = filedialog.askopenfilename(
        title="Select CSV File",
        filetypes=(("CSV Files", "*.csv"), ("All Files", "*.*"))
    )
    if filepath:
        entry_input.delete(0, tk.END)
        entry_input.insert(0, filepath)

def process_csv():
    input_path = entry_input.get()
    
    if not input_path or not os.path.exists(input_path):
        messagebox.showerror("Error", "Please select a valid input CSV file.")
        return

    try:
        # Read the original CSV
        df = pd.read_csv(input_path)
        
        # Create a copy so we can safely overwrite specific rows
        df_modified = df.copy()
        
        # 1. Figure out which rows to flip based on Start/End Frame
        # By default, select all rows (True for every row)
        row_mask = pd.Series(True, index=df.index)
        
        start_val = entry_start.get().strip()
        end_val = entry_end.get().strip()
        
        if (start_val or end_val):
            if 'frame' not in df.columns:
                messagebox.showwarning("Warning", "No 'frame' column found. Applying flip to entire file.")
            else:
                if start_val:
                    row_mask = row_mask & (df['frame'] >= float(start_val))
                if end_val:
                    row_mask = row_mask & (df['frame'] <= float(end_val))
                    
        # 2. Map how columns should swap (e.g. angle_seg_1 maps to angle_seg_-1)
        rename_map = {}
        for col in df.columns:
            if col.startswith('angle_seg_'):
                num = int(col.split('_')[-1])
                new_col = f"angle_seg_{-num}"
                rename_map[col] = new_col

        # 3. Swap the data ONLY for the rows inside the frame range
        # We read from df (original) and write to df_modified to prevent overwriting issues
        for old_col, new_col in rename_map.items():
            df_modified.loc[row_mask, new_col] = df.loc[row_mask, old_col]

        # 4. Sort the columns numerically just like the original script
        angle_cols = [col for col in df_modified.columns if col.startswith('angle_seg_')]
        angle_cols_sorted = sorted(angle_cols, key=lambda x: int(x.split('_')[-1]))

        # Reorder the dataframe columns: 'frame' (and other non-angles) first, then sorted angles
        non_angle_cols = [col for col in df_modified.columns if not col.startswith('angle_seg_')]
        final_cols = non_angle_cols + angle_cols_sorted

        df_modified = df_modified[final_cols]

        # 5. Save to a new CSV file
        output_path = input_path.replace('.csv', '_flipped.csv')
        df_modified.to_csv(output_path, index=False)
        
        messagebox.showinfo("Success", f"Processing complete!\n\nSaved to:\n{output_path}")
        
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while processing:\n{str(e)}")

# --- GUI Setup ---
root = tk.Tk()
root.title("Angle Segments Flipper")
root.geometry("500x220")
root.resizable(False, False)

# Padding configuration
padx = 10
pady = 10

# Input File Row
tk.Label(root, text="Input CSV:").grid(row=0, column=0, sticky="e", padx=padx, pady=pady)
entry_input = tk.Entry(root, width=45)
entry_input.grid(row=0, column=1, padx=padx, pady=pady)
btn_browse = tk.Button(root, text="Browse", command=browse_file)
btn_browse.grid(row=0, column=2, padx=padx, pady=pady)

# Start Frame Row
tk.Label(root, text="Start Frame:").grid(row=1, column=0, sticky="e", padx=padx, pady=pady)
entry_start = tk.Entry(root, width=15)
entry_start.grid(row=1, column=1, sticky="w", padx=padx, pady=pady)
tk.Label(root, text="(Optional)", fg="gray").grid(row=1, column=1, sticky="e", padx=padx)

# End Frame Row
tk.Label(root, text="End Frame:").grid(row=2, column=0, sticky="e", padx=padx, pady=pady)
entry_end = tk.Entry(root, width=15)
entry_end.grid(row=2, column=1, sticky="w", padx=padx, pady=pady)
tk.Label(root, text="(Optional)", fg="gray").grid(row=2, column=1, sticky="e", padx=padx)

# Process Button
btn_process = tk.Button(root, text="Process and Save", command=process_csv, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
btn_process.grid(row=3, column=0, columnspan=3, pady=20)

# Run the application
root.mainloop()