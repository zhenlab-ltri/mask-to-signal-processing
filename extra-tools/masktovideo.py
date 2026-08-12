import argparse
import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import cv2


def natural_sort_key(path: str):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', path)]


def make_video_from_images(input_dir, output_path, fps=10, fourcc='mp4v'):
    input_path = Path(input_dir)
    output_path = Path(output_path)

    if not input_path.exists() or not input_path.is_dir():
        raise FileNotFoundError(f"Input folder not found: {input_path}")

    image_files = sorted(
        [p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}],
        key=lambda p: natural_sort_key(p.name),
    )

    if not image_files:
        raise FileNotFoundError(f"No image files found in {input_path}")

    first_image = cv2.imread(str(image_files[0]), cv2.IMREAD_UNCHANGED)
    if first_image is None:
        raise ValueError(f"Could not read image: {image_files[0]}")

    height, width = first_image.shape[:2]
    if len(first_image.shape) == 2:
        color_mode = cv2.IMREAD_GRAYSCALE
    else:
        color_mode = cv2.IMREAD_UNCHANGED

    output_path.parent.mkdir(parents=True, exist_ok=True)

    codec = cv2.VideoWriter_fourcc(*fourcc)
    writer = cv2.VideoWriter(str(output_path), codec, fps, (width, height))

    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer for {output_path}")

    for image_file in image_files:
        frame = cv2.imread(str(image_file), color_mode)
        if frame is None:
            print(f"Skipping unreadable file: {image_file}")
            continue

        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        if frame.shape[1] != width or frame.shape[0] != height:
            frame = cv2.resize(frame, (width, height))

        writer.write(frame)

    writer.release()
    print(f"Saved video to {output_path}")


class ImageToVideoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('PNG Folder to Video')
        self.root.geometry('520x220')

        tk.Label(root, text='Image folder:').grid(row=0, column=0, sticky='w', padx=10, pady=(10, 2))
        self.input_var = tk.StringVar()
        tk.Entry(root, textvariable=self.input_var, width=60).grid(row=1, column=0, padx=10, pady=2, sticky='ew')
        tk.Button(root, text='Select Folder', command=self.select_input_folder).grid(row=1, column=1, padx=10, pady=2)

        tk.Label(root, text='Output video:').grid(row=2, column=0, sticky='w', padx=10, pady=(10, 2))
        self.output_var = tk.StringVar(value='output.mp4')
        tk.Entry(root, textvariable=self.output_var, width=60).grid(row=3, column=0, padx=10, pady=2, sticky='ew')
        tk.Button(root, text='Save As', command=self.select_output_file).grid(row=3, column=1, padx=10, pady=2)

        tk.Label(root, text='FPS:').grid(row=4, column=0, sticky='w', padx=10, pady=(10, 2))
        self.fps_var = tk.StringVar(value='10')
        tk.Entry(root, textvariable=self.fps_var, width=10).grid(row=4, column=1, padx=10, pady=2, sticky='w')

        tk.Button(root, text='Create Video', command=self.create_video, width=20).grid(row=5, column=0, columnspan=2, pady=15)

        root.grid_columnconfigure(0, weight=1)

    def select_input_folder(self):
        folder = filedialog.askdirectory(title='Select folder containing PNG images')
        if folder:
            self.input_var.set(folder)
            if not self.output_var.get() or self.output_var.get() == 'output.mp4':
                default_name = os.path.join(folder, os.path.basename(folder) + '.mp4')
                self.output_var.set(default_name)

    def select_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title='Save video as',
            defaultextension='.mp4',
            filetypes=[('MP4 video', '*.mp4'), ('All files', '*.*')],
        )
        if file_path:
            self.output_var.set(file_path)

    def create_video(self):
        input_dir = self.input_var.get().strip()
        output_path = self.output_var.get().strip()

        if not input_dir:
            messagebox.showerror('Missing folder', 'Please select a folder containing image files.')
            return

        if not output_path:
            output_path = os.path.join(input_dir, 'video.mp4')

        try:
            fps = int(self.fps_var.get().strip() or '10')
            make_video_from_images(input_dir, output_path, fps=fps)
            messagebox.showinfo('Success', f'Video saved to:\n{output_path}')
        except Exception as exc:
            messagebox.showerror('Error', str(exc))


def main():
    parser = argparse.ArgumentParser(description='Create a video from a folder of images.')
    parser.add_argument('input_dir', nargs='?', help='Optional folder containing image frames')
    parser.add_argument('output_video', nargs='?', default='output.mp4', help='Optional output video path')
    parser.add_argument('--fps', type=int, default=10, help='Frames per second for the output video')
    parser.add_argument('--codec', default='mp4v', help='OpenCV video codec code (default: mp4v)')
    args = parser.parse_args()

    if args.input_dir:
        make_video_from_images(args.input_dir, args.output_video, fps=args.fps, fourcc=args.codec)
    else:
        root = tk.Tk()
        ImageToVideoGUI(root)
        root.mainloop()


if __name__ == '__main__':
    main()
