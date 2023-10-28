import os
import re
import sys
import requests
import threading
import subprocess
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QIcon, QColor, QPixmap, QPainter
from PyQt5.QtCore import Qt, pyqtSlot, QDateTime, QThread
from PyQt5.QtWidgets import QMessageBox, QProgressDialog, QPushButton, QMainWindow, QListWidget, QDialog, QFileDialog
from bs4 import BeautifulSoup
from pySmartDL import SmartDL
from functools import partial
import pickle
import shutil
import time
import psutil
import configparser
from tqdm import tqdm
import ctypes

# Path to 7-Zip executable (7z.exe)
seven_zip_path = 'C:\\Program Files\\7-Zip\\7z.exe'

# Path to the 7z archive and the output folder
archive_path = ''
output_folder = 'output_folder'

# Use 7-Zip to extract the archive
subprocess.call([seven_zip_path, 'x', archive_path, f'-o{output_folder}'])

icon_path = "resources/icons/icon.ico"
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VoidLauncher")
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(icon_path)

class Config:
    config_file = "config.ini"

    @classmethod
    def get_config_path(cls):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, cls.config_file)

    @classmethod
    def ensure_config_file_exists(cls):
        exe_dir = os.path.dirname(sys.executable)
        config_path = cls.get_config_path()
        if not os.path.exists(config_path):
            # Create the config file with default values
            config = configparser.ConfigParser()
            config["Paths"] = {"game_destination_folder": os.path.join(exe_dir, "game")}
            config["Settings"] = {
                "disable_initial_dialog": "False",
                "last_refresh_time": "" 
            }
            
            with open(config_path, "w") as configfile:
                config.write(configfile)
                
    @classmethod
    def get_last_refresh_time(cls):
        cls.ensure_config_file_exists() 
        config = configparser.ConfigParser()
        config.read(cls.get_config_path())
        return config.get("Settings", "last_refresh_time")

    @classmethod
    def set_last_refresh_time(cls, value):
        cls.ensure_config_file_exists()
        config = configparser.ConfigParser()
        config.read(cls.get_config_path())
        config.set("Settings", "last_refresh_time", value)

        with open(cls.get_config_path(), "w") as configfile:
            config.write(configfile)
    @classmethod
    def get_game_destination_folder(cls):
        cls.ensure_config_file_exists()
        config = configparser.ConfigParser()
        config.read(cls.get_config_path())
        return config.get("Paths", "game_destination_folder")
    
    @classmethod
    def set_game_destination_folder(cls, new_folder):
        cls.ensure_config_file_exists() 
        config = configparser.ConfigParser()
        config.read(cls.get_config_path())
        config.set("Paths", "game_destination_folder", new_folder)

        with open(cls.get_config_path(), "w") as configfile:
            config.write(configfile)

    @classmethod
    def get_disable_initial_dialog(cls):
        cls.ensure_config_file_exists() 
        config = configparser.ConfigParser()
        config.read(cls.get_config_path())
        return config.getboolean("Settings", "disable_initial_dialog")

    @classmethod
    def set_disable_initial_dialog(cls, value):
        cls.ensure_config_file_exists()
        config = configparser.ConfigParser()
        config.read(cls.get_config_path())
        config.set("Settings", "disable_initial_dialog", str(value))

        with open(cls.get_config_path(), "w") as configfile:
            config.write(configfile)

    @classmethod
    def get_archived_installs_folder(cls):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, "archives")

class DownloadWorker(QtCore.QObject):
    update_download_progress = QtCore.pyqtSignal(int)
    download_error = QtCore.pyqtSignal(str)
    download_completed = QtCore.pyqtSignal()
    extract_file = QtCore.pyqtSignal()
    update_extract_progress = QtCore.pyqtSignal(int)
    extraction_completed = QtCore.pyqtSignal()

    def __init__(self):        
        self.archived_installs_path = Config.get_archived_installs_folder()
        self.game_destination_path = Config.get_game_destination_folder()
        self.output_folder = ""
        self.cancelled = False
        super().__init__()

    def start_download(self, url):
        self.cancelled = False
        os.makedirs(self.archived_installs_path, exist_ok=True)
        filename = url.split("/")[-1]
        local_file_path = os.path.join(self.archived_installs_path, filename)
        obj = SmartDL(url, local_file_path, progress_bar=False)
        obj.start(blocking=False)

        while obj.get_status() == "downloading":
            progress = int(obj.get_progress() * 100)
            self.update_download_progress.emit(progress)
            if self.cancelled:
                print(self.cancelled)
                obj.stop
                return
            
        if obj.isSuccessful():
            self.download_completed.emit()
            self.extract_file.emit()
        else:
            self.download_error.emit("Download failed")
    def extract_and_move_thread(self):
        extraction_thread = threading.Thread(target=self.start_extraction_and_move)
        extraction_thread.start()

    def start_extraction_and_move(self):
        try:
            if not os.path.exists(self.archived_installs_path) or not os.path.exists(self.game_destination_path):
                os.makedirs(self.game_destination_path)  # Create the destination path if it doesn't exist

            seven_zip_path = 'C:\\Program Files\\7-Zip\\7z.exe'

            for root, _, files in os.walk(self.archived_installs_path):
                for file in files:
                    if file.endswith(".7z"):
                        print("found 7z file")
                        source_file = os.path.join(root, file)
                        self.output_folder = self.game_destination_path  # Use game_destination_path as the output folder
                        print(self.output_folder)

                        if os.path.exists(seven_zip_path):
                            subprocess.call([seven_zip_path, 'x', source_file, '-o' + self.output_folder, '-y'])
                        else:
                            print("7-Zip not found. Please install 7-Zip to extract 7z archives.")
                            return

                        os.remove(source_file)
                        print(f"Extracted and deleted: {source_file}")
                        self.extraction_completed.emit()
        except Exception as e:
            print(f"Extraction error: {str(e)}")

class CustomListWidget(QListWidget):
    def __init__(self):
        super().__init__()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            selected_item = self.currentItem()
            if selected_item:
                print(f"Selected item: {selected_item.text()}")

        super().keyPressEvent(event)

class InitialDialog(QDialog):
    def __init__(self, config, dialog_text):
        super().__init__()

        self.setWindowTitle("IMPORTANT!")
        self.setWindowFlag(Qt.Dialog)
        screen_geometry = QtWidgets.QDesktopWidget().screenGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.setGeometry(x, y, 400, 150)

        label = QtWidgets.QLabel(dialog_text)

        self.ok_button = QPushButton("I understand")

        button_layout = QtWidgets.QVBoxLayout()
        button_layout.addWidget(label)
        button_layout.addWidget(self.ok_button)
        self.ok_button.clicked.connect(self.accept)

        self.setLayout(button_layout)

        # Store the configuration
        self.config = config

class VoidLauncher(QMainWindow):

    def __init__(self, download_worker, game_fetch_worker):
        super().__init__()  
        self.resize(1280, 720)
        app_icon = QIcon("resources/icons/icon.ico")  # Replace "path_to_your_icon.ico" with the actual path to your icon file        
        self.setWindowTitle("Void Launcher")
        app.setWindowIcon(app_icon)
        self.selected_game_names = ["VotV-Win64-Shipping.exe"]
        self.selected_game_name = ""
        self.script_directory = os.path.dirname(sys.argv[0])
        self.download_worker = download_worker
        self.game_fetch_worker = game_fetch_worker
        self.archived_installs_path = Config.get_archived_installs_folder()
        self.game_destination_path = Config.get_game_destination_folder()
        self.version_name_map = self.game_fetch_worker.get_version_name_map
        self.version_description_map = self.game_fetch_worker.get_version_description_map
        self.version_download_link_map = self.game_fetch_worker.version_download_link_map        
        self.final_descriptions_map = self.game_fetch_worker.get_final_descriptions_map
        self.version_names = self.game_fetch_worker.get_version_names
        self.current_exe_path = ""
        self.current_description = ""
        self.current_download_link = ""
        self.selected_version = ""
        self.game_exe = ""
        self.game_path = ""             
        self.game_process = None
        self.config = Config()
        dialog_text = "Playing many older builds of Voices of the Void WILL reset your stats and\nachievements!\n\nIf you already have a version of Voices of the Void installed then make sure\nto add it to the library and launch through this program at least once!\n\nThis will back up your data and stop it from getting permanently deleted."
        if not self.config.get_disable_initial_dialog():
            initial_dialog = InitialDialog(self.config, dialog_text)
            result = initial_dialog.exec_()
        self.init_ui()
        self.init_download_worker()
        self.init_game_fetch_worker()
        self.show()

    def init_download_worker(self):
        self.download_thread = QtCore.QThread()
        self.download_worker.moveToThread(self.download_thread)
        self.download_worker.update_download_progress.connect(self.update_download_progress)
        self.download_worker.download_error.connect(self.download_error)
        self.download_worker.download_completed.connect(self.download_finished)
        self.download_worker.extract_file.connect(self.extract_file)
        self.download_worker.extraction_completed.connect(self.extraction_finished)
        self.download_thread.start()

    def init_game_fetch_worker(self):
        self.fetch_thread = QtCore.QThread()
        self.game_fetch_worker.moveToThread(self.fetch_thread)
        self.game_fetch_worker.game_fetch_worker_fetch_game_exe.connect(self.game_fetch_worker_fetch_game_exe)
        download_function = partial(self.game_fetch_worker.fetch_game_versions)
        threading.Thread(target=download_function).start()
        self.fetch_thread.start()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.dragPosition = None
        self.setupLayout()
        self.setupTitleBar()
        self.setupTabWidget()
        self.setupLibraryTab()
        self.setupDownloadsTab()
        self.setupSettingsTab()
        self.setupInfoTab()
        self.setupHtmlContent()
        self.setupStyles()
        self.connectActions()
        additional_text = QtWidgets.QLabel("Created by @Tameranian3d/Tameranian, in collaboration with @entechcore/user#5555 (Version 0.2)")
        additional_text.setStyleSheet("color: white;")
        additional_text.setAlignment(Qt.AlignCenter)

        self.layout.addWidget(additional_text, 2, 0, 1, 2)

    def setupStyles(self):
        dark_mode_stylesheet = """
            QMainWindow {
                background-image: url('resources/background.jpg');
                background-color: #1C1C1C;
                background-size: cover;
                background-position: center center;
                background-repeat: no-repeat;
                color: white;
                selection-background-color: #8E2DC5;
                selection-color: white;
            }

            QTabWidget::pane {
                border: 0;
            }

            QTabWidget::tab-bar {
                alignment: left;
            }

            QTabBar::tab {
                background: #444;
                color: white;
                min-width: 100px;
            }

            QTabBar::tab:selected {
                background: #555;
            }

            QListWidget {
                background-color: #1C1C1C;
                color: white;
                selection-background-color: #8E2DC5;
                selection-color: white;
            }

            QTextBrowser {
                background-color: #1C1C1C;
                color: white;
                font-size: 15px;
            }

            QPushButton {
                background-color: #444;
                color: white;
                border: 1px solid #666;
                border-radius: 5px;
                padding: 5px 10px;
            }

            QPushButton:hover {
                background-color: #555;
            }

            QSplitter {
                background-color: #1C1C1C;
            }

            QListWidget::item {
                padding: 5px;
                border: 1px solid #666;
                border-radius: 5px;
                margin: 5px;
            }

            QListWidget::item:selected {
                background-color: #8E2DC5;
                color: white;
            }

            QListWidget::item:focus {
                border: none; 
            }
        """
        self.setStyleSheet(dark_mode_stylesheet)
        self.versions_list.setStyleSheet(dark_mode_stylesheet)
        self.description_text.setStyleSheet(dark_mode_stylesheet)
        self.game_name_list.setStyleSheet(dark_mode_stylesheet)
        self.download_button.setStyleSheet(dark_mode_stylesheet)
        self.reload_data.setStyleSheet(dark_mode_stylesheet)

    def setupHtmlContent(self):        
        self.html_content = ""
        self.description_text.setHtml(self.html_content)
    
    def setupLayout(self):
        self.central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QtWidgets.QGridLayout()
        self.central_widget.setLayout(self.layout)

    def setupTitleBar(self):
        self.title_bar = TitleBar(self)
        self.layout.addWidget(self.title_bar, 0, 0, 1, 2)

    def setupTabWidget(self):
        self.tab_widget = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tab_widget, 1, 0, 1, 2)
        self.tab_widget.setContentsMargins(0, 0, 0, 0)
        self.tab_widget.setStyleSheet("QTabWidget::pane { border: 0; }")
        self.tab_names = ["Library", "Downloads", "Info", "Settings"]
        self.tabs = []

        for name in self.tab_names:
            tab = QtWidgets.QWidget()
            self.tabs.append(tab)
            self.tab_widget.addTab(tab, name)

    def setupLibraryTab(self):
        self.tab0_layout = QtWidgets.QVBoxLayout(self.tabs[0])
        self.game_name_list = CustomListWidget()
        self.game_name_list.setFocusPolicy(Qt.NoFocus)
        self.tab0_layout.addWidget(self.game_name_list)
        
        button_layout = QtWidgets.QHBoxLayout()
        
        self.add_game_install_button = QPushButton("Manually Add Installed Version")
        self.add_game_install_button.setMaximumWidth(400)
        self.add_game_install_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        button_layout.addWidget(self.add_game_install_button, alignment=Qt.AlignCenter)                   
        
        self.game_path_button = QPushButton("Open Library Folder")
        self.game_path_button.setMaximumWidth(400)
        self.game_path_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        button_layout.addWidget(self.game_path_button, alignment=Qt.AlignCenter)                   
        
        self.game_backup_path_button = QPushButton("Open Save Backups")
        self.game_backup_path_button.setMaximumWidth(400)
        self.game_backup_path_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        button_layout.addWidget(self.game_backup_path_button, alignment=Qt.AlignCenter)                   
        
        self.refesh_library = QPushButton("Refresh Library")
        self.refesh_library.setMaximumWidth(400)
        self.refesh_library.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        button_layout.addWidget(self.refesh_library, alignment=Qt.AlignCenter)                   

        button_layout.addStretch()
                
        self.launch_button = QPushButton("Launch Game")
        self.launch_button.setMaximumWidth(150)
        self.launch_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        button_layout.addWidget(self.launch_button, alignment=Qt.AlignRight)
        
        self.tab0_layout.addLayout(button_layout)

    def setupDownloadsTab(self):
        self.tab1_layout = QtWidgets.QVBoxLayout(self.tabs[1])
        self.download_button = QtWidgets.QPushButton("Download")
        
        self.reload_data = self.game_fetch_worker.get_reload_data()
        self.versions_list = self.game_fetch_worker.get_versions_list()
        self.versions_list.setStyleSheet("""
            font-size: 18px;
            QListWidget::item:selected {
                border: 1px solid transparent;
                background-color: #8E2DC5;
                color: white;
            }
        """)
        self.versions_list.setFocusPolicy(Qt.NoFocus)
        self.description_text = self.game_fetch_worker.get_description_text()
        self.description_text.setOpenExternalLinks(True)
        self.description_text.setOpenLinks(True)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.tab1_layout.addWidget(self.splitter)
        self.splitter.addWidget(self.versions_list)
        self.splitter.addWidget(self.description_text)
        self.tab1_layout.addWidget(self.reload_data)
        self.tab1_layout.addWidget(self.download_button)

    def setupSettingsTab(self):
        self.tab2_layout = QtWidgets.QVBoxLayout(self.tabs[3])  # Use QVBoxLayout for vertical layout

        # Create a horizontal layout for the label and checkbox
        toggle_layout = QtWidgets.QHBoxLayout()

        self.toggle_label = QtWidgets.QLabel("Disable Startup Dialog")
        self.toggle_label.setStyleSheet("color: white;margin-left: 500px;")  # Set text color to white   

        self.toggle_startup_button = QtWidgets.QCheckBox()  # Use QCheckBox for the toggle
        initial_state =  self.config.get_disable_initial_dialog()  # Invert the config value
        self.toggle_startup_button.setChecked(initial_state)

        toggle_layout.addWidget(self.toggle_label)  # Add the label to the horizontal layout
        toggle_layout.addWidget(self.toggle_startup_button)  # Add the checkbox to the horizontal layout

        # Add the horizontal layout to the vertical layout
        self.tab2_layout.addLayout(toggle_layout)
        
        # Align the items within the horizontal layout to the top
        toggle_layout.setAlignment(QtCore.Qt.AlignTop)

    def setupInfoTab(self):
        self.tab3_layout = QtWidgets.QVBoxLayout(self.tabs[2])
        
        # Create a QTextBrowser to display information with links
        info_text = QtWidgets.QTextBrowser()
        info_text.setOpenExternalLinks(True)
        info_text.setOpenLinks(True)
        
        # Example text with links
        info_text.setHtml('''
            <div style="margin: 24px;">
                <p style="font-size: 24px; color: white; text-align: center;">
                    <b>Thank you for installing Void Launcher!</b>
                </p>
                          <br>
                <p style="font-size: 20px; color: white; text-align: center;">
                    Coding this program was my first experience with Python! There may be some issues so please be patient as I work to iron out the bugs!
                </p>
                          <br>
                <p style="font-size: 20px; color: white; text-align: center;">
                    As stated in the startup text, please make sure to back up your data before launching older versions of the game. It won't remove your saves as long as you don't load a newer save in an old version, but it will reset all your stats, achievements, and such. Starting up any version of Voices of the Void through this launcher will automatically save your data to the respective version's name.
                </p>
                          <br>
                <p style="font-size: 20px; color: white; text-align: center;">
                    You can access the save backup folder in the 'Library' tab.
                </p>
                </p>
                          <br>
                <p style="font-size: 20px; color: white; text-align: center;">
                    Void Launcher also works with Steam Overlay! Add 'VoidLauncher.exe' as a non steam then Launch any installed game through the launcher!
                </p>
                          <br>
                <p style="font-size: 20px; color: white; text-align: center;">
                    Void Launcher would not have been possible without @entechcore/user#5555's website for hosting the files and their cooperation in making the site more friendly to parse the data from. If you have any queries, suggestions, or issues with the launcher, please contact me on Discord at @Tameranian, or email me at Tameraniantv@gmail.com.
                </p>
                          <br>
                <p style="font-size: 20px; color: white; text-align: center;">
                    This launcher has no affiliation with EternityDev/MrDrNose, the creator of Voices of the Void, It was made because I thought it'd be neat :D.
                </p>
                <br>
                <p style="font-size: 20px; color: white; text-align: center;">
                    Go support the creator of Voices of the Void on Patreon <a href="https://www.patreon.com/eternitydev" style="color: #007BFF; text-decoration: none;">here</a>.
                </p>
                <br>
                <p style="font-size: 20px; color: white; text-align: center;">
                    Join the Voices of the Void Discord <a href="https://discord.com/invite/WKBvqu4tjV" style="color: #007BFF; text-decoration: none;">here</a>.
                </p>
            </div>
        ''')
        self.tab3_layout.addWidget(info_text)
   
    def connectActions(self):
        initial_index = 2 if not self.config.get_disable_initial_dialog() else 0
        self.tab_widget.setCurrentIndex(initial_index)
        self.versions_list.itemSelectionChanged.connect(self.load_selected_description)
        self.game_name_list.itemSelectionChanged.connect(self.load_selected_game_exe)
        self.download_button.clicked.connect(self.showDownloadDialog)
        self.reload_data.clicked.connect(self.refetch)
        self.launch_button.clicked.connect(self.launch_game)
        self.toggle_startup_button.clicked.connect(self.toggleStartupDialog)
        self.game_path_button.clicked.connect(self.open_libray)
        self.add_game_install_button.clicked.connect(self.add_game_install)
        self.refesh_library.clicked.connect(lambda: self.fetch_game_exe(self.game_destination_path))
        self.game_backup_path_button.clicked.connect(self.open_game_backup_folder)
    
    def toggleStartupDialog(self):
        # Update the configuration based on the checkbox state
        self.config.set_disable_initial_dialog(self.toggle_startup_button.isChecked())
  
    def open_libray(self):
        if self.game_destination_path:
            subprocess.Popen(['explorer', self.game_destination_path], shell=True)

    def add_game_install(self):
        if self.game_destination_path:
            # Prompt the user to select a folder using a native file dialog
            folder_dialog = QFileDialog.getExistingDirectory(
                None,
                "Select a folder",
                options=QFileDialog.ShowDirsOnly
            )

            if folder_dialog:
                # Check if "votv.exe" is in the selected folder
                votv_exe_path = os.path.join(folder_dialog, "votv.exe")
                parent_name = os.path.basename(folder_dialog)

                if os.path.isfile(votv_exe_path):
                    # Create a subfolder with the name of the parent folder
                    destination_folder = os.path.join(self.game_destination_path, parent_name)
                    try:
                        shutil.copytree(folder_dialog, destination_folder, dirs_exist_ok=True)
                        subprocess.Popen(['explorer', destination_folder], shell=True)
                    except Exception as e:
                        QMessageBox.critical(None, "Error", f"An error occurred: {str(e)}")
                else:
                    # Check if "votv.exe" is in the "WindowsNoEditor" subfolder
                    votv_exe_path = os.path.join(folder_dialog, "WindowsNoEditor", "votv.exe")

                    if os.path.isfile(votv_exe_path):
                        # Create a subfolder named "WindowsNoEditor" for "votv.exe"
                        destination_folder = os.path.join(self.game_destination_path, parent_name, "WindowsNoEditor")
                        try:
                            shutil.copytree(os.path.dirname(votv_exe_path), destination_folder, dirs_exist_ok=True)
                        except Exception as e:
                            QMessageBox.critical(None, "Error", f"An error occurred: {str(e)}")
                    else:
                        QMessageBox.warning(None, "Warning", "No 'votv.exe' found in the selected folder or its subfolders.")
   
    def open_game_backup_folder(self):
        if self.game_destination_path:
            game_backups_path = os.path.join(self.script_directory, "game backups")
            source_save_folder = os.path.join(os.path.expanduser("~"), "AppData", "Local", "VotV", "Saved")

            if not os.path.exists(game_backups_path) or not os.path.isdir(game_backups_path):
                os.makedirs(game_backups_path)

            # Create startup information for the left and right positions
            left_startupinfo = subprocess.STARTUPINFO()
            left_startupinfo.dwX = 100  # Set the X position for the left window

            right_startupinfo = subprocess.STARTUPINFO()
            right_startupinfo.dwX = 800  # Set the X position for the right window

            subprocess.Popen(['explorer', game_backups_path], shell=True, startupinfo=left_startupinfo)
            subprocess.Popen(['explorer', source_save_folder], shell=True, startupinfo=right_startupinfo)

    def toggle_input(self, state):
        if state == Qt.Checked:
            self.file_path_input.setDisabled(False)
            self.file_path_label.setStyleSheet("color: white;")
            self.file_path_input.setStyleSheet("color: black;")
            self.action_button.setStyleSheet("color: white;")
            self.action_button.setDisabled(False)
        else:
            self.file_path_input.setDisabled(True)
            self.file_path_label.setStyleSheet("color: gray;")
            self.file_path_input.setStyleSheet("color: gray;")
            self.action_button.setStyleSheet("color: gray;")

            self.action_button.setDisabled(True)

    def showDownloadDialog(self):       
        if self.selected_version in self.game_fetch_worker.get_version_download_link_map():
            selected_download_link =  self.game_fetch_worker.get_version_download_link_map()[self.selected_version]
            print(self.selected_version)
            download_dialog = QMessageBox()
            download_dialog.setWindowTitle("Download Confirmation")
            download_dialog.setText(f'Would you like to download "{self.selected_version}"?\n\nFiles provided by entechcore at invotek.net')
            download_dialog.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            download_dialog.setDefaultButton(QMessageBox.Ok)

            result = download_dialog.exec_()
            if result == QMessageBox.Ok:
                download_function = partial(self.download_file, selected_download_link)
                threading.Thread(target=download_function).start()
        else:
            print(f"No exact matching version found for '{self.selected_version}'")

    def download_file(self, url):        
        self.progress_dialog = QProgressDialog(f'Downloading "{self.selected_version}"', 'Cancel', 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        cancel_buttons = self.progress_dialog.findChildren(QPushButton)
        self.progress_dialog.canceled.connect(self.cancel_download)
        if cancel_buttons:
            cancel_buttons[0].hide()
        self.progress_dialog.setParent(self)
        self.progress_dialog.setWindowTitle("Downloading")
        QtWidgets.qApp.processEvents()

        self.download_worker.start_download(url)
    
    pyqtSlot(int)
    def update_download_progress(self, progress):
        self.progress_dialog.setValue(progress)        

    pyqtSlot()
    def cancel_download(self):        
        self.download_worker.cancelled = True 
        self.progress_dialog.close()
        msg_box = QMessageBox(self)
        msg_box.setWindowModality(Qt.ApplicationModal)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Download Cancelled!")
        msg_box.setText(f'"{self.selected_version}" has stopped downloading!')
        msg_box.addButton(QMessageBox.Ok)        
        self.progress_dialog.close()
        msg_box.exec_()
        
    pyqtSlot(str)
    def download_error(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Download Error", f"Download error: {error_message}", QMessageBox.Ok)
        print(f"Download Error: {error_message}")

    pyqtSlot()
    def download_finished(self):        
        print("Download Completed")

    pyqtSlot()
    def extract_file(self):                                                               
        QtWidgets.qApp.processEvents()        
        #selected_item = self.versions_list.currentItem()
        #selected_version = selected_item.text()
        #self.extract_dialog = QProgressDialog(f'"Extracting" {selected_version}', "Cancel", 0, 100, self)
        #self.extract_dialog.setWindowModality(Qt.WindowModal)        
        #self.extract_dialog.setAutoClose(True)
        #cancel_buttons = self.extract_dialog.findChildren(QPushButton)
        #if cancel_buttons:
        #    cancel_buttons[0].hide()
        #self.extract_dialog.setWindowTitle("Extracting")
        #self.extract_dialog.show()

        self.download_worker.extract_and_move_thread()

    #pyqtSlot()
    #def update_extract_progress(self, progress):
        #self.extract_dialog.setValue(progress)   

    pyqtSlot()
    def extraction_finished(self):   
        selected_item = self.versions_list.currentItem()
        selected_version = selected_item.text()
        self.fetch_game_exe(self.game_destination_path)
        QMessageBox.information(self, "Download Completed", f'"{selected_version}" has installed successfully.\n\nCheck your library!', QMessageBox.Ok)
        print("Download Completed")

    def fetch_game_exe(self, folder_path):
        try:
            self.game_name_list.clear()
            if not os.path.exists(folder_path):
                print(f"Directory '{folder_path}' does not exist.")
                return
            game_exe = []

            self.search_for_votv_exe(folder_path, game_exe)

            if not game_exe:
                print("No 'VotV.exe' found.")
                return

            for game_path in game_exe:
                self.game_name_list.addItem(game_path)  # Add each path to the list
        except Exception as e:
            print(f"An error occurred in fetch_game_exe: {str(e)}")
    
    def search_for_votv_exe(self, path, game_exe):
        for root, _, files in os.walk(path):
            for file in files:
                if file == 'VotV.exe':
                    game_path = os.path.join(root, file)
                    parent_folder = os.path.basename(os.path.dirname(root))
                    game_exe.append(parent_folder)  # Append the full path to 'VotV.exe' to the list
                    
    def load_selected_description(self):
        selected_item = self.versions_list.currentItem()
        if selected_item:
            self.selected_version = selected_item.text()

            description = self.game_fetch_worker.get_final_descriptions_map().get(self.selected_version, "Description not found")
            self.description_text.setHtml(description)

    def load_selected_game_exe(self):
        self.selected_game_name = self.game_name_list.currentItem().text()
        if self.selected_game_name:
            game_path_to_search = os.path.join(self.game_destination_path, self.selected_game_name)            
               
        def search_for_votv_exe():
            for root, _, files in os.walk(game_path_to_search):
                for file in files:
                    if file == 'VotV.exe':
                        self.game_exe = file 
                        self.game_path = os.path.join(root, file)
        print(self.selected_game_name)

        search_for_votv_exe()  
   
    def is_game_running(self):
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            try:
                process_name = proc.info['name'].lower()
                for name in self.selected_game_names:
                    if name.lower() in process_name:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
        
        
    def launch_game(self):
        try:
            source_backup_folder = os.path.join(self.script_directory, "game backups", self.selected_game_name, "Saved")
            source_save_folder = os.path.join(os.path.expanduser("~"), "AppData", "Local", "VotV", "Saved")

            if not os.path.exists(source_backup_folder):
                os.makedirs(source_backup_folder, exist_ok=True)

            if not os.path.exists(source_save_folder):
                os.makedirs(source_save_folder)
                
            self.move_game_data(source_backup_folder, source_save_folder)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            process = subprocess.Popen(self.game_path, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            game_pid = process.pid
            print(f"Game PID: {game_pid}")

            print("Game has started. Now waiting for it to close...")
            self.hide()

            while True:
                stdout = process.stdout.readline()
                stderr = process.stderr.readline()
                if not stdout and not stderr and process.poll() is not None:
                    break
                if stdout:
                    print(f"Game Output: {stdout.strip()}")
                if stderr:
                    print(f"Game Error: {stderr.strip()}")

            self.perform_backup(source_backup_folder, source_save_folder)
            print("backup done")
            self.show()

        except Exception as e:
            print(f"Error launching the game: {str(e)}")

    def move_game_data(self, source_backup_folder, source_save_folder):
        backup_folder_path = os.path.join(source_backup_folder, self.selected_game_name)

        if not os.path.exists(backup_folder_path):
            print(f"No backup data found for '{self.selected_game_name}'.")
            return

        for item in os.listdir(backup_folder_path):
            source_item = os.path.join(backup_folder_path, item)
            destination_item = os.path.join(source_save_folder, item)

            if os.path.getsize(source_item) == 0:
                print(f"Skipping empty file: {source_item}")
                continue

            shutil.move(source_item, destination_item)

        print(f"Game data for '{self.selected_game_name}' moved to '{source_save_folder}'.")

    def perform_backup(self, source_backup_folder, source_save_folder):
        print("starting backup")
        try:
            print("trying backup")
            if os.path.exists(source_backup_folder):
                os.makedirs(source_backup_folder, exist_ok=True)

            while self.is_game_running():
                time.sleep(1)

            print("Game has closed. Starting backup...")

            for root, _, files in os.walk(source_save_folder):
                for item in files:
                    source_item = os.path.join(root, item)

                    try:
                        if os.path.getsize(source_item) == 0:
                            print(f"Skipping empty file: {source_item}")
                            continue

                        relative_path = os.path.relpath(source_item, source_save_folder)
                        destination_item = os.path.join(source_backup_folder, relative_path)

                        os.makedirs(os.path.dirname(destination_item), exist_ok=True)

                        shutil.copy2(source_item, destination_item)
                    except Exception as e:
                        print(f"Error copying file: {source_item} - {str(e)}")

            print("Backup completed successfully.")

        except Exception as e:
            print(f"Error during backup: {str(e)}")

    def refetch(self):
        if not os.path.exists('cached_data.pk1'):
            # Show a pop-up dialog indicating that data caching is in progress
            wait_dialog = QMessageBox()
            wait_dialog.setWindowTitle("Wait for data caching")
            wait_dialog.setText("Data caching is in progress. Please wait.")
            wait_dialog.exec_()
            return

        download_dialog = QMessageBox()
        download_dialog.setWindowTitle("Are you sure?")
        download_dialog.setText(f'Finds all available downloads of VotV from invotek.net.\n\nThis may take a while.')
        download_dialog.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        download_dialog.setDefaultButton(QMessageBox.Ok)
        result = download_dialog.exec_()

        if result == QMessageBox.Ok:
            self.versions_list.clear()
            self.description_text.clear()
            os.remove('cached_data.pk1')
            fetch_function = partial(self.game_fetch_worker.fetch_game_versions)
            threading.Thread(target=fetch_function).start()
            
    pyqtSlot()
    def game_fetch_worker_fetch_game_exe(self):        
        self.fetch_game_exe(self.game_destination_path)
            

def load_custom_font():
    font_db = QtGui.QFontDatabase()
    font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources/fonts/ShareTechMono-Regular.ttf')

    if os.path.exists(font_path):
        font_id = font_db.addApplicationFont(font_path)
        if font_id != -1:
            font_info = font_db.applicationFontFamilies(font_id)
            if font_info:
                app = QtWidgets.QApplication.instance()
                if app:
                    app.setFont(QtGui.QFont(font_info[0]))

class GameFetchWorker(QtCore.QObject):

    game_fetch_worker_fetch_game_exe = QtCore.pyqtSignal(str)
    game_fetch_worker_load_data = QtCore.pyqtSignal()
    update_fetch_progress = QtCore.pyqtSignal(str)

    def __init__(self):        
        self.config = Config()
        self.version_name_map = {}
        self.versions_list =  CustomListWidget()
        self.version_names = []
        self.version_download_link_map = {}
        self.version_description_map = {}
        self.final_descriptions_map = {}
        self.description_text =  QtWidgets.QTextBrowser()  
        self.html_content = ""                
        last_refresh_time = self.config.get_last_refresh_time()
        initial_button_text = "Refresh Versions List | Last Refreshed: " + last_refresh_time        
        self.reload_data = QtWidgets.QPushButton(initial_button_text) 
        self.game_destination_path = Config.get_game_destination_folder()
        self.html_content_and_style =  """
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                body {
                    background-color: #1C1C1C;
                    color: white;
                    font-size: 15px;
                }
                p {
                    font-size: 18px;
                }
                body h1 {
                    font-size: 20px;
                }
                body h1 {
                    font-size: 20px;
                }
            </style>
            </head>
            <body>
            """
        super().__init__()

    def get_version_name_map(self):
        return self.version_name_map   

    def get_versions_list(self):
        return self.versions_list   

    def get_version_names(self):
        return self.version_names   

    def get_version_download_link_map(self):
        return self.version_download_link_map   

    def get_version_description_map(self):
        return self.version_description_map   

    def get_final_descriptions_map(self):
        return self.final_descriptions_map

    def get_html_content_and_style(self):
        return self.html_content_and_style      

    def get_description_text(self):
        return self.description_text   

    def get_reload_data(self):
        return self.reload_data   

    def fetch_game_versions(self):    
        if not os.path.exists('cached_data.pk1') or not os.access('cached_data.pk1', os.R_OK):
            url = "https://www.invotek.net/releases"
            try:
                response = requests.get(url)
                response.raise_for_status()

                if response.status_code == 200:
                    html = response.text
                    soup = BeautifulSoup(html, 'html.parser')
                    release_containers = soup.find_all('div', class_='release-container')
                    self.process_release_containers(release_containers)
            except requests.exceptions.RequestException as e:
                print(f"Error: {e}")
            self.fetch_descriptions()       
        else:
            self.load_data()

    def process_release_containers(self, release_containers):
        for release_container in release_containers:
            h1_tags = release_container.find_all('h1')
            version_name = " ".join(tag.get_text().strip() for tag in h1_tags).strip()
            self.version_name_map[version_name] = ""
            item = QtWidgets.QListWidgetItem(version_name)
            self.versions_list.addItem(item)
            self.version_names.append(version_name)

            self.current_description = ""
            download_link_div = release_container.find('div', class_='download-link')
            if download_link_div:
                a_child = download_link_div.find('a')
                if a_child:
                    download_link = a_child.get('href')
                    self.version_download_link_map[version_name] = f"https://www.invotek.net{download_link}"

            p_tags = release_container.find_all(['p', 'a'])
            descriptions = [self.process_tag(tag) for tag in p_tags]
            self.current_description = "\n".join(filter(None, descriptions))
            self.version_description_map[version_name] = self.current_description

    def process_tag(self, tag):
        result = ""
        result_2 = "" 

        if tag.name == 'p':
            text = tag.get_text()
            if all(keyword not in text for keyword in ['SHA256:', 'Download', 'Website changelog / Discord changelog', 'changelog']):
                result = text + '\n' 
            if all(keyword not in text for keyword in ['SHA256:', 'Download', 'Website changelog / Discord changelog', '🕛']):
                result_2 = text + '\n'
        elif tag.name == 'a':
            text = tag.get_text()
            if all(keyword not in text for keyword in ['SHA256:', 'Download', '🕛']):
                description_link = tag.get('href')
                if not description_link.startswith("https"):
                    description_link = f"https://www.invotek.net{description_link}"
                result = f"{result_2} {text} {description_link}\n"
        return result
    
    def fetch_descriptions(self):
        for selected_version, description in self.version_description_map.items():
            modified_description = f"<p>{description}</p>\n\n"
            first_link = self.find_first_link(description)
            self.html_content =  self.html_content_and_style
            if first_link:
                if first_link.endswith('.txt'):
                    link_response = requests.get(first_link)
                    if link_response.status_code == 200:
                        text = link_response.text

                        lines = text.split('\n')
                        modified_lines = []

                        for line in lines:
                            if '>' in line:
                                line = line.replace('>', '\n\n>')
                            if ' -' in line:
                                line = line.replace(' -', '\n\n -')
                            modified_lines.append(line)
                        modified_text = '\n'.join(modified_lines)

                        modified_description += modified_text
                else:
                    link_response = requests.get(first_link)
                    if link_response.status_code == 200:
                        link_html = link_response.text
                        link_soup = BeautifulSoup(link_html, 'html.parser')
                        post_body_section = link_soup.find('section', class_='object_text_widget_widget base_widget user_formatted post_body')
                        if post_body_section:
                            self.html_content +=str(post_body_section)
                            modified_description += self.html_content
                        else:
                            body_text = link_soup.body.get_text() if link_soup.body else ""
                            if body_text.strip():
                                modified_description += body_text.strip()
            modified_description = re.sub(r'http[s]?://\S+', '', modified_description)
            modified_description = re.sub(r'Discord changelog|website changelog|to Discord post', '', modified_description, flags=re.IGNORECASE)
            modified_description = re.sub(r'https://discord\.com', '', modified_description)
            self.final_descriptions_map[selected_version] = modified_description      
            current_time = QDateTime.currentDateTime().toString(Qt.DefaultLocaleLongDate)
            self.reload_data.setText("Refresh Versions List | Last Refreshed: " + current_time)

            # Set the last refresh time in the configuration
            Config.set_last_refresh_time(current_time)
        self.save_data()    

        
    def save_data(self):
        if not isinstance(self.version_name_map, dict):
            raise ValueError("self.version_name_map should be a dictionary")

        if not isinstance(self.final_descriptions_map, dict):
            raise ValueError("self.final_descriptions_map should be a dictionary")

        data = {
            'version_name_map': self.version_name_map,
            'final_descriptions_map': self.final_descriptions_map,
            'version_download_link_map': self.version_download_link_map
        }

        # Save data as a pickle file
        with open('cached_data.pk1', 'wb') as pickle_file:
            pickle.dump(data, pickle_file, protocol=pickle.HIGHEST_PROTOCOL, fix_imports=False)

        # Save data as a text file
        with open('cached_data.txt', 'w', encoding='utf-8') as text_file:
            for key, value in data.items():
                text_file.write(f"{key}:\n")
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        text_file.write(f"  {subkey}: {subvalue}\n")
                else:
                    text_file.write(f"  {value}\n")

        # Print a confirmation message
        print("Data saved as cached_data.pk1 and cached_data.txt")


    def load_data(self):        
        self.game_fetch_worker_fetch_game_exe.emit(self.game_destination_path)
        if os.path.exists('cached_data.pk1') and os.access('cached_data.pk1', os.R_OK):
            with open('cached_data.pk1', 'rb') as file:
                try:
                    loaded_data = pickle.load(file, encoding='utf-8')
                    self.version_name_map = loaded_data['version_name_map']
                    self.final_descriptions_map = loaded_data['final_descriptions_map'] 
                    self.version_download_link_map = loaded_data['version_download_link_map']
                    self.versions_list.clear()
                    for version_name, description in self.final_descriptions_map.items():
                        version_name = ''.join(c for c in version_name if ord(c) < 128)
                        description = ''.join(c for c in description if ord(c) < 128)   
                        item = QtWidgets.QListWidgetItem(version_name)
                        self.versions_list.addItem(item)
                except (pickle.UnpicklingError, EOFError, Exception) as e:
                    print(f"Error loading data from 'cached_data.pk1': {e}. Proceeding to fetch from the website.")
        else:
            print("The pickle file 'cached_data.pk1' does not exist or is not readable. Proceeding to fetch from the website.")

    def find_first_link(self, text):
        import re
        urls = re.findall(r'(https?://[^\s]+)', text)
        return urls[0] if urls else None

class TitleBar(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
            
        min_button_icon = QIcon_from_svg('resources/icons/remove.svg', 'white')
        max_button_icon = QIcon_from_svg('resources/icons/fullscreen_black_24dp.svg', 'white')
        close_button_icon = QIcon_from_svg('resources/icons/close-circle.svg', 'white')

        button_size = QtCore.QSize(32, 32) 

        min_button = QPushButton()
        min_button.setIcon(min_button_icon)
        min_button.setFixedSize(button_size)
        min_button.clicked.connect(self.minimize)
        min_button.setStyleSheet('''
            QPushButton {
                border: none;
            }
            QPushButton:hover {
                background-color: gray;
                color: white;
            }
        ''')

        max_button = QPushButton()
        max_button.setIcon(max_button_icon)
        max_button.setFixedSize(button_size)
        max_button.clicked.connect(self.maximize)
        max_button.setStyleSheet('''
            QPushButton {
                border: none;
            }
            QPushButton:hover {
                background-color: gray;
                color: white;
            }
        ''')

        close_button = QPushButton()
        close_button.setIcon(close_button_icon)
        close_button.setFixedSize(button_size) 
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet('''
            QPushButton {
                border: none;
            }
            QPushButton:hover {
                background-color: red;
                color: white;
            }
        ''')
        title_label = QtWidgets.QLabel(self.parent.windowTitle()) 
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet('color: white; font-size: 30px;')

        icon_label = QtWidgets.QLabel()
        script_dir = os.path.dirname(os.path.abspath(__file__))

    
        image_path = os.path.join(script_dir, 'resources/icons/icon.png')

       
        window_icon = QtGui.QPixmap(image_path).scaled(30, 30, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(window_icon)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(min_button)
        layout.addWidget(max_button)
        layout.addWidget(close_button)

        self.setStyleSheet("""
            background-color: 333;
        """)

    def minimize(self):
        self.parent.showMinimized()

    def maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def close(self):
        self.parent.close()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.parent.dragPosition = event.globalPos() - self.parent.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            self.parent.move(event.globalPos() - self.parent.dragPosition)

def QIcon_from_svg(svg_filepath, color='black'):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    absolute_path = os.path.join(script_dir, svg_filepath) 

    img = QPixmap(absolute_path)
    qp = QPainter(img)
    qp.setCompositionMode(QPainter.CompositionMode_SourceIn)
    qp.fillRect(img.rect(), QColor(color))
    qp.end()

    return QIcon(img)

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    load_custom_font()
    download_worker = DownloadWorker()
    game_fetch_worker = GameFetchWorker()
    window = VoidLauncher(download_worker, game_fetch_worker)
    window.show()
    sys.exit(app.exec_())

