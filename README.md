# Processing Pipeline Repository

This repository contains a suite of graphical user interface (GUI) scripts designed to process, align, and extract signals from dual-channel imaging masks. 

Below is the step-by-step tutorial for utilizing this pipeline, based on the standard processing workflow. A pdf version of this manual is also included in this repository and contains pictures of the different GUIs.

---

## Pipeline manual

Follow these steps in order to process the masks, extract centerlines, and plot the final calcium and curvature signals.
### Phase 0: Set Up Environment 

Execute `python -m venv proenv`. 

Execute `proenv/Scripts/activate` to activate the environment.

Execute `pip install -r requirements.txt`.

### Phase 1: Mask Preparation & Alignment

*   **Step 1: Correct the masks**
    *   Use **SAM3GUI** or the **Mask Annotator app** to correct the initial masks.
*   **Step 2: Crop the masks into separate channels**
    *   Execute `python croppingmasks.py` in the terminal.
    *   Using the **Mask Cropper** GUI, select the full masks folder. 
    *   Keep the left half for the worm masks (red channel) and the right half for the neuron masks (green channel).
*   **Step 3: Calculate alignment and ROI**
    *   Use the **CaTracker pipeline** to align and track a single frame. 
    *   Write down the calculated alignment (dx, dy) and the ROI values.
*   **Step 4: Align the green channel (neuron) masks**
    *   Execute `python alignmasks.py`.
    *   In the **Mask Aligner** GUI, select the green channel masks as the input. 
    *   Enter the alignment parameters from Step 3, but *reverse the sign* (e.g., if you recorded dx: -3 and dy: -5, input 3 and 5).

### Phase 2: Merging & Centroid Extraction

*   **Step 5: Merge the channel masks**
    *   Execute `python merge-masks.py`.
    *   Using the **Mask Combiner** GUI, input the red channel folder and the newly aligned green channel folder to merge them into a single output folder.
*   **Step 6: Extract neuron positions**
    *   Execute `python extract_neuron_positions.py`.
    *   In the **Neuron Mask Centroid Extractor** GUI, input the aligned green masks (from Step 4) to automatically save a CSV of the positions to the root folder.

### Phase 3: Centerlines & Tracking

*   **Step 7: Extract centerlines**
    *   Execute `python masktocenterline.py`.
    *   In the **Mask to Centerline (Optimized)** GUI, select the merged masks from Step 5. 
    *   Keep the default centerline spacing of `30.0` pixels to generate a new `centerlines` subfolder.
*   **Step 8: Align centerlines with neuron positions**
    *   Execute `python track_fixed_pts_neuron.py`.
    *   In the **Centerline Tracking & Plotting** GUI, input the Neuron Positions CSV (Step 6), the Centerlines directory (Step 7), and the Merged Masks directory (Step 5).
    *   This generates a `matched_points.csv` file and a verification folder named `Overplotted matched points` containing PNGs.
*   **Step 9: Calculate angles**
    *   Execute `python angles.csv` in the terminal.
    *   Use the **Centerline to Angles Converter** GUI to process the `matched_points.csv` obtained in Step 8.

### Phase 4: Full Masks & Signal Extraction

*   **Step 10: Create full masks for raw TIFFs**
    *   Execute `python tiffmasks.py`.
    *   In the **Full-Frame Mask Generator** GUI, use the merged masks from Step 5 as the "Unshifted Masks Folder" and the CSV from Step 6 as the "Positions CSV". 
    *   Use the ROI values recorded in Step 3 as the padding parameters.
*   **Step 11: Extract the signal**
    *   Execute `python tiffsignal.py`.
    *   Using the **TIFF Signal Extractor** GUI, select the Raw TIFFs and the Full Masks to extract the data.
    *   This produces two CSV files: one containing the total pixel intensity of the ROI, and another containing the top 95% brightest pixels.
*   **Step 12: Plot curvature and signal**
    *   Execute `python all_plots.py`.
    *   In the **Curvature & Calcium Plotter** GUI, load the Angles CSV (from Step 9) and the Calcium CSV (from Step 11) to generate the final visualization in a new window.

---

## Script Directory Reference

| Script Command | GUI Name | Primary Function | Input Data Required |
| :--- | :--- | :--- | :--- |
| `python croppingmasks.py` | Mask Cropper | Splits masks into left (red) and right (green) channels. | Full uncropped masks |
| `python alignmasks.py` | Mask Aligner | Aligns the green masks using inverted alignment coordinates. | Cropped green masks, alignment values |
| `python merge-masks.py` | Mask Combiner | Combines red and green channels back together. | Red masks, Aligned green masks |
| `python extract_neuron_positions.py` | Neuron Mask Centroid Extractor | Extracts neuron coordinates to a CSV. | Aligned green masks |
| `python masktocenterline.py` | Mask to Centerline (Optimized) | Generates centerlines with 30px spacing. | Merged red channel masks |
| `python track_fixed_pts_neuron.py` | Centerline Tracking & Plotting | Matches centerlines to neuron coordinates. | Centerlines, Neuron CSV, Merged Masks |
| `python angles.csv` | Centerline to Angles Converter | Calculates geometric angles from tracked points. | `matched_points.csv` |
| `python tiffmasks.py` | Full-Frame Mask Generator | Applies ROI padding to create final TIFF masks. | Raw TIFFs, Merged Masks, Neuron CSV, ROI padding |
| `python tiffsignal.py` | TIFF Signal Extractor | Extracts pixel intensity data into two distinct CSVs. | Raw TIFFs, Full-Frame TIFF Masks |
| `python all_plots.py` | Curvature & Calcium Plotter | Renders the final combined data plots. | Angles CSV, Calcium Signal CSV |