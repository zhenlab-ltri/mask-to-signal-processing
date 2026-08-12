import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog, messagebox

def compute_kymo(angles_csv, calcium_csv, end_frame=None):
    """
    Load curvature angles and calcium data,
    compute curvature kymograph while preserving missing regions.
    """
    # =========================
    # LOAD ANGLE DATA
    # =========================
    T = pd.read_csv(angles_csv)

    ang_cols = [
        col for col in T.columns
        if str(col).startswith('angle_seg')
    ]

    # Extract segment indices
    seg_numbers = []

    for col in ang_cols:
        match = re.search(r'angle_seg_(-?\d+)', col)
        if match:
            seg_numbers.append(int(match.group(1)))
        else:
            seg_numbers.append(-999)

    # Sort columns spatially
    ord_idx = np.argsort(seg_numbers)

    segIdx = np.array(seg_numbers)[ord_idx]
    ang_cols_sorted = [ang_cols[i] for i in ord_idx]

    # =========================
    # IMPORTANT:
    # DO NOT INTERPOLATE
    # =========================
    # Missing segments should stay missing.
    # Interpolation creates fake horizontal stripes.
    ang = T[ang_cols_sorted].values.astype(float)
    framesA = T['frame'].values

    # =========================
    # UNWRAP ANGLES
    # =========================
    # Do this frame-by-frame
    angU = np.full_like(ang, np.nan)

    for i in range(ang.shape[0]):
        row = ang[i]
        valid = np.isfinite(row)

        # Need enough valid segments
        if np.sum(valid) > 3:
            # unwrap only valid values
            unwrapped = np.unwrap(row[valid])
            angU[i, valid] = unwrapped

    # =========================
    # OPTIONAL VERY LIGHT SMOOTHING
    # =========================
    # Disabled for now because smoothing can
    # reintroduce artifacts across missing regions.
    angS = angU

    # =========================
    # COMPUTE CURVATURE
    # =========================
    K = np.diff(angS, axis=1).T
    segIdx = segIdx[:-1]

    # =========================
    # LOAD CALCIUM DATA
    # =========================
    C = pd.read_csv(calcium_csv)
    framesC = np.arange(len(C))

    G_all = C['Green_Intensity'].values
    R_all = C['Red_Intensity'].values

    # =========================
    # ALIGN FRAMES
    # =========================
    frames, ia, ic = np.intersect1d(
        framesA,
        framesC,
        return_indices=True
    )

    if end_frame is not None:
        keep = frames <= end_frame
        frames = frames[keep]
        ia = ia[keep]
        ic = ic[keep]

    K = K[:, ia]
    G = G_all[ic]
    R = R_all[ic]

    return K, segIdx, G, R, frames


def create_all_plots(angles_csv, calcium_csv, raw_csv, output_dir=None, end_frame=None):
    K, segIdx, G, R, frames = compute_kymo(angles_csv, calcium_csv, end_frame=end_frame)

    df = pd.read_csv(raw_csv)
    if end_frame is not None:
        df = df[df.index <= end_frame].copy()
    if 'Red_Intensity' not in df.columns or 'Green_Intensity' not in df.columns:
        raise ValueError('Required intensity columns are missing from the CSV.')

    recording_name = os.path.basename(calcium_csv).replace('.csv', '')
    raw_name = os.path.basename(raw_csv).replace('.csv', '')

    fig = plt.figure(figsize=(14, 24), constrained_layout=True)
    gs = fig.add_gridspec(4, 1, height_ratios=[2.5, 1.2, 1.2, 1.2])

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
    ax3 = fig.add_subplot(gs[2, 0], sharex=ax1)
    ax4 = fig.add_subplot(gs[3, 0])

    fig.suptitle(f"Recording: {recording_name} | Raw data: {raw_name}", fontsize=18, fontweight='bold')

    # Mask invalid values
    K_masked = np.ma.masked_invalid(K)

    # Compute contrast from valid values only
    valid_vals = np.abs(K[np.isfinite(K)])

    if len(valid_vals) == 0:
        vmax = 1
    else:
        vmax = np.percentile(valid_vals, 95)
        if vmax == 0:
            vmax = 1

    # Colormap with white for missing values
    cmap = plt.cm.coolwarm.copy()
    cmap.set_bad(color='white')

    im = ax1.imshow(
        K_masked,
        aspect='auto',
        cmap=cmap,
        origin='lower',
        interpolation='none',   # IMPORTANT
        extent=[
            frames[0],
            frames[-1],
            segIdx[0],
            segIdx[-1]
        ],
        vmin=-vmax,
        vmax=vmax,
    )
    
    # Force the X-axis to match the frame range strictly
    ax1.set_xlim(frames[0], frames[-1])
    ax1.set_ylabel('Segment Index')
    ax1.set_title('Curvature Kymograph (Horizontal Stripes = Segments)')

    cb = fig.colorbar(
        im,
        ax=ax1,
        orientation='vertical',
        fraction=0.04,
        pad=0.02
    )
    cb.set_label('Curvature')

    G_z = (G - np.nanmean(G)) / np.nanstd(G)
    R_z = (R - np.nanmean(R)) / np.nanstd(R)
    ax2.plot(frames, G_z, color='green', label='Z-scored GCaMP (GFP)', linewidth=1.5)
    ax2.plot(frames, R_z, color='red', label='Z-scored RFP', linewidth=1.5)
    ax2.set_xlabel('Frame')
    ax2.set_ylabel('Z-score Intensity')
    ax2.set_title('Z-score Normalized Aligned Calcium Traces')
    ax2.legend(loc='upper right')

    ax3_red = ax3
    ax3_green = ax3.twinx()

    red_line, = ax3_red.plot(df.index, df['Red_Intensity'], color='red', alpha=0.7, label='Raw Red Signal (RFP)')
    green_line, = ax3_green.plot(df.index, df['Green_Intensity'], color='green', alpha=0.7, label='Raw Green Signal (GFP)')

    ax3_red.set_xlabel('Data Point Index')
    ax3_red.set_ylabel('Red Signal Intensity (RFP)', color='red')
    ax3_green.set_ylabel('Green Signal Intensity (GFP)', color='green')
    ax3_red.set_title('Raw Red and Green Signals (Separate Scales)')

    ax3_red.tick_params(axis='y', colors='red')
    ax3_green.tick_params(axis='y', colors='green')

    ax3_red.legend([red_line, green_line], ['Raw Red Signal (RFP)', 'Raw Green Signal (GFP)'], loc='upper right')

    ax4.scatter(df['Green_Intensity'], df['Red_Intensity'], color='blue', alpha=0.4, s=18)
    ax4.set_xlabel('Green Signal (GFP Intensity)')
    ax4.set_ylabel('Red Signal (RFP Intensity)')
    ax4.set_title('Raw GFP vs RFP Signal Correlation')

    fig.subplots_adjust(hspace=0.35)

    if output_dir is not None:
        os.makedirs(output_dir, exist_ok=True)
        base_name = f"new_combined_plots_{os.path.splitext(os.path.basename(raw_csv))[0]}"
        save_path = os.path.join(output_dir, f"{base_name}.png")
        fig.savefig(save_path, dpi=200, bbox_inches='tight')
        print(f"Saved combined plot to {save_path}")

    plt.show()

# =========================
# GUI SETUP
# =========================
def select_angles_file():
    path = filedialog.askopenfilename(title="Select Angles CSV", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
    if path:
        angles_entry.delete(0, tk.END)
        angles_entry.insert(0, path)

def select_calcium_file():
    path = filedialog.askopenfilename(title="Select Calcium CSV", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
    if path:
        calcium_entry.delete(0, tk.END)
        calcium_entry.insert(0, path)

def run_plot():
    angles_csv = angles_entry.get()
    calcium_csv = calcium_entry.get()
    end_frame_str = end_frame_entry.get()

    if not os.path.exists(angles_csv) or not os.path.exists(calcium_csv):
        messagebox.showerror("Error", "Please select valid CSV files for both Angles and Calcium data.")
        return

    end_frame = None
    if end_frame_str.strip():
        try:
            end_frame = int(end_frame_str)
        except ValueError:
            messagebox.showerror("Error", "End Frame must be an integer.")
            return

    output_dir = os.path.join('data', 'plots_combined')
    
    # Run the plot script
    try:
        # In your original script, raw_file was assigned the same path as calcium_file
        create_all_plots(angles_csv, calcium_csv, calcium_csv, output_dir=output_dir, end_frame=end_frame)
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while plotting:\n{str(e)}")

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Curvature & Calcium Plotter")
    root.geometry("550x200")
    root.resizable(False, False)

    padx = 10
    pady = 10

    # Angles File
    tk.Label(root, text="Angles CSV:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    angles_entry = tk.Entry(root, width=45)
    angles_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=select_angles_file).grid(row=0, column=2, padx=padx, pady=pady)

    # Calcium File
    tk.Label(root, text="Calcium CSV:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    calcium_entry = tk.Entry(root, width=45)
    calcium_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=select_calcium_file).grid(row=1, column=2, padx=padx, pady=pady)

    # End Frame
    tk.Label(root, text="End Frame (optional):").grid(row=2, column=0, padx=padx, pady=pady, sticky="e")
    end_frame_entry = tk.Entry(root, width=15)
    end_frame_entry.grid(row=2, column=1, sticky="w", padx=padx, pady=pady)

    # Plot Button
    plot_btn = tk.Button(root, text="Generate Plots", command=run_plot, bg="#2196F3", fg="white", font=("Arial", 10, "bold"))
    plot_btn.grid(row=3, column=0, columnspan=3, pady=10)

    root.mainloop()