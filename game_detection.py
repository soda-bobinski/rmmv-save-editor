import os
import time
import winreg
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QLabel, QPushButton, QMessageBox
)
# from styles.animations import fade_in, slide_down

def is_rpg_mv_game(path):
    www_path = path / "www"
    game_root = path.parent if path.name.lower() == "www" else path

    classic_conditions = [
        (www_path / "index.html").exists(),
        (www_path / "js/rpg_core.js").exists(),
        (www_path / "js/rpg_managers.js").exists(),
        (game_root / "Game.exe").exists()
    ]

    web_conditions = [
        (path / "index.html").exists(),
        (path / "js/rpg_core.js").exists(),
        (path / "js/rpg_managers.js").exists(),
        (path / "js/plugins.js").exists()
    ]

    if all(classic_conditions):
        return game_root
    elif all(web_conditions):
        return path
    return None

class GameScanner(QThread):
    update_progress = Signal(str)
    game_found = Signal(Path)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, search_paths):
        super().__init__()
        self.search_paths = search_paths
        self._pause = False
        self._is_running = True

    def pause(self):
        self._pause = True

    def resume(self):
        self._pause = False

    def run(self):
        try:
            checked_paths = set()
            for base_path in self.search_paths:
                if self._pause:
                    while self._pause:
                        time.sleep(0.1)

                self.update_progress.emit(f"Scanning {base_path}...")

                try:
                    for pattern in ["*", "*/*"]:
                        for path in base_path.glob(pattern):
                            if not self._is_running:
                                return

                            if path.is_dir() and path not in checked_paths:
                                checked_paths.add(path)
                                if is_rpg_mv_game(path):
                                    self.game_found.emit(path)
                except Exception as e:
                    self.error_occurred.emit(f"Skipped {base_path}: {str(e)}")

            self.finished.emit()
        except Exception as e:
            self.error_occurred.emit(f"Scan failed: {str(e)}")

    def stop(self):
        self._is_running = False

class GameDetectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_editor = parent
        self.game_paths = []
        self.scanner = None
        self.init_ui()
        self.init_with_cache()
        # self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_TranslucentBackground)

    def init_with_cache(self):
        if self.parent_editor.cached_games:
            self.game_paths = self.parent_editor.cached_games.copy()
            for path in self.game_paths:
                self.list_widget.addItem(path.name)
            self.progress_label.setText(f"Loaded {len(self.game_paths)} cached games")
        else:
            self.start_scan()

    def init_ui(self):
        self.setWindowTitle("Detected RPG Maker MV Games")
        self.setMinimumSize(400, 300)
        self.layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.progress_label = QLabel("Ready to scan")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.refresh_btn = QPushButton("Start Scan")
        self.refresh_btn.clicked.connect(self.start_scan)
        self.layout.addWidget(self.progress_label)
        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.refresh_btn)
        self.setLayout(self.layout)

    def start_scan(self):
        self.list_widget.clear()
        self.game_paths = []
        search_paths = self.get_search_paths()
        self.scanner = GameScanner(search_paths)
        self.scanner.game_found.connect(self.add_game)
        self.scanner.finished.connect(self.on_scan_complete)
        self.scanner.error_occurred.connect(self.show_scan_error)
        self.scanner.update_progress.connect(self.update_progress_text)
        self.refresh_btn.setEnabled(False)
        self.progress_label.setText("Scanning...")
        self.scanner.start()

    def add_game(self, path):
        game_root = path.parent if path.name.lower() == "www" else path
        if game_root not in self.game_paths:
            self.game_paths.append(game_root)
            self.list_widget.addItem(game_root.name)
        if self.parent_editor:
            self.parent_editor.cached_games = self.game_paths.copy()

    def update_progress_text(self, text):
        self.progress_label.setText(text)

    def show_scan_error(self, error):
        self.list_widget.addItem(f"Error: {error}")

    def on_scan_complete(self):
        if self.parent_editor:
            self.parent_editor.cached_games = self.game_paths.copy()
        self.refresh_btn.setEnabled(True)
        self.progress_label.setText("Scan complete")
        if not self.game_paths:
            self.list_widget.addItem("No games found")

    def get_windows_drives(self):
        import ctypes
        drives = []
        for drive in range(65, 91):
            drive_name = ctypes.c_wchar_p(chr(drive) + ":\\")
            if ctypes.windll.kernel32.GetDriveTypeW(drive_name) == 3:
                drives.append(Path(drive_name.value))
        return drives

    def get_steam_library_paths(self):
        steam_paths = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as key:
                steam_install = Path(winreg.QueryValueEx(key, "InstallPath")[0])

            main_steamapps = steam_install / "steamapps/common"
            if main_steamapps.exists():
                steam_paths.append(main_steamapps)

            library_file = steam_install / "steamapps/libraryfolders.vdf"
            if library_file.exists():
                with open(library_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if '"path"' in line:
                            path = Path(line.split('"')[3].replace("\\\\", "/"))
                            steamapps = path / "steamapps/common"
                            if steamapps.exists():
                                steam_paths.append(steamapps)

            proton_paths = [
                steam_install / "steamapps/compatdata",
                steam_install / "steamapps/shadercache"
            ]
            for p in proton_paths:
                if p.exists():
                    steam_paths.append(p)

        except Exception as e:
            print(f"Steam detection error: {str(e)}")

        return steam_paths

    def get_search_paths(self):
        search_paths = [
            Path.home() / "Games",
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
            Path.home() / "Desktop",
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "AppData/Local"
        ]
        steam_paths = self.get_steam_library_paths()
        search_paths.extend(steam_paths)
        search_paths.extend(self.get_windows_drives())
        return search_paths

    def closeEvent(self, event):
        if self.scanner and self.scanner.isRunning():
            self.scanner.stop()
            self.scanner.wait(2000)
        event.accept()

    def showEvent(self, event):
        # fade_in(self, 250)
        # slide_down(self, 350)
        super().showEvent(event)

    def hideEvent(self, event):
        self.deleteLater()  # Force cleanup
        super().hideEvent(event)