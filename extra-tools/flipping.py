import pandas as pd

# Read the original CSV
df = pd.read_csv("D:/Completed recordings/R23/aligned masks/R23_angles_complete.csv")

# Create a mapping dictionary to rename the columns
rename_map = {}
angle_cols = []

for col in df.columns:
    if col.startswith('angle_seg_'):
        # Extract the number, negate it, and create the new column name
        num = int(col.split('_')[-1])
        new_num = -num
        new_col = f"angle_seg_{new_num}"
        rename_map[col] = new_col
        angle_cols.append(new_col)
    else:
        # Keep non-angle columns (like 'frame') exactly the same
        rename_map[col] = col

# Rename columns
df_flipped = df.rename(columns=rename_map)

# Sort the new angle columns numerically
angle_cols_sorted = sorted(angle_cols, key=lambda x: int(x.split('_')[-1]))

# Reorder the dataframe columns: 'frame' first, then sorted angles
non_angle_cols = [col for col in df.columns if not col.startswith('angle_seg_')]
final_cols = non_angle_cols + angle_cols_sorted

df_flipped = df_flipped[final_cols]

# Save to a new CSV file
df_flipped.to_csv('D:/Completed recordings/R23/aligned masks/R23_angles_complete_flipped.csv', index=False)