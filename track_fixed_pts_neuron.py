import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from ast import literal_eval
import tkinter as tk
from tkinter import filedialog, messagebox

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def get_tangent_and_normal(centerline, idx):
    if 0 < idx < len(centerline) - 1:
        tangent = centerline[idx + 1] - centerline[idx - 1]
    elif idx == 0:
        tangent = centerline[1] - centerline[0]
    else:
        tangent = centerline[-1] - centerline[-2]
    tangent = tangent.astype(np.float64)
    norm = np.linalg.norm(tangent)
    if norm == 0:
        norm = 1.0
    tangent /= norm
    normal = np.array([-tangent[1], tangent[0]])
    return tangent, normal

def compute_initial_offset(centerline, neuron_pos):
    idx = cKDTree(centerline).query(neuron_pos)[1]
    anchor_point = centerline[idx]
    _, normal = get_tangent_and_normal(centerline, idx)
    offset = np.dot(neuron_pos - anchor_point, normal) 
    # distance from neuron to closest centerline point projected on normal of centerline point
    return offset

def find_matching_anchor(centerline, neuron_pos, target_offset):
    closest_idx = None
    min_error = float("inf")
    for idx in range(1, len(centerline) - 1):
        _, normal = get_tangent_and_normal(centerline, idx)
        center_point = centerline[idx]
        # Projected neuron position from this centerline point and normal
        projected_neuron = center_point + target_offset * normal
        # Compare to actual neuron position
        error = np.linalg.norm(projected_neuron - neuron_pos)

        if error < min_error:
            min_error = error
            closest_idx = idx
    return closest_idx

def get_relative_body_points(centerline, anchor_idx, num_before, num_after):
    points = []
    for i in range(-num_before, num_after + 1):
        idx = anchor_idx + i
        if 0 <= idx < len(centerline):
            points.append(centerline[idx])
        else:
            points.append((np.nan, np.nan))
    return points


# ==========================================
# MAIN PROCESSING LOGIC
# ==========================================
def run_tracking_process(csv_path, centerline_dir, mask_dir, start_frame, end_frame, num_before, num_after):
    # Setup output directories
    output_dir = os.path.join(mask_dir, "overplotted matched points")
    os.makedirs(output_dir, exist_ok=True)

    # === Load neuron positions from CSV ===
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

    # === Compute fixed offset from the FIRST VALID neuron in the selected range ===
    first_valid_frame = -1
    first_neuron = None

    for t in range(start_frame, end_frame + 1):
        neuron = neuron_coords[t] if t < len(neuron_coords) else np.array([np.nan, np.nan])
        if not np.isnan(neuron).any():
            first_valid_frame = t
            first_neuron = neuron
            break

    if first_neuron is None:
        raise ValueError(
            f"Could not find any valid (non-NaN) neuron coordinates between frames {start_frame} and {end_frame}."
        )

    centerline_path = os.path.join(centerline_dir, f"{first_valid_frame}_centerline.npy")
    if not os.path.exists(centerline_path):
        raise FileNotFoundError(f"Missing required centerline file for frame {first_valid_frame}: {centerline_path}")

    # Load the centerline (and apply the x/y flip!)
    first_centerline = np.load(centerline_path)[:, ::-1] 

    offset = compute_initial_offset(first_centerline, first_neuron)
    print(f"Using fixed signed offset: {offset:.3f} from neuron to centerline (calculated at frame {first_valid_frame})")
    print(f"Processing frames from {start_frame} to {end_frame} inclusive.")

    # === Process each frame in the chosen range ===
    results = []
    for t in range(start_frame, end_frame + 1):
        centerline_fp = os.path.join(centerline_dir, f"{t}_centerline.npy")
        if not os.path.exists(centerline_fp):
            print(f"Frame {t} missing centerline. Skipping.")
            continue

        centerline = np.load(centerline_fp)[:, ::-1]  # flip (y, x) → (x, y)
        neuron = neuron_coords[t]

        anchor_idx = find_matching_anchor(centerline, neuron, offset)
        if anchor_idx is None:
            print(f"Could not find matching anchor for frame {t}")
            continue

        anchor_point = centerline[anchor_idx]
        tracked_points = get_relative_body_points(centerline, anchor_idx, num_before, num_after)

        row = {
            "frame": t,
            "neuron_x": neuron[0],
            "neuron_y": neuron[1],
            "anchor_x": anchor_point[0],
            "anchor_y": anchor_point[1]
        }
        for i, pt in enumerate(tracked_points):
            row[f"pt_{i - num_before}_x"] = pt[0]
            row[f"pt_{i - num_before}_y"] = pt[1]
        results.append(row)

        # === Plot and save ===
        fig, ax = plt.subplots(figsize=(8, 8))

        # Load and show the mask image as background
        mask_fp = os.path.join(mask_dir, f"{t}_mask.png")  # adjust extension if needed
        if os.path.exists(mask_fp):
            img = plt.imread(mask_fp)
            ax.imshow(img, origin="upper")  # default origin assumes (0,0) is top-left
        else:
            print(f"Warning: Mask for frame {t} not found at {mask_fp}")

        ax.plot(centerline[:, 0], centerline[:, 1], 'r.', label="centerline (x, y)")
        ax.plot(*neuron, 'ro', label="neuron")
        ax.plot(*anchor_point, 'go', label="matched centerline point")
        for pt in tracked_points:
            if not np.isnan(pt[0]):
                ax.plot(pt[0], pt[1], 'bo', markersize=4)
        ax.set_title(f"Frame {t}")
        ax.set_aspect("equal")
        ax.legend()
        
        plt.savefig(os.path.join(output_dir, f"frame_{t:03d}.png"))
        plt.close(fig) # Explicitly close the figure to free up memory

    # === Save output CSV next to masks folder ===
    out_csv = os.path.join(mask_dir, f"matched_points_{start_frame}_{end_frame}.csv")
    pd.DataFrame(results).to_csv(out_csv, index=False)
    
    return len(results), out_csv, output_dir


# ==========================================
# GUI SETUP
# ==========================================
def browse_file(entry_widget):
    path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
    if path:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, path)

def browse_directory(entry_widget):
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def start_processing():
    csv_path = csv_entry.get()
    centerline_dir = center_entry.get()
    mask_dir = mask_entry.get()

    if not all([csv_path, centerline_dir, mask_dir]):
        messagebox.showerror("Error", "Please select the CSV file and both directories.")
        return

    try:
        start_frame = int(start_entry.get())
        end_frame = int(end_entry.get())
        num_before = int(before_entry.get())
        num_after = int(after_entry.get())
    except ValueError:
        messagebox.showerror("Error", "Frames and Points parameters must be integers.")
        return

    if end_frame < start_frame:
        messagebox.showerror("Error", "End Frame must be greater than or equal to Start Frame.")
        return

    # Disable the button and show processing status
    run_btn.config(state=tk.DISABLED, text="Processing... Please wait")
    root.update()

    try:
        count, csv_out, img_out = run_tracking_process(
            csv_path, centerline_dir, mask_dir, start_frame, end_frame, num_before, num_after
        )
        messagebox.showinfo(
            "Success", 
            f"Tracking complete!\n\nProcessed {count} frames successfully.\n\n"
            f"Results saved to:\n{csv_out}\n\nImages saved in:\n{img_out}"
        )
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
    finally:
        # Re-enable the button
        run_btn.config(state=tk.NORMAL, text="Run Tracking")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Centerline Tracking & Plotting")
    root.geometry("600x300")
    root.resizable(False, False)

    padx = 10
    pady = 8

    # --- File / Folder Paths ---
    tk.Label(root, text="Neuron Pos CSV:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    csv_entry = tk.Entry(root, width=50)
    csv_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_file(csv_entry)).grid(row=0, column=2, padx=padx)

    tk.Label(root, text="Centerlines Dir:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    center_entry = tk.Entry(root, width=50)
    center_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(center_entry)).grid(row=1, column=2, padx=padx)

    tk.Label(root, text="Masks Dir:").grid(row=2, column=0, padx=padx, pady=pady, sticky="e")
    mask_entry = tk.Entry(root, width=50)
    mask_entry.grid(row=2, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(mask_entry)).grid(row=2, column=2, padx=padx)

    # --- Settings Frame ---
    settings_frame = tk.Frame(root)
    settings_frame.grid(row=3, column=0, columnspan=3, pady=10)

    # Frames
    tk.Label(settings_frame, text="Start Frame:").grid(row=0, column=0, padx=5, sticky="e")
    start_entry = tk.Entry(settings_frame, width=8)
    start_entry.insert(0, "2200")
    start_entry.grid(row=0, column=1, padx=5)

    tk.Label(settings_frame, text="End Frame:").grid(row=0, column=2, padx=5, sticky="e")
    end_entry = tk.Entry(settings_frame, width=8)
    end_entry.insert(0, "5065")
    end_entry.grid(row=0, column=3, padx=5)

    # Points
    tk.Label(settings_frame, text="Points Before:").grid(row=0, column=4, padx=(20, 5), sticky="e")
    before_entry = tk.Entry(settings_frame, width=6)
    before_entry.insert(0, "70")
    before_entry.grid(row=0, column=5, padx=5)

    tk.Label(settings_frame, text="Points After:").grid(row=0, column=6, padx=5, sticky="e")
    after_entry = tk.Entry(settings_frame, width=6)
    after_entry.insert(0, "70")
    after_entry.grid(row=0, column=7, padx=5)

    # --- Run Button ---
    run_btn = tk.Button(root, text="Run Tracking", command=start_processing, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
    run_btn.grid(row=4, column=0, columnspan=3, pady=10)

    root.mainloop()