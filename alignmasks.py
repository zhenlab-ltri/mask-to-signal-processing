import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox

# ==========================================
# TRANSFORMATION FUNCTIONS (From your utilities)
# ==========================================
def add_padding(data: np.ndarray, pad_width: int, pad_height: int) -> np.ndarray:
    """Adds padding to a 2D image of shape (height, width, channels)"""
    if len(data.shape) < 3 or data.shape[2] not in [1, 3, 4]:
        raise ValueError("Invalid image dimensions")

    height, width, channels = data.shape
    new_height = height + 2 * pad_height
    new_width = width + 2 * pad_width

    # Create an array with zeros and shape (new_height, new_width, channels)
    padded_image = np.ones((new_height, new_width, channels), dtype=data.dtype)

    # Copy the original image data into the center of the padded image
    padded_image[pad_height : pad_height + height, pad_width : pad_width + width] = data

    return padded_image

def get_border_value(image: np.ndarray) -> int:
    """Get the border value for the image based on the number of channels"""
    if len(image.shape) == 2:
        # Grayscale image
        return 0
    elif len(image.shape) == 3:
        # Color image (RGB or RGBA)
        return (0, 0, 0)[: image.shape[2]]  # Handles both RGB and RGBA
    else:
        raise ValueError("Unsupported image format")

def translate_image(image: np.ndarray, tx: float, ty: float) -> np.ndarray:
    """Translate an image by a given amount in the x and y directions"""
    border_value = get_border_value(image)
    M = np.float32([[1, 0, tx], [0, 1, ty]])
    result = cv2.warpAffine(
        image,
        M,
        image.shape[1::-1],
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_value,
    )
    return result

def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate an image by a given angle"""
    border_value = get_border_value(image)
    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    result = cv2.warpAffine(
        image,
        rot_mat,
        image.shape[1::-1],
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_value,
    )
    return result

def apply_transformation(image: np.ndarray, tx: float, ty: float, rotate: float) -> np.ndarray:
    """Apply translation and rotation to an image"""
    # Apply translation
    transformed_image = translate_image(image, tx, ty)

    # Apply rotation
    if rotate != 0:
        transformed_image = rotate_image(transformed_image, rotate)

    return transformed_image

# ==========================================
# BATCH PROCESSING LOGIC
# ==========================================
def batch_align_masks(input_dir, output_dir, translate_x, translate_y, rotate):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    mask_files = [f for f in os.listdir(input_dir) if f.endswith('.png')] 
    
    if not mask_files:
        raise FileNotFoundError(f"No PNG files found in {input_dir}.")

    print(f"Found {len(mask_files)} masks. Applying alignment: tx={translate_x}, ty={translate_y}, rot={rotate}")

    processed_count = 0
    for filename in mask_files:
        in_path = os.path.join(input_dir, filename)
        out_path = os.path.join(output_dir, filename)

        # Load mask
        mask = cv2.imread(in_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            print(f"Warning: Failed to read {filename}. Skipping.")
            continue

        # Convert boolean/binary mask to uint8 to prevent cv2 interpolation errors
        if mask.max() == 1:
            mask = (mask * 255).astype(np.uint8)

        # Apply the transformation
        aligned_mask = apply_transformation(mask, translate_x, translate_y, rotate)

        # Threshold to ensure the output remains strictly binary after any potential affine interpolation
        _, binary_aligned_mask = cv2.threshold(aligned_mask, 127, 255, cv2.THRESH_BINARY)

        cv2.imwrite(out_path, binary_aligned_mask)
        processed_count += 1

    return processed_count

# ==========================================
# GUI SETUP
# ==========================================
def browse_directory(entry_widget):
    """Helper to open a directory selection dialog and update an Entry widget."""
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def run_alignment():
    """Gathers paths and parameters from the GUI, validates them, and runs the alignment."""
    input_dir = input_entry.get()
    output_dir = output_entry.get()

    if not input_dir or not output_dir:
        messagebox.showerror("Error", "Please select both Input and Output directories.")
        return

    if not os.path.exists(input_dir):
        messagebox.showerror("Error", "The selected Input directory does not exist.")
        return

    # Validate numeric inputs
    try:
        tx = float(tx_entry.get())
        ty = float(ty_entry.get())
        rot = float(rot_entry.get())
    except ValueError:
        messagebox.showerror("Error", "Translation and Rotation parameters must be numbers.")
        return

    # Disable button to prevent multiple clicks
    run_btn.config(state=tk.DISABLED, text="Processing...")
    root.update()

    try:
        count = batch_align_masks(input_dir, output_dir, tx, ty, rot)
        messagebox.showinfo("Success", f"Alignment complete!\nProcessed {count} masks successfully.")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during alignment:\n{str(e)}")
    finally:
        # Re-enable button
        run_btn.config(state=tk.NORMAL, text="Run Alignment")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Mask Aligner")
    root.geometry("550x260")
    root.resizable(False, False)

    padx = 10
    pady = 10

    # --- Directories ---
    tk.Label(root, text="Input Masks Folder:").grid(row=0, column=0, padx=padx, pady=pady, sticky="e")
    input_entry = tk.Entry(root, width=45)
    input_entry.grid(row=0, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(input_entry)).grid(row=0, column=2, padx=padx)

    tk.Label(root, text="Output Folder:").grid(row=1, column=0, padx=padx, pady=pady, sticky="e")
    output_entry = tk.Entry(root, width=45)
    output_entry.grid(row=1, column=1, padx=padx, pady=pady)
    tk.Button(root, text="Browse...", command=lambda: browse_directory(output_entry)).grid(row=1, column=2, padx=padx)

    # --- Parameters Frame ---
    param_frame = tk.LabelFrame(root, text="Transformation Parameters")
    param_frame.grid(row=2, column=0, columnspan=3, padx=padx, pady=10, sticky="ew")

    # Translation X
    tk.Label(param_frame, text="Translate X:").grid(row=0, column=0, padx=5, pady=10, sticky="e")
    tx_entry = tk.Entry(param_frame, width=10)
    tx_entry.insert(0, "-19.0")
    tx_entry.grid(row=0, column=1, padx=5, pady=10)

    # Translation Y
    tk.Label(param_frame, text="Translate Y:").grid(row=0, column=2, padx=5, pady=10, sticky="e")
    ty_entry = tk.Entry(param_frame, width=10)
    ty_entry.insert(0, "-14.0")
    ty_entry.grid(row=0, column=3, padx=5, pady=10)

    # Rotation
    tk.Label(param_frame, text="Rotate (°):").grid(row=0, column=4, padx=5, pady=10, sticky="e")
    rot_entry = tk.Entry(param_frame, width=10)
    rot_entry.insert(0, "0.0")
    rot_entry.grid(row=0, column=5, padx=5, pady=10)

    # --- Run Button ---
    run_btn = tk.Button(root, text="Run Alignment", command=run_alignment, bg="#2196F3", fg="white", font=("Arial", 10, "bold"))
    run_btn.grid(row=3, column=0, columnspan=3, pady=5)

    root.mainloop()