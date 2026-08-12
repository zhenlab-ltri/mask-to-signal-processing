import os
import re
import cv2
import pandas as pd
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

def generate_position_csv(input_dir, output_csv):
    """
    Reads all masks in a folder, calculates their centroid, 
    and saves a CSV formatted for literal_eval parsing.
    """
    # Find all image files
    valid_extensions = ('.png', '.jpg', '.jpeg', '.tif', '.tiff')
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(valid_extensions)]
    
    if not files:
        raise ValueError("No image masks found in the selected folder.")

    # Map frame number to file path
    frame_dict = {}
    for f in files:
        frame_num = extract_frame_num(f)
        if frame_num != -1:
            frame_dict[frame_num] = os.path.join(input_dir, f)
            
    if not frame_dict:
        raise ValueError("Could not identify frame numbers from the filenames (e.g., '0_mask.png').")

    # Determine the maximum frame to ensure continuous indexing from 0
    max_frame = max(frame_dict.keys())
    
    positions = []
    frames = []

    print(f"Processing {len(frame_dict)} masks up to frame {max_frame}...")

    # Iterate from 0 to max_frame to ensure the CSV row index matches the frame number
    for i in range(max_frame + 1):
        frames.append(i)
        
        if i in frame_dict:
            img = cv2.imread(frame_dict[i], cv2.IMREAD_GRAYSCALE)
            
            if img is None:
                positions.append("[nan, nan]")
                continue
                
            # Ensure binary image
            _, binary = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
            
            # Calculate centroid using image moments
            M = cv2.moments(binary)
            
            if M["m00"] != 0:
                cX = M["m10"] / M["m00"]
                cY = M["m01"] / M["m00"]
                # Format exactly as a string list for literal_eval
                positions.append(f"[{cX:.2f}, {cY:.2f}]")
            else:
                # Mask is completely black (no neuron found)
                positions.append("[nan, nan]")
        else:
            # File doesn't exist for this frame number
            positions.append("[nan, nan]")

    # The downstream script expects the position data in the very first column (iloc[:, 0])
    df = pd.DataFrame({
        "Neuron_Position": positions,
        "Frame": frames
    })
    
    df.to_csv(output_csv, index=False)
    return len(frame_dict), max_frame

# ==========================================
# GUI SETUP
# ==========================================
def browse_input_directory():
    folder = filedialog.askdirectory(title="Select Mask Folder")
    if folder:
        input_entry.delete(0, tk.END)
        input_entry.insert(0, folder)
        
        # Auto-suggest an output CSV name in the same parent directory
        suggested_csv = os.path.join(os.path.dirname(folder), "neuron_positions.csv")
        output_entry.delete(0, tk.END)
        output_entry.insert(0, suggested_csv)

def browse_output_file():
    file_path = filedialog.asksaveasfilename(
        title="Save Positions CSV",
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
    )
    if file_path:
        output_entry.delete(0, tk.END)
        output_entry.insert(0, file_path)

def run_extraction():
    input_dir = input_entry.get()
    output_csv = output_entry.get()

    if not input_dir or not output_csv:
        messagebox.showerror("Error", "Please select both the input folder and output CSV location.")
        return

    if not os.path.exists(input_dir):
        messagebox.showerror("Error", "The selected input folder does not exist.")
        return

    # Disable button
    run_btn.config(state=tk.DISABLED, text="Processing...")
    root.update()

    try:
        processed_count, max_frame = generate_position_csv(input_dir, output_csv)
        messagebox.showinfo(
            "Success", 
            f"Extraction complete!\n\n"
            f"Processed {processed_count} masks.\n"
            f"CSV spans frames 0 to {max_frame}.\n\n"
            f"Saved to:\n{output_csv}"
        )
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
    finally:
        # Re-enable button
        run_btn.config(state=tk.NORMAL, text="Extract Positions")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Neuron Mask Centroid Extractor")
    root.geometry("550x160")
    root.resizable(False, False)

    padx = 10
    pady = 10

    # Input Folder Row
    tk.Label(root, text="Input Masks Folder:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    input_entry = tk.Entry(root, width=40)
    input_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=browse_input_directory).grid(row=0, column=2, padx=padx)

    # Output CSV Row
    tk.Label(root, text="Output CSV File:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    output_entry = tk.Entry(root, width=40)
    output_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=browse_output_file).grid(row=1, column=2, padx=padx)

    # Process Button
    run_btn = tk.Button(root, text="Extract Positions", command=run_extraction, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
    run_btn.grid(row=2, column=0, columnspan=3, pady=5)

    root.mainloop()