import os
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw
import time

from skimage.morphology import skeletonize
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path

# --- Anti-Formatting Bug Variables ---
# We use these variables to prevent your text editor from 
# deleting the numbers 0 and 1 inside square brackets.
IDX_0 = 0
IDX_1 = 1
# -------------------------------------

# 1. OPTIMIZED: Blazing fast local grid-graph generation instead of global cdist
#############################################################
def skeleton_to_graph_fast(coords, mask_shape):
    """Builds a sparse graph from skeleton points by checking adjacent grid points."""
    # Create an index mapping image: grid_map[y, x] = index of that coordinate
    grid_map = np.full(mask_shape, -1, dtype=np.int32)
    grid_map[coords[:, IDX_0], coords[:, IDX_1]] = np.arange(len(coords))
    
    row_idx, col_idx = [], []
    
    # 8-connected neighborhood shifts
    shifts = [(-1, -1), (-1, IDX_0), (-1, IDX_1), (IDX_0, -1), (IDX_0, IDX_1), (IDX_1, -1), (IDX_1, IDX_0), (IDX_1, IDX_1)]
    
    for dy, dx in shifts:
        ny, nx = coords[:, IDX_0] + dy, coords[:, IDX_1] + dx
        # Check image boundaries safely
        valid = (ny >= 0) & (ny < mask_shape[IDX_0]) & (nx >= 0) & (nx < mask_shape[IDX_1])
        if not np.any(valid): 
            continue
            
        neighbor_indices = grid_map[ny[valid], nx[valid]]
        valid_neighbors = neighbor_indices != -1
        
        if np.any(valid_neighbors):
            row_idx.extend(grid_map[coords[:, IDX_0][valid], coords[:, IDX_1][valid]][valid_neighbors])
            col_idx.extend(neighbor_indices[valid_neighbors])
            
    adjacency = csr_matrix((np.ones(len(row_idx), dtype=np.uint8), (row_idx, col_idx)), shape=(len(coords), len(coords)))
    return adjacency

def longest_skeleton_path_fast(coords, mask_shape):
    graph = skeleton_to_graph_fast(coords, mask_shape)
    degrees = np.array(graph.sum(axis=1)).ravel()
    endpoints = np.where(degrees == 1)[IDX_0]

    if len(endpoints) < 2:
        # Fallback to endpoints with degree 0 or more if clean skeleton endpoints missing
        endpoints = np.where(degrees >= 0)[IDX_0]
        if len(endpoints) < 2:
            raise ValueError("No valid skeleton endpoints found")

    dist, pred = shortest_path(graph, directed=False, return_predecessors=True)

    # Use matrix searching to find the maximum distance pair quickly
    valid_dists = dist[endpoints[:, None], endpoints]
    valid_dists[~np.isfinite(valid_dists)] = -1
    
    idx_max = np.argmax(valid_dists)
    i_local, j_local = np.unravel_index(idx_max, valid_dists.shape)
    
    start_node = endpoints[i_local]
    end_node = endpoints[j_local]

    # Reconstruct path trajectory
    path = []
    cur = end_node
    while cur != -9999:
        path.append(cur)
        cur = pred[start_node, cur]

    return coords[path[::-1]]

# 2. OPTIMIZED: Vectorized interpolation path mapping
#######################################################
def resample_fixed_spacing_fast(centerline, spacing_px):
    diffs = np.diff(centerline, axis=0)
    seg_lens = np.sqrt((diffs ** 2).sum(axis=1))
    arc = np.concatenate([np.zeros(1), np.cumsum(seg_lens)])

    total_len = arc[-1]
    num_pts = int(np.floor(total_len / spacing_px)) + 1
    targets = np.arange(num_pts) * spacing_px

    # Vectorized interpolation for x and y coordinates simultaneously
    resampled_y = np.interp(targets, arc, centerline[:, IDX_0])
    resampled_x = np.interp(targets, arc, centerline[:, IDX_1])

    return np.column_stack((resampled_y, resampled_x))

def centerline_from_mask(mask, spacing_px):
    skeleton = skeletonize(mask)
    coords = np.column_stack(np.where(skeleton))

    if len(coords) < 10:
        raise ValueError("Skeleton too small")

    ordered = longest_skeleton_path_fast(coords, mask.shape)
    return resample_fixed_spacing_fast(ordered, spacing_px)


# GUI + batch processing
########################################
class MaskCenterlineApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mask to Centerline (Optimized)")
        self.spacing_px = tk.DoubleVar(value=30.0)
        self.start_frame = tk.IntVar(value=0)

        tk.Button(root, text="Select Mask Folder", command=self.select_folder).pack(pady=10)
        tk.Label(root, text="Start frame:").pack()
        tk.Entry(root, textvariable=self.start_frame, width=10).pack()
        tk.Label(root, text="Centerline spacing (pixels):").pack()
        tk.Entry(root, textvariable=self.spacing_px, width=10).pack()

        self.status = tk.Label(root, text="")
        self.status.pack(pady=10)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        try:
            skipped = self.process_folder(folder)
            if skipped:
                skipped_info = "\n".join([f"Frame {f_num}: {fname} - {err}" for f_num, fname, err in skipped])
                messagebox.showinfo("Done", f"Centerlines saved.\n\nSkipped frames:\n{skipped_info}")
            else:
                messagebox.showinfo("Done", "All frames processed successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def process_folder(self, folder):
        raw_files = [
            f for f in os.listdir(folder)
            if f.lower().endswith((".png", ".jpg", ".tif")) and "_mask" in f.lower()
        ]

        if not raw_files:
            raise ValueError("No mask images found")

        def get_frame_number(filename):
            try:
                return int(filename.split("_mask")[IDX_0])
            except ValueError:
                return float('inf')

        mask_files = sorted(raw_files, key=get_frame_number)
        start_frame = self.start_frame.get()
        mask_files = [f for f in mask_files if get_frame_number(f) >= start_frame]

        if not mask_files:
            raise ValueError(f"No mask images found starting at frame {start_frame}")

        centerline_dir = os.path.join(folder, "centerlines")
        overlay_dir = os.path.join(folder, "overplotted")
        os.makedirs(centerline_dir, exist_ok=True)
        os.makedirs(overlay_dir, exist_ok=True)

        all_centerlines = []
        skipped_frames = []

        start_processing_time = time.time()
        total_num_files = len(mask_files)
        curr_frame_idx = 0
        prev_centerline = None

        for fname in mask_files:
            time_elapsed = time.time() - start_processing_time
            time_per_frame = time_elapsed / (curr_frame_idx + 1)

            msg = f"Processing {fname} ({curr_frame_idx + 1}/{total_num_files}) - Est. Remaining: {(total_num_files - curr_frame_idx - 1) * time_per_frame:.2f}s"
            self.status.config(text=msg)
            self.root.update()
            curr_frame_idx += 1

            try:
                frame_num = fname.split("_mask")[IDX_0]
                
                img = Image.open(os.path.join(folder, fname)).convert("L")
                mask = np.array(img) > 0

                # Extract centerline coordinates
                centerline = centerline_from_mask(mask, self.spacing_px.get())

                # Direction flip correction check
                if prev_centerline is not None:
                    dist_normal = np.linalg.norm(centerline[IDX_0] - prev_centerline[IDX_0]) + np.linalg.norm(centerline[-1] - prev_centerline[-1])
                    dist_flipped = np.linalg.norm(centerline[-1] - prev_centerline[IDX_0]) + np.linalg.norm(centerline[IDX_0] - prev_centerline[-1])
                    if dist_flipped < dist_normal:
                        centerline = centerline[::-1]
                
                prev_centerline = centerline.copy()
                all_centerlines.append(centerline)

                # Save coordinate binary directly
                np.save(os.path.join(centerline_dir, f"{frame_num}_centerline.npy"), centerline)

                # 3. OPTIMIZED: High speed overlay image writing using PIL instead of Matplotlib
                # Convert grayscale mask to an RGB canvas background
                overlay_img = Image.fromarray((mask * 255).astype(np.uint8)).convert("RGB")
                draw = ImageDraw.Draw(overlay_img)
                
                # Transform centerline coords into coordinate tuple sequences (X, Y)
                points_list = [(pt[IDX_1], pt[IDX_0]) for pt in centerline]
                
                # Draw path lines and joint points
                if len(points_list) > 1:
                    draw.line(points_list, fill=(255, 0, 0), width=1)
                for pt in points_list:
                    draw.ellipse([pt[IDX_0]-2, pt[IDX_1]-2, pt[IDX_0]+2, pt[IDX_1]+2], fill=(255, 0, 0))

                overlay_img.save(os.path.join(overlay_dir, f"{frame_num}_overlay.png"))

            except ValueError as e:
                frame_num = fname.split("_mask")[IDX_0]
                skipped_frames.append((frame_num, fname, str(e)))
                self.status.config(text=f"Skipped {fname}: {str(e)}")
                self.root.update()
                continue

        print(f"Processed {total_num_files} frames completed in {time.time() - start_processing_time:.2f} seconds.")
        np.save(os.path.join(folder, "centerlines_all.npy"), np.array(all_centerlines, dtype=object))

        return skipped_frames

if __name__ == "__main__":
    root = tk.Tk()
    app = MaskCenterlineApp(root)
    root.mainloop()