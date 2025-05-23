import sys
import os
import json
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QProgressBar, 
                            QFileDialog, QMessageBox, QGroupBox, QGridLayout,
                            QDialog, QDialogButtonBox, QLineEdit, QFrame, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QFont, QAction, QKeySequence, QShortcut, QIcon
from PIL import Image

class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(500, 250)
        
        self.current_settings = current_settings or {}
        self.setup_ui()
        self.load_current_settings()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        settings_group = QGroupBox("Folder Settings")
        settings_layout = QGridLayout()
        
        settings_layout.addWidget(QLabel("Source Folder:"), 0, 0)
        self.source_edit = QLineEdit()
        self.source_edit.setReadOnly(True)
        settings_layout.addWidget(self.source_edit, 0, 1)
        self.source_btn = QPushButton("Browse...")
        self.source_btn.clicked.connect(self.browse_source)
        settings_layout.addWidget(self.source_btn, 0, 2)
        
        settings_layout.addWidget(QLabel("Target Folder:"), 1, 0)
        self.target_edit = QLineEdit()
        self.target_edit.setReadOnly(True)
        settings_layout.addWidget(self.target_edit, 1, 1)
        self.target_btn = QPushButton("Browse...")
        self.target_btn.clicked.connect(self.browse_target)
        settings_layout.addWidget(self.target_btn, 1, 2)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        resume_group = QGroupBox("Resume Settings")
        resume_layout = QVBoxLayout()
        
        self.remember_position_cb = QCheckBox("Remember last position when reopening")
        self.remember_position_cb.setToolTip("When enabled, the program will remember where you left off and ask if you want to continue from that point")
        resume_layout.addWidget(self.remember_position_cb)
        
        resume_group.setLayout(resume_layout)
        layout.addWidget(resume_group)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                     QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def load_current_settings(self):
        if 'source_folder' in self.current_settings:
            self.source_edit.setText(self.current_settings['source_folder'])
        if 'target_folder' in self.current_settings:
            self.target_edit.setText(self.current_settings['target_folder'])
        if 'remember_position' in self.current_settings:
            self.remember_position_cb.setChecked(self.current_settings['remember_position'])
            
    def browse_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            self.source_edit.setText(folder)
            
    def browse_target(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Target Folder")
        if folder:
            self.target_edit.setText(folder)
            
    def get_settings(self):
        return {
            'source_folder': self.source_edit.text(),
            'target_folder': self.target_edit.text(),
            'remember_position': self.remember_position_cb.isChecked()
        }

class ImageLoaderThread(QThread):
    imageLoaded = pyqtSignal(str, object)
    loadError = pyqtSignal(str, str)
    
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        
    def run(self):
        try:
            with Image.open(self.filepath) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Load the full resolution image for better scaling
                temp_path = "temp_image.jpg"
                img.save(temp_path, "JPEG", quality=95)
                
                pixmap = QPixmap(temp_path)
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                self.imageLoaded.emit(self.filepath, pixmap)
                
        except Exception as e:
            self.loadError.emit(self.filepath, str(e))

class ScaledLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("border: 1px solid gray; background-color: black;")
        self.setText("No image loaded")
        self.original_pixmap = None
        
    def setPixmap(self, pixmap):
        self.original_pixmap = pixmap
        self.updatePixmap()
        
    def updatePixmap(self):
        if self.original_pixmap:
            scaled_pixmap = self.original_pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            super().setPixmap(scaled_pixmap)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_pixmap:
            self.updatePixmap()

class ImageSorterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Sorter")
        self.setGeometry(100, 100, 900, 800)
        
        # Set window icon
        if os.path.exists("assets/logo/icon.ico"):
            self.setWindowIcon(QIcon("assets/logo/icon.ico"))
        
        self.settings_file = "settings.json"
        self.session_file = "session.json"
        
        self.image_files = []
        self.current_index = 0
        self.processed_count = 0
        self.kept_count = 0
        self.current_image_path = None
        self.image_loader_thread = None
        
        self.supported_formats = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')
        
        self.settings = self.load_settings()
        
        self.setup_ui()
        self.setup_menu()
        self.setup_shortcuts()
        
        self.check_for_resume()
        
    def setup_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu('File')
        
        settings_action = QAction('Settings', self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        reset_session_action = QAction('Reset Session', self)
        reset_session_action.triggered.connect(self.reset_session)
        file_menu.addAction(reset_session_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
    def setup_shortcuts(self):
        self.keep_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.keep_shortcut.activated.connect(self.thumbs_up)
        
        self.dont_keep_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.dont_keep_shortcut.activated.connect(self.thumbs_down)
        
        self.skip_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.skip_shortcut.activated.connect(self.skip_image)
        
        self.keep_shortcut_k = QShortcut(QKeySequence('K'), self)
        self.keep_shortcut_k.activated.connect(self.thumbs_up)
        
        self.dont_keep_shortcut_d = QShortcut(QKeySequence('D'), self)
        self.dont_keep_shortcut_d.activated.connect(self.thumbs_down)
        
        self.skip_shortcut_s = QShortcut(QKeySequence('S'), self)
        self.skip_shortcut_s.activated.connect(self.skip_image)
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Top section with fixed height
        top_widget = QWidget()
        top_widget.setFixedHeight(200)  # Fixed height for top section
        top_layout = QVBoxLayout()
        top_widget.setLayout(top_layout)
        
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Ready to start")
        self.status_label.setFont(QFont("Arial", 10))
        status_layout.addWidget(self.status_label)
        
        self.stats_label = QLabel("")
        self.stats_label.setFont(QFont("Arial", 9))
        status_layout.addWidget(self.stats_label)
        
        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.progress_bar)
        
        status_group.setLayout(status_layout)
        top_layout.addWidget(status_group)
        
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Sorting")
        self.start_btn.clicked.connect(self.start_sorting)
        self.start_btn.setEnabled(self.can_start_sorting())
        control_layout.addWidget(self.start_btn)
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        control_layout.addWidget(self.settings_btn)
        
        control_layout.addStretch()
        top_layout.addLayout(control_layout)
        
        main_layout.addWidget(top_widget)
        
        # Image section that takes remaining space
        image_group = QGroupBox("Current Image")
        image_layout = QVBoxLayout()
        
        # Use custom scaling label with black background
        self.image_label = ScaledLabel()
        self.image_label.setText("No image loaded")
        image_layout.addWidget(self.image_label, 1)  # Stretch factor 1 to take available space
        
        self.filename_label = QLabel("")
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.filename_label.setFixedHeight(25)  # Fixed height
        image_layout.addWidget(self.filename_label)
        
        shortcuts_info = QLabel("Keyboard shortcuts: ← or D = Don't Keep | → or K = Keep | Space or S = Skip")
        shortcuts_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcuts_info.setFont(QFont("Arial", 9))
        shortcuts_info.setStyleSheet("color: #666; margin: 5px;")
        shortcuts_info.setFixedHeight(20)  # Fixed height
        image_layout.addWidget(shortcuts_info)
        
        # Bottom buttons section with fixed height
        action_layout = QHBoxLayout()
        
        self.thumbs_down_btn = QPushButton("👎 Don't Keep (←/D)")
        self.thumbs_down_btn.clicked.connect(self.thumbs_down)
        self.thumbs_down_btn.setEnabled(False)
        self.thumbs_down_btn.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        self.thumbs_down_btn.setFixedHeight(50)  # Fixed height
        action_layout.addWidget(self.thumbs_down_btn)
        
        self.skip_btn = QPushButton("⏭ Skip (Space/S)")
        self.skip_btn.clicked.connect(self.skip_image)
        self.skip_btn.setEnabled(False)
        self.skip_btn.setStyleSheet("QPushButton { font-size: 12px; padding: 8px; }")
        self.skip_btn.setFixedHeight(50)  # Fixed height
        action_layout.addWidget(self.skip_btn)
        
        self.thumbs_up_btn = QPushButton("👍 Keep (→/K)")
        self.thumbs_up_btn.clicked.connect(self.thumbs_up)
        self.thumbs_up_btn.setEnabled(False)
        self.thumbs_up_btn.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        self.thumbs_up_btn.setFixedHeight(50)  # Fixed height
        action_layout.addWidget(self.thumbs_up_btn)
        
        image_layout.addLayout(action_layout)
        image_group.setLayout(image_layout)
        main_layout.addWidget(image_group, 1)  # Stretch factor 1 to take remaining space
        
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
        return {}
        
    def save_settings(self):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
            
    def load_session(self):
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading session: {e}")
        return {}
        
    def save_session(self):
        if not self.settings.get('remember_position', False):
            return
            
        try:
            session_data = {
                'source_folder': self.settings.get('source_folder'),
                'target_folder': self.settings.get('target_folder'),
                'current_index': self.current_index,
                'processed_count': self.processed_count,
                'kept_count': self.kept_count,
                'total_files': len(self.image_files) if self.image_files else 0,
                'image_files': self.image_files
            }
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            print(f"Error saving session: {e}")
            
    def reset_session(self):
        try:
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
            QMessageBox.information(self, "Session Reset", "Session data has been cleared.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not reset session: {e}")
            
    def check_for_resume(self):
        if not self.settings.get('remember_position', False):
            return
            
        session_data = self.load_session()
        if not session_data or session_data.get('total_files', 0) == 0:
            return
            
        current_source = self.settings.get('source_folder')
        current_target = self.settings.get('target_folder')
        
        if (session_data.get('source_folder') == current_source and 
            session_data.get('target_folder') == current_target and
            session_data.get('current_index', 0) < session_data.get('total_files', 0)):
            
            progress = session_data.get('current_index', 0)
            total = session_data.get('total_files', 0)
            processed = session_data.get('processed_count', 0)
            kept = session_data.get('kept_count', 0)
            
            reply = QMessageBox.question(
                self, 
                "Resume Session", 
                f"Found previous sorting session:\n\n"
                f"Progress: {progress}/{total} images\n"
                f"Processed: {processed} images\n"
                f"Kept: {kept} images\n\n"
                f"Do you want to continue from where you left off?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.resume_session(session_data)
                
    def resume_session(self, session_data):
        try:
            self.image_files = session_data.get('image_files', [])
            self.current_index = session_data.get('current_index', 0)
            self.processed_count = session_data.get('processed_count', 0)
            self.kept_count = session_data.get('kept_count', 0)
            
            if self.image_files and self.current_index < len(self.image_files):
                self.progress_bar.setMaximum(len(self.image_files))
                self.progress_bar.setValue(self.current_index)
                
                self.start_btn.setEnabled(False)
                self.thumbs_up_btn.setEnabled(True)
                self.thumbs_down_btn.setEnabled(True)
                self.skip_btn.setEnabled(True)
                
                self.load_current_image()
            else:
                self.reset_session()
                
        except Exception as e:
            QMessageBox.warning(self, "Resume Error", f"Could not resume session: {e}")
            self.reset_session()
            
    def show_settings(self):
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_settings = dialog.get_settings()
            old_remember = self.settings.get('remember_position', False)
            new_remember = new_settings.get('remember_position', False)
            
            self.settings.update(new_settings)
            self.save_settings()
            self.start_btn.setEnabled(self.can_start_sorting())
            
            if old_remember and not new_remember:
                self.reset_session()
            
    def can_start_sorting(self):
        source_folder = self.settings.get('source_folder', '')
        target_folder = self.settings.get('target_folder', '')
        return bool(source_folder and target_folder and os.path.exists(source_folder))
                
    def start_sorting(self):
        source_folder = self.settings.get('source_folder')
        target_folder = self.settings.get('target_folder')
        
        if not source_folder or not os.path.exists(source_folder):
            QMessageBox.warning(self, "Warning", "Please select a valid source folder in settings.")
            return
            
        if not target_folder:
            QMessageBox.warning(self, "Warning", "Please select a target folder in settings.")
            return
            
        try:
            os.makedirs(target_folder, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create target folder: {e}")
            return
            
        self.find_image_files()
        
        if not self.image_files:
            QMessageBox.information(self, "Info", "No image files found in the source folder.")
            return
            
        self.current_index = 0
        self.processed_count = 0
        self.kept_count = 0
        
        self.progress_bar.setMaximum(len(self.image_files))
        self.progress_bar.setValue(0)
        
        self.start_btn.setEnabled(False)
        self.thumbs_up_btn.setEnabled(True)
        self.thumbs_down_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        
        self.load_current_image()
        
    def find_image_files(self):
        self.image_files = []
        source_folder = self.settings.get('source_folder')
        
        for root, dirs, files in os.walk(source_folder):
            for file in files:
                if file.lower().endswith(self.supported_formats):
                    self.image_files.append(os.path.join(root, file))
                    
        self.status_label.setText(f"Found {len(self.image_files)} image files")
        
    def load_current_image(self):
        if self.current_index >= len(self.image_files):
            self.sorting_complete()
            return
            
        self.current_image_path = self.image_files[self.current_index]
        self.filename_label.setText(os.path.basename(self.current_image_path))
        
        self.image_label.setText("Loading image...")
        
        self.image_loader_thread = ImageLoaderThread(self.current_image_path)
        self.image_loader_thread.imageLoaded.connect(self.on_image_loaded)
        self.image_loader_thread.loadError.connect(self.on_image_load_error)
        self.image_loader_thread.start()
        
        self.update_progress()
        self.save_session()
        
    def on_image_loaded(self, filepath, pixmap):
        if filepath == self.current_image_path:
            self.image_label.setPixmap(pixmap)
            
    def on_image_load_error(self, filepath, error_msg):
        if filepath == self.current_image_path:
            self.image_label.setText(f"Error loading image:\n{error_msg}")
            
    def update_progress(self):
        progress_text = f"Image {self.current_index + 1} of {len(self.image_files)}"
        percentage = ((self.current_index + 1) / len(self.image_files)) * 100
        progress_text += f" ({percentage:.1f}%)"
        self.status_label.setText(progress_text)
        
        stats_text = f"Processed: {self.processed_count} | Kept: {self.kept_count}"
        if self.processed_count > 0:
            keep_percentage = (self.kept_count / self.processed_count) * 100
            stats_text += f" ({keep_percentage:.1f}%)"
        self.stats_label.setText(stats_text)
        
        self.progress_bar.setValue(self.current_index + 1)
        
    def thumbs_up(self):
        if not self.thumbs_up_btn.isEnabled():
            return
        if self.current_image_path:
            self.copy_image_to_target()
            self.kept_count += 1
        self.next_image()
        
    def thumbs_down(self):
        if not self.thumbs_down_btn.isEnabled():
            return
        self.next_image()
        
    def skip_image(self):
        if not self.skip_btn.isEnabled():
            return
        self.current_index += 1
        self.load_current_image()
        
    def next_image(self):
        self.processed_count += 1
        self.current_index += 1
        self.load_current_image()
        
    def copy_image_to_target(self):
        if not self.current_image_path:
            return
            
        try:
            source_file = self.current_image_path
            filename = os.path.basename(source_file)
            target_folder = self.settings.get('target_folder')
            target_file = os.path.join(target_folder, filename)
            
            if os.path.exists(target_file):
                name, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(target_file):
                    new_filename = f"{name}_{counter}{ext}"
                    target_file = os.path.join(target_folder, new_filename)
                    counter += 1
                    
            shutil.copy2(source_file, target_file)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error copying file: {e}")
            
    def sorting_complete(self):
        self.thumbs_up_btn.setEnabled(False)
        self.thumbs_down_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        
        self.image_label.setText("Sorting Complete!")
        self.filename_label.setText("")
        
        completion_msg = f"Sorting completed!\n\nProcessed {self.processed_count} images\n"
        completion_msg += f"Kept {self.kept_count} images\n"
        if self.processed_count > 0:
            percentage = (self.kept_count / self.processed_count) * 100
            completion_msg += f"Keep rate: {percentage:.1f}%"
            
        QMessageBox.information(self, "Complete", completion_msg)
        
        if self.settings.get('remember_position', False):
            self.reset_session()
        
    def closeEvent(self, event):
        if self.image_loader_thread and self.image_loader_thread.isRunning():
            self.image_loader_thread.quit()
            self.image_loader_thread.wait()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Image Sorter")
    
    # Set application icon for taskbar
    if os.path.exists("assets/logo/icon.ico"):
        app.setWindowIcon(QIcon("assets/logo/icon.ico"))
    
    window = ImageSorterApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
