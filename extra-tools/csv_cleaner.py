import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import tempfile

def select_file():
    """Opens a file dialog to select a CSV file."""
    file_path = filedialog.askopenfilename(
        title="Select CSV File",
        filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
    )
    file_entry.delete(0, tk.END)
    file_entry.insert(0, file_path)

def process_csv():
    """Reads the CSV, clears the specified interval, and overwrites the original file."""
    input_file = file_entry.get()
    start_frame_str = start_entry.get()
    end_frame_str = end_entry.get()

    # Validate inputs
    if not input_file or not os.path.exists(input_file):
        messagebox.showerror("Error", "Please select a valid CSV file.")
        return

    try:
        start_frame = int(start_frame_str)
        end_frame = int(end_frame_str)
    except ValueError:
        messagebox.showerror("Error", "Start and End frames must be integers.")
        return

    if start_frame > end_frame:
        messagebox.showerror("Error", "Start frame must be less than or equal to End frame.")
        return

    try:
        # Create a temporary file to safely write the changes
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(input_file), suffix=".csv")
        
        with open(input_file, mode='r', newline='', encoding='utf-8') as infile, \
             open(fd, mode='w', newline='', encoding='utf-8') as outfile:
            
            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            # Read and write the header row
            header = next(reader, None)
            if header:
                writer.writerow(header)

            # Process the remaining rows
            for row in reader:
                if not row:
                    continue  # Skip completely empty rows
                
                try:
                    # Attempt to read the frame number from the first column
                    current_frame = int(row[0])
                    
                    # If frame is within the interval, keep the frame number but clear the rest
                    if start_frame <= current_frame <= end_frame:
                        modified_row = [row[0]] + [''] * (len(row) - 1)
                        writer.writerow(modified_row)
                    else:
                        # Write the row unchanged
                        writer.writerow(row)
                except ValueError:
                    # If the first column isn't an integer, write as is
                    writer.writerow(row)

        # Safely overwrite the original file with the modified temporary file
        os.replace(temp_path, input_file)
        
        messagebox.showinfo("Success", "Processing complete!\nThe original file has been updated.")
        
    except Exception as e:
        # If an error happens, show a message and clean up the temp file
        messagebox.showerror("Error", f"An error occurred while processing:\n{str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)

# --- UI Setup ---
root = tk.Tk()
root.title("CSV Interval Cleaner")
root.geometry("450x200")
root.resizable(False, False)

# Padding configurations
padx = 10
pady = 10

# File Selection Row
tk.Label(root, text="CSV File:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
file_entry = tk.Entry(root, width=35)
file_entry.grid(row=0, column=1, padx=padx, pady=pady)
tk.Button(root, text="Browse...", command=select_file).grid(row=0, column=2, padx=padx, pady=pady)

# Start Frame Row
tk.Label(root, text="Start Frame:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
start_entry = tk.Entry(root, width=15)
start_entry.grid(row=1, column=1, sticky="w", padx=padx, pady=pady)

# End Frame Row
tk.Label(root, text="End Frame:").grid(row=2, column=0, padx=padx, pady=pady, sticky="e")
end_entry = tk.Entry(root, width=15)
end_entry.grid(row=2, column=1, sticky="w", padx=padx, pady=pady)

# Process Button
process_btn = tk.Button(root, text="Clear Interval Data", command=process_csv, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
process_btn.grid(row=3, column=0, columnspan=3, pady=15)

# Start the application
root.mainloop()