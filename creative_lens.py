import os
import traceback

import skimage
from colorthief import ColorThief
from PIL import Image, ImageOps
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QFileDialog, \
    QHBoxLayout, QSlider, QLineEdit, QDialog, QTextEdit, QMenuBar, QAction, QCheckBox, QDockWidget
from PyQt5.QtGui import QPixmap, QImage, QTransform
from PyQt5.QtCore import Qt

import cv2
import numpy as np
from PIL import Image, ExifTags
import piexif
import pyexiv2
import copy
from PyQt5.QtWidgets import QComboBox, QDialog
from PIL import Image
import os


def dominant_colors(image, num_colors, position, thickness_percentage, reverse_order=False):
    temp_path = "temp.jpg"
    image.save(temp_path)

    color_thief = ColorThief(temp_path)

    dominant_colors = color_thief.get_palette(color_count=num_colors)

    dominant_colors.sort(key=lambda c: sum(c))

    if reverse_order:
        dominant_colors = dominant_colors[::-1]

    image = Image.open(temp_path)

    width, height = image.size

    block_size_width, block_size_height = get_block_size(width, height, num_colors, position, thickness_percentage)

    if position.lower() == 'top':
        new_height = height + block_size_height
        new_image = Image.new('RGB', (width, new_height))
        x = 0
        y = block_size_height
        new_image.paste(image, (x, y))

    elif position.lower() == 'bottom':
        new_height = height + block_size_height
        new_image = Image.new('RGB', (width, new_height))
        x = 0
        y = 0
        new_image.paste(image, (x, y))

    elif position.lower() == 'left':
        new_width = width + block_size_width
        new_image = Image.new('RGB', (new_width, height))
        x = block_size_width
        y = 0
        new_image.paste(image, (x, y))

    elif position.lower() == 'right':
        new_width = width + block_size_width
        new_image = Image.new('RGB', (new_width, height))
        x = 0
        y = 0
        new_image.paste(image, (x, y))

    x = 0
    y = 0
    for color in dominant_colors:
        cube = Image.new('RGB', (block_size_width, block_size_height), color)
        if position.lower() == 'top':
            y = 0
        elif position.lower() == 'bottom':
            y = height
        elif position.lower() == 'left':
            x = 0
        elif position.lower() == 'right':
            x = width
        new_image.paste(cube, (x, y))
        if position.lower() == 'top' or position.lower() == 'bottom':
            x += block_size_width
        elif position.lower() == 'left' or position.lower() == 'right':
            y += block_size_height

    os.remove(temp_path)

    return new_image


def get_block_size(width, height, num_colors, position, thickness_percentage):
    if position.lower() == 'top' or position.lower() == 'bottom':
        block_size_width = width // num_colors
        block_size_height = thickness_percentage * block_size_width // 100

    elif position.lower() == 'left' or position.lower() == 'right':
        block_size_height = height // num_colors
        block_size_width = thickness_percentage * block_size_height // 100

    return block_size_width, block_size_height


def add_border(image, border_size_dict, border_color):
    try:
        left_border = int(border_size_dict.get('left', 0))
        right_border = int(border_size_dict.get('right', 0))
        top_border = int(border_size_dict.get('top', 0))
        bottom_border = int(border_size_dict.get('bottom', 0))
    except ValueError:
        print("Invalid border size.")
        return None

    bordered_image = ImageOps.expand(Image.fromarray(image.copy()),
                                     border=(left_border, top_border, right_border, bottom_border),
                                     fill=border_color)
    return np.array(bordered_image)


def open_convert_window(self):
    if self.image_path:
        convert_window = ConvertWindow(self.image_path, self.corrected_image, self)
        convert_window.exec_()


class FilmPhotoEditor(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Film Photo Editor")
        self.setGeometry(100, 100, 1000, 800)

        self.image_path = None
        self.original_image = None
        self.modified_image = None
        self.corrected_image = None

        self.red_changes = 0
        self.green_changes = 0
        self.blue_changes = 0

        # Add grayscale and sepia buttons
        self.grayscale_button = QPushButton("Grayscale")
        self.grayscale_button.setEnabled(False)
        self.grayscale_button.clicked.connect(self.apply_grayscale)

        self.sepia_button = QPushButton("Sepia")
        self.sepia_button.setEnabled(False)
        self.sepia_button.clicked.connect(self.apply_sepia)

        self.create_widgets()
        self.create_layout()
        self.create_menu_bar()
        self.update_slider_state()

        self.image_format = "JPEG"  # Default format

        # Initialize InformationWidget
        self.info_widget = InformationWidget()
        self.is_info_visible = True  # Flag to track if the information panel is visible

        # Initialize Original Image visibility flag
        self.is_original_image_visible = True

        # Add InformationWidget to the right-hand side of the main window
        self.info_dock_widget = QWidget()
        self.info_dock_widget.setLayout(QVBoxLayout())
        self.info_dock_widget.layout().addWidget(self.info_widget)
        self.info_dock_widget.setFixedWidth(250)

        self.info_dock = QDockWidget("Information")
        self.info_dock.setWidget(self.info_dock_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.info_dock)

        # Add Toggle Button to show/hide the information panel
        self.toggle_info_button = QPushButton("Hide Information")
        self.toggle_info_button.clicked.connect(self.toggle_info_panel)

        # Add Toggle Button to show/hide the original image
        self.toggle_original_image_button = QPushButton("Hide Original Image")
        self.toggle_original_image_button.clicked.connect(self.toggle_original_image)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e2429;
            }

            QWidget {
                background-color: #272e34;
                color: #FFFFFF;
            }

            QMainWindow::title {
                background-color: #272e34;
                color: #FFFFFF;
            }
        """)

    def create_widgets(self):
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_image)

        self.change_button = QPushButton("Invert Colors")
        self.change_button.setEnabled(False)
        self.change_button.clicked.connect(self.invert_colors)

        self.border_button = QPushButton("Add Border")
        self.border_button.setEnabled(False)
        self.border_button.clicked.connect(self.open_border_window)

        self.dominant_colors_button = QPushButton("Get Dominant Colors")
        self.dominant_colors_button.setEnabled(False)
        self.dominant_colors_button.clicked.connect(self.open_dominant_colors_window)

        self.back_button = QPushButton("Back")
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.restore_previous_changes)

        self.save_button = QPushButton("Save")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_image)

        self.metadata_button = QPushButton("Metadata")
        self.metadata_button.setEnabled(False)
        self.metadata_button.clicked.connect(self.open_metadata_window)

        self.rotate_left_button = QPushButton("Rotate Left")
        self.rotate_left_button.setEnabled(False)
        self.rotate_left_button.clicked.connect(self.rotate_left)

        self.rotate_right_button = QPushButton("Rotate Right")
        self.rotate_right_button.setEnabled(False)
        self.rotate_right_button.clicked.connect(self.rotate_right)

        self.original_image_label = QLabel("Original Image")
        self.original_image_label.setAlignment(Qt.AlignCenter)

        self.corrected_image_label = QLabel("Corrected Image")
        self.corrected_image_label.setAlignment(Qt.AlignCenter)

        self.red_label = QLabel("Red: 0")
        self.green_label = QLabel("Green: 0")
        self.blue_label = QLabel("Blue: 0")

        self.red_slider = QSlider(Qt.Horizontal)
        self.red_slider.setRange(0, 255)
        self.red_slider.setTickInterval(1)
        self.red_slider.setPageStep(10)
        self.red_slider.valueChanged.connect(self.red_slider_changed)

        self.green_slider = QSlider(Qt.Horizontal)
        self.green_slider.setRange(0, 255)
        self.green_slider.setTickInterval(1)
        self.green_slider.setPageStep(10)
        self.green_slider.valueChanged.connect(self.green_slider_changed)

        self.blue_slider = QSlider(Qt.Horizontal)
        self.blue_slider.setRange(0, 255)
        self.blue_slider.setTickInterval(1)
        self.blue_slider.setPageStep(10)
        self.blue_slider.valueChanged.connect(self.blue_slider_changed)

        # Add the new buttons to the function
        self.grayscale_button = QPushButton("Grayscale")
        self.grayscale_button.setEnabled(False)
        self.grayscale_button.clicked.connect(self.apply_grayscale)

        self.sepia_button = QPushButton("Sepia")
        self.sepia_button.setEnabled(False)
        self.sepia_button.clicked.connect(self.apply_sepia)

        self.convert_button = QPushButton("Convert Image")
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(self.open_convert_window)

        # Add the toggle button here
        self.toggle_info_button = QPushButton("Hide Information")
        self.toggle_info_button.clicked.connect(self.toggle_info_panel)

        # Add Toggle Button to show/hide the original image
        self.toggle_original_image_button = QPushButton("Hide Original Image")
        self.toggle_original_image_button.clicked.connect(self.toggle_original_image)

    def create_layout(self):
        layout = QVBoxLayout()
        top_layout = QHBoxLayout()

        top_layout.addWidget(self.browse_button)
        top_layout.addStretch(1)
        top_layout.addWidget(self.toggle_original_image_button)
        top_layout.addWidget(self.change_button)
        top_layout.addWidget(self.border_button)
        top_layout.addWidget(self.dominant_colors_button)
        top_layout.addWidget(self.back_button)
        top_layout.addWidget(self.save_button)
        top_layout.addWidget(self.metadata_button)
        top_layout.addWidget(self.rotate_left_button)
        top_layout.addWidget(self.rotate_right_button)
        top_layout.addWidget(self.grayscale_button)
        top_layout.addWidget(self.sepia_button)
        top_layout.addWidget(self.convert_button)
        top_layout.addWidget(self.toggle_info_button)


        layout.addLayout(top_layout)

        image_layout = QHBoxLayout()

        image_layout.addWidget(self.original_image_label)
        image_layout.addWidget(self.corrected_image_label)

        layout.addLayout(image_layout)

        layout.addStretch(1)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Red"))
        color_layout.addWidget(self.red_slider)
        color_layout.addWidget(self.red_label)
        color_layout.addWidget(QLabel("Green"))
        color_layout.addWidget(self.green_slider)
        color_layout.addWidget(self.green_label)
        color_layout.addWidget(QLabel("Blue"))
        color_layout.addWidget(self.blue_slider)
        color_layout.addWidget(self.blue_label)

        layout.addLayout(color_layout)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def create_menu_bar(self):
        menu_bar = QMenuBar()

        file_menu = menu_bar.addMenu("File")
        edit_menu = menu_bar.addMenu("Edit")
        help_menu = menu_bar.addMenu("Help")

        browse_action = QAction("Browse", self)
        browse_action.triggered.connect(self.browse_image)
        file_menu.addAction(browse_action)

        save_action = QAction("Save", self)
        save_action.setEnabled(False)
        save_action.triggered.connect(self.save_image)
        file_menu.addAction(save_action)

        invert_action = QAction("Invert Colors", self)
        invert_action.setEnabled(False)
        invert_action.triggered.connect(self.invert_colors)
        edit_menu.addAction(invert_action)

        back_action = QAction("Back", self)
        back_action.setEnabled(False)
        back_action.triggered.connect(self.restore_previous_changes)
        edit_menu.addAction(back_action)

        metadata_action = QAction("Metadata", self)
        metadata_action.setEnabled(False)
        metadata_action.triggered.connect(self.open_metadata_window)
        help_menu.addAction(metadata_action)

        self.setMenuBar(menu_bar)

    def browse_image(self):
        image_path, _ = QFileDialog.getOpenFileName(self, "Select Image", filter="Image files (*.jpg *.jpeg *.png)")
        if image_path:
            self.image_path = image_path
            self.load_image()
            self.update_slider_state()

            # Update information in the InformationWidget
            self.info_widget.update_info(self.image_path)

    def load_image(self):
        self.original_image = np.array(Image.open(self.image_path))
        self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_RGB2BGR)  # Added this line
        self.modified_image = self.original_image.copy()
        self.corrected_image = self.original_image.copy()

        self.display_image(self.original_image, self.original_image_label)
        self.display_image(self.corrected_image, self.corrected_image_label)

        self.change_button.setEnabled(True)
        self.border_button.setEnabled(True)
        self.dominant_colors_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self.back_button.setEnabled(False)
        self.metadata_button.setEnabled(True)
        self.rotate_left_button.setEnabled(True)
        self.rotate_right_button.setEnabled(True)
        self.grayscale_button.setEnabled(True)
        self.sepia_button.setEnabled(True)
        self.convert_button.setEnabled(True)

    def display_image(self, image, label):
        height, width, channel = image.shape
        bytes_per_line = 3 * width
        q_image = QImage(image.data, width, height, bytes_per_line,
                         QImage.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_image)
        pixmap = pixmap.scaled(600, 800, Qt.KeepAspectRatio)
        label.setPixmap(pixmap)

    def rotate_left(self):
        if self.corrected_image is not None:
            self.corrected_image = cv2.rotate(self.corrected_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            self.display_image(self.corrected_image, self.corrected_image_label)
            self.save_button.setEnabled(True)
            self.back_button.setEnabled(True)

    def rotate_right(self):
        if self.corrected_image is not None:
            self.corrected_image = cv2.rotate(self.corrected_image, cv2.ROTATE_90_CLOCKWISE)
            self.display_image(self.corrected_image, self.corrected_image_label)
            self.save_button.setEnabled(True)
            self.back_button.setEnabled(True)

    def invert_colors(self):
        if self.corrected_image is not None:
            img = self.corrected_image.copy()

            r, g, b = cv2.split(img)

            clip_rmax = np.percentile(r, 99)
            clip_gmax = np.percentile(g, 99)
            clip_bmax = np.percentile(b, 99)
            clip_rmin = np.percentile(r, 0)
            clip_gmin = np.percentile(g, 0)
            clip_bmin = np.percentile(b, 0)

            r_stretch = skimage.exposure.rescale_intensity(r, in_range=(clip_rmin, clip_rmax),
                                                           out_range=(0, 255)).astype(np.uint8)
            g_stretch = skimage.exposure.rescale_intensity(g, in_range=(clip_gmin, clip_gmax),
                                                           out_range=(0, 255)).astype(np.uint8)
            b_stretch = skimage.exposure.rescale_intensity(b, in_range=(clip_bmin, clip_bmax),
                                                           out_range=(0, 255)).astype(np.uint8)

            img_stretch = cv2.merge([r_stretch, g_stretch, b_stretch])
            inverted_img = 255 - img_stretch

            self.modified_image = inverted_img.copy()
            self.corrected_image = self.modified_image.copy()

            self.display_image(self.modified_image, self.corrected_image_label)
            self.save_button.setEnabled(True)
            self.back_button.setEnabled(True)

    def red_slider_changed(self, value):
        self.red_label.setText(f"Red: {value}")
        self.red_changes = value
        self.apply_rgb_changes()

    def green_slider_changed(self, value):
        self.green_label.setText(f"Green: {value}")
        self.green_changes = value
        self.apply_rgb_changes()

    def blue_slider_changed(self, value):
        self.blue_label.setText(f"Blue: {value}")
        self.blue_changes = value
        self.apply_rgb_changes()

    def apply_rgb_changes(self):
        self.corrected_image = self.modified_image.copy()

        self.corrected_image[:, :, 2] += self.red_changes
        self.corrected_image[:, :, 1] += self.green_changes
        self.corrected_image[:, :, 0] += self.blue_changes

        self.corrected_image = np.clip(self.corrected_image, 0, 255)

        self.display_image(self.corrected_image, self.corrected_image_label)
        self.save_button.setEnabled(True)
        self.back_button.setEnabled(True)

    def restore_previous_changes(self):
        self.corrected_image = self.modified_image.copy()

        self.display_image(self.corrected_image, self.corrected_image_label)
        self.save_button.setEnabled(True)
        self.back_button.setEnabled(False)

    def save_image(self):
        save_dialog = QFileDialog()
        save_path, _ = save_dialog.getSaveFileName(self, "Save Image", filter=f"Image files (*.{self.image_format.lower()})")
        if save_path:
            Image.fromarray(self.corrected_image).save(save_path, format=self.image_format)
            self.save_button.setEnabled(False)

    def update_slider_state(self):
        if self.image_path:
            self.red_slider.setEnabled(True)
            self.green_slider.setEnabled(True)
            self.blue_slider.setEnabled(True)
        else:
            self.red_slider.setEnabled(False)
            self.green_slider.setEnabled(False)
            self.blue_slider.setEnabled(False)

    def open_metadata_window(self):
        if self.image_path:
            metadata_window = MetadataWindow(self.image_path)
            metadata_window.exec_()

    def open_border_window(self):
        if self.image_path:
            border_window = BorderWindow(self.image_path, self.modified_image.copy(), self)
            border_window.exec_()

    def open_dominant_colors_window(self):
        if self.image_path:
            dominant_colors_window = DominantColorsWindow(self.image_path, self.modified_image.copy(), self)
            dominant_colors_window.exec_()

    def apply_grayscale(self):
        if self.corrected_image is not None:
            self.corrected_image = cv2.cvtColor(self.corrected_image, cv2.COLOR_BGR2GRAY)
            self.corrected_image = cv2.cvtColor(self.corrected_image, cv2.COLOR_GRAY2BGR)  # So it remains as a 3 channel image
            self.display_image(self.corrected_image, self.corrected_image_label)
            self.save_button.setEnabled(True)
            self.back_button.setEnabled(True)

    def apply_sepia(self):
        if self.corrected_image is not None:
            sepia_filter = np.array([[0.272, 0.534, 0.131],
                                     [0.349, 0.686, 0.168],
                                     [0.393, 0.769, 0.189]])
            self.corrected_image = cv2.transform(self.corrected_image, sepia_filter)
            self.corrected_image = np.clip(self.corrected_image, 0, 255)
            self.display_image(self.corrected_image, self.corrected_image_label)
            self.save_button.setEnabled(True)
            self.back_button.setEnabled(True)

    def open_convert_window(self):
        if self.image_path:
            convert_window = ConvertWindow(self.image_path, self.corrected_image, self)
            convert_window.exec_()

    def toggle_info_panel(self):
        if self.is_info_visible:
            self.info_dock.hide()
            self.toggle_info_button.setText("Show Information")
            self.is_info_visible = False
        else:
            self.info_dock.show()
            self.toggle_info_button.setText("Hide Information")
            self.is_info_visible = True

    def toggle_original_image(self):
        self.is_original_image_visible = not self.is_original_image_visible
        self.original_image_label.setVisible(self.is_original_image_visible)


class MetadataWindow(QDialog):
    def __init__(self, image_path):
        super().__init__()

        try:
            self.setWindowTitle("Image Metadata")
            self.setGeometry(100, 100, 400, 300)

            self.image_path = image_path

            self.metadata_text_edit = QTextEdit()
            self.metadata_text_edit.setReadOnly(False)

            self.save_button = QPushButton("Save")
            self.save_button.clicked.connect(self.save_metadata)

            self.layout = QVBoxLayout()
            self.layout.addWidget(self.metadata_text_edit)
            self.layout.addWidget(self.save_button)

            self.setLayout(self.layout)

            self.load_metadata()

        except Exception as e:
            print("An error occurred during initialization of MetadataWindow:")
            print(str(e))
            traceback.print_exc()

    def load_metadata(self):
        try:
            with Image.open(self.image_path) as img:
                exif_data = img.info.get("exif")
                if exif_data is not None:
                    exif_dict = piexif.load(exif_data)  # Convert bytes to dictionary

                    metadata_text = "Image Metadata:\n"
                    for ifd_name in exif_dict:  # We're now iterating over exif_dict
                        if ifd_name == "thumbnail":
                            continue
                        for tag_id, value in exif_dict[ifd_name].items():  # And here as well
                            tag_name = piexif.TAGS[ifd_name][tag_id]["name"]
                            if isinstance(value, bytes):
                                try:
                                    value = value.decode("utf-8")
                                except UnicodeDecodeError:
                                    value = str(value)
                            metadata_text += f"{tag_name}: {value}\n"

                    self.metadata_text_edit.setText(metadata_text)
                else:
                    self.metadata_text_edit.setText("No metadata found.")
        except Exception as e:
            self.metadata_text_edit.setText(f"An error occurred while loading metadata: {str(e)}")
            traceback.print_exc()

    def update_exif_data(self, exif_dict, new_data):
        for key, value in new_data.items():
            exif_dict["Exif"][key] = value
        return exif_dict

    def save_metadata(self):
        try:
            with Image.open(self.image_path) as img:
                exif_data = img.info.get("exif")
                if exif_data is not None:
                    exif_dict = piexif.load(exif_data)  # Convert bytes to dictionary
                else:
                    exif_dict = {}  # Or provide some default dictionary

                metadata_text = self.metadata_text_edit.toPlainText()
                new_data = {}
                for line in metadata_text.split("\n"):
                    if ":" in line:
                        tag_name, value = line.split(":", 1)
                        tag_name = tag_name.strip()
                        value = value.strip()
                        if tag_name in ExifTags.TAGS:
                            tag_id = ExifTags.TAGS[tag_name]
                            if isinstance(value, str):
                                new_data[tag_id] = value.encode("utf-8")
                            else:
                                new_data[tag_id] = value

                updated_exif_dict = self.update_exif_data(exif_dict, new_data)  # exif_dict is a dictionary

                # We need to convert the updated_exif_dict back to bytes to save it
                updated_exif_bytes = piexif.dump(updated_exif_dict)

                # Now save the updated_exif_bytes
                image = pyexiv2.Image(self.image_path)
                image.clear_exif()
                image.modify_exif(updated_exif_bytes)
                image.write()

                self.load_metadata()
        except Exception as e:
            self.metadata_text_edit.setText(f"An error occurred while saving metadata: {str(e)}")
            traceback.print_exc()


class BorderWindow(QDialog):
    def __init__(self, image_path, image, parent=None):
        super().__init__(parent)

        self.image_path = image_path
        self.image = image
        self.parent = parent

        self.setWindowTitle("Add Border")
        self.setGeometry(100, 100, 400, 300)

        # Added line edits for each border side
        self.border_size_left_line_edit = QLineEdit()
        self.border_size_left_line_edit.setText("100")
        self.border_size_right_line_edit = QLineEdit()
        self.border_size_right_line_edit.setText("100")
        self.border_size_top_line_edit = QLineEdit()
        self.border_size_top_line_edit.setText("100")
        self.border_size_bottom_line_edit = QLineEdit()
        self.border_size_bottom_line_edit.setText("700")

        self.border_color_line_edit = QLineEdit()
        self.border_color_line_edit.setText("White")

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_border)

        self.layout = QVBoxLayout()
        self.layout.addWidget(QLabel("Left Border Size"))
        self.layout.addWidget(self.border_size_left_line_edit)
        self.layout.addWidget(QLabel("Right Border Size"))
        self.layout.addWidget(self.border_size_right_line_edit)
        self.layout.addWidget(QLabel("Top Border Size"))
        self.layout.addWidget(self.border_size_top_line_edit)
        self.layout.addWidget(QLabel("Bottom Border Size"))
        self.layout.addWidget(self.border_size_bottom_line_edit)
        self.layout.addWidget(QLabel("Border Color"))
        self.layout.addWidget(self.border_color_line_edit)
        self.layout.addWidget(self.apply_button)

        self.setLayout(self.layout)

    def apply_border(self):
        border_size_dict = {'left': self.border_size_left_line_edit.text(),
                            'right': self.border_size_right_line_edit.text(),
                            'top': self.border_size_top_line_edit.text(),
                            'bottom': self.border_size_bottom_line_edit.text()}
        border_color = self.border_color_line_edit.text()

        self.parent.corrected_image = add_border(np.array(Image.fromarray(self.parent.corrected_image)),
                                                 border_size_dict,
                                                 border_color)
        self.parent.display_image(self.parent.corrected_image, self.parent.corrected_image_label)
        self.parent.save_button.setEnabled(True)
        self.parent.back_button.setEnabled(True)


class DominantColorsWindow(QDialog):
    def __init__(self, image_path, image, parent=None):
        super().__init__(parent)

        self.image_path = image_path
        self.image = image
        self.parent = parent

        self.setWindowTitle("Get Dominant Colors")
        self.setGeometry(100, 100, 400, 300)

        self.num_colors_line_edit = QLineEdit()
        self.num_colors_line_edit.setText("5")

        self.position_line_edit = QLineEdit()
        self.position_line_edit.setText("bottom")

        self.thickness_percentage_line_edit = QLineEdit()
        self.thickness_percentage_line_edit.setText("50")

        self.reverse_order_check_box = QCheckBox("Reverse Order")

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_dominant_colors)

        self.layout = QVBoxLayout()
        self.layout.addWidget(QLabel("Number of Colors"))
        self.layout.addWidget(self.num_colors_line_edit)
        self.layout.addWidget(QLabel("Position (top, bottom, left, right)"))
        self.layout.addWidget(self.position_line_edit)
        self.layout.addWidget(QLabel("Thickness Percentage"))
        self.layout.addWidget(self.thickness_percentage_line_edit)
        self.layout.addWidget(self.reverse_order_check_box)
        self.layout.addWidget(self.apply_button)

        self.setLayout(self.layout)

    def apply_dominant_colors(self):
        num_colors = int(self.num_colors_line_edit.text())
        position = self.position_line_edit.text()
        thickness_percentage = int(self.thickness_percentage_line_edit.text())
        reverse_order = self.reverse_order_check_box.isChecked()

        image_pil = Image.fromarray(self.parent.corrected_image)
        self.parent.corrected_image = np.array(
            dominant_colors(image_pil, num_colors, position, thickness_percentage, reverse_order))
        self.parent.display_image(self.parent.corrected_image, self.parent.corrected_image_label)
        self.parent.save_button.setEnabled(True)
        self.parent.back_button.setEnabled(True)


class ConvertWindow(QDialog):
    def __init__(self, image_path, image, parent=None):
        super().__init__(parent)

        self.image_path = image_path
        self.image = image
        self.parent = parent

        self.setWindowTitle("Convert Image")
        self.setGeometry(100, 100, 300, 120)

        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self.convert_image)

        self.image_types = QComboBox()
        self.image_types.addItems(["JPEG", "PNG", "BMP", "GIF", "TIFF"])

        self.layout = QVBoxLayout()
        self.layout.addWidget(QLabel("Image Type"))
        self.layout.addWidget(self.image_types)
        self.layout.addWidget(self.convert_button)

        self.setLayout(self.layout)

    def convert_image(self):
        image_type = self.image_types.currentText().upper()  # Store as uppercase
        self.parent.image_format = image_type
        self.close()


class InformationWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.init_ui()

    def init_ui(self):
        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(5)

        self.image_name_label = QLabel("Name:")
        self.file_type_label = QLabel("File Type:")
        self.size_label = QLabel("Size:")
        self.metadata_label = QLabel("Metadata:")

        self.info_layout.addWidget(self.image_name_label)
        self.info_layout.addWidget(self.file_type_label)
        self.info_layout.addWidget(self.size_label)
        self.info_layout.addWidget(self.metadata_label)

        self.setLayout(self.info_layout)

    def update_info(self, image_path):
        image_name = os.path.basename(image_path)
        self.image_name_label.setText(f"Name: {image_name}")

        file_type = os.path.splitext(image_path)[1][1:].upper()
        self.file_type_label.setText(f"File Type: {file_type}")

        size = os.path.getsize(image_path)
        self.size_label.setText(f"Size: {size} bytes")

        metadata = self.get_image_metadata(image_path)
        self.metadata_label.setText(f"Metadata:\n{metadata}")

    def get_image_metadata(self, image_path):
        try:
            with Image.open(image_path) as img:
                exif_data = img.info.get("exif")
                if exif_data is not None:
                    exif_dict = piexif.load(exif_data)  # Convert bytes to dictionary
                    metadata_text = ""
                    for ifd_name in exif_dict:
                        if ifd_name == "thumbnail":
                            continue
                        for tag_id, value in exif_dict[ifd_name].items():
                            tag_name = piexif.TAGS[ifd_name].get(tag_id, tag_id)
                            if isinstance(value, bytes):
                                try:
                                    value = value.decode("utf-8")
                                except UnicodeDecodeError:
                                    value = str(value)
                            metadata_text += f"{tag_name}: {value}\n"
                    return metadata_text
                else:
                    return "No metadata found."
        except Exception as e:
            print(f"Error getting metadata: {e}")
            return "Error getting metadata."



if __name__ == "__main__":
    app = QApplication([])
    editor = FilmPhotoEditor()
    editor.show()
    app.exec_()
