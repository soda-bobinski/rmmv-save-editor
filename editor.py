import os
import json
import shutil
from pathlib import Path
from lzstring import LZString
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
    QTreeWidgetItem, QPushButton, QFileDialog, QMessageBox, QToolBar,
    QStyle, QLabel, QScrollArea, QApplication, QToolButton
)
from PySide6.QtGui import QClipboard, QKeySequence, QAction
from PySide6.QtCore import (
    Qt, QObject, QByteArray, Signal, QPropertyAnimation,QEasingCurve,
    QEvent, QTimer, QPoint
)
from game_detection import GameDetectionDialog
# from styles.animations import fade_in, slide_down

class Command:
    def __init__(self, path, old_value, new_value):
        self.path = path
        self.old_value = old_value
        self.new_value = new_value

class HoverButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._animate_hover = False

    def event(self, event):
        if event.type() == QEvent.Enter:
            self.parent().animate_hover(self, True)
        elif event.type() == QEvent.Leave:
            self.parent().animate_hover(self, False)
        return super().event(event)

class SafeTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_key = ""
        self.setFlags(self.flags() | Qt.ItemIsEditable)


class SaveFileEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = ""
        self.data = {}
        self.lz = LZString()
        self._loading = False
        self.beautify_names = False
        self.undo_stack = []
        self.redo_stack = []
        self.cached_games = []
        self.init_ui()
        self.setup_animations()

    def setup_animations(self):
        # self.setAttribute(Qt.WA_TranslucentBackground)
        # self.setAttribute(Qt.WA_NoSystemBackground)
        # # Replace all QPushButton instances with HoverButton
        # for btn in self.findChildren(QPushButton):
        #     hover_btn = HoverButton(btn.text(), self)
        #     hover_btn.setIcon(btn.icon())
        #     hover_btn.clicked.connect(btn.clicked)
        #     btn.deleteLater()
        pass

    def animate_hover(self, widget, hover):
        anim = QPropertyAnimation(widget, b"geometry")
        anim.setDuration(150)
        rect = widget.geometry()

        if hover:
            rect.adjust(-2, -2, 2, 2)
            anim.setEasingCurve(QEasingCurve.OutBack)
        else:
            anim.setEasingCurve(QEasingCurve.InBack)

        anim.setEndValue(rect)
        anim.start()

    def init_ui(self):
        self.setWindowTitle("RPG Maker MV Save Editor")
        self.setGeometry(100, 100, 800, 600)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        self.init_toolbar()

        # File controls
        file_layout = QHBoxLayout()
        self.open_btn = QPushButton("Open Save File")
        self.open_btn.clicked.connect(self.open_file)
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_file)
        self.save_btn.setEnabled(False)

        file_layout.addWidget(self.open_btn)
        file_layout.addWidget(self.save_btn)

        # Tree display
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Property", "Value"])
        self.tree.setColumnWidth(0, 250)
        self.tree.itemChanged.connect(self.handle_item_change)

        # Layout organization
        layout.addLayout(file_layout)
        layout.addWidget(QLabel("Save File Contents:"))
        layout.addWidget(self.tree)

        # Style
        self.setStyleSheet("""
            QTreeWidget::item { padding: 3px; }
            QToolButton { padding: 5px; border-radius: 3px; }
            QToolButton:checked { background-color: #e0f0ff; }
        """)

    def init_toolbar(self):
        toolbar = QToolBar("Tools")
        self.toolbar = toolbar
        self.addToolBar(toolbar)

        # Beautify Action
        beautify_icon = self.style().standardIcon(QStyle.SP_FileDialogContentsView)
        self.beautify_action = QAction(beautify_icon, "Beautify Names", self)
        self.beautify_action.setCheckable(True)
        self.beautify_action.toggled.connect(self.toggle_beautifier)
        toolbar.addAction(self.beautify_action)

        # Game Detection
        detect_icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        detect_action = QAction(detect_icon, "Detect Games", self)
        detect_action.triggered.connect(self.show_game_detection)
        toolbar.addAction(detect_action)

        # Undo/Redo Actions
        undo_icon = self.style().standardIcon(QStyle.SP_ArrowBack)
        self.undo_action = QAction(undo_icon, "Undo", self)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.setEnabled(False)

        redo_icon = self.style().standardIcon(QStyle.SP_ArrowForward)
        self.redo_action = QAction(redo_icon, "Redo", self)
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.setEnabled(False)

        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)

    def toggle_beautifier(self, state):
        self.beautify_names = state
        if self.data:
            expanded = self.save_expansion_states()
            self.tree.blockSignals(True)
            try:
                self.populate_tree()
                self.restore_expansion_states(expanded)
            finally:
                self.tree.blockSignals(False)

    def show_game_detection(self):
        self.game_detection_dialog = GameDetectionDialog(self)
        self.game_detection_dialog.list_widget.itemClicked.connect(self.handle_game_selection)
        self.game_detection_dialog.show()
        # self.dialog = self.game_detection_dialog
        #
        # self.dialog.move(self.dialog.pos() + QPoint(0, 100))
        # anim = QPropertyAnimation(self.dialog, b"pos")
        # anim.setDuration(300)
        # anim.setStartValue(self.dialog.pos() - QPoint(0, 100))
        # anim.setEndValue(self.dialog.pos())
        # anim.start()

    def handle_game_selection(self, item):
        try:
            # Get the selected game path
            game_path = next(
                p for p in self.game_detection_dialog.game_paths
                if p.name == item.text()
            )

            # Determine save directory path
            save_dir = game_path / "www/save"

            # Create directory if needed
            if not save_dir.exists():
                save_dir.mkdir(parents=True)

            # Open file dialog
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Open Save File",
                str(save_dir),
                "RPG Maker Save Files (*.rpgsave)"
            )

            if filename:
                self.current_file = filename
                self.load_file()

        except Exception as e:
            self.show_error("Selection Error", str(e))

    def save_expansion_states(self):
        expanded = set()

        def walk(item, path):
            for i in range(item.childCount()):
                child = item.child(i)
                child_path = path + [child.original_key]
                if child.isExpanded():
                    expanded.add('/'.join(child_path))
                walk(child, child_path)

        walk(self.tree.invisibleRootItem(), [])
        return expanded

    def restore_expansion_states(self, expanded):
        def walk(item, path):
            for i in range(item.childCount()):
                child = item.child(i)
                child_path = path + [child.original_key]
                if '/'.join(child_path) in expanded:
                    child.setExpanded(True)
                walk(child, child_path)

        walk(self.tree.invisibleRootItem(), [])

    def beautify_key(self, key):
        clean_key = key.lstrip('_0123456789')
        spaced_key = ''.join([' ' + c if c.isupper() else c for c in clean_key]).strip()
        words = spaced_key.split(' ')
        final_words = []
        for word in words:
            if word.lower() in ['id', 'hp', 'mp', 'xp']:
                final_words.append(word.upper())
            else:
                final_words.append(word.capitalize())
        return ' '.join(final_words)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Save File", "", "RPG Maker Save Files (*.rpgsave)"
        )
        if file_path:
            self.current_file = file_path
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_undo_redo_buttons()
            self.load_file()

    def show_error(self, title, message, details=""):
        print(f"\n=== ERROR ===")
        print(f"Title: {title}")
        print(f"Message: {message}")
        print(f"Details:\n{details}")
        print("=============\n")

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(message)
        copy_btn = QPushButton("Copy Error", msg_box)
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(
            f"{title}\n{message}\n\nDetails:\n{details}"
        ))
        msg_box.addButton(copy_btn, QMessageBox.ActionRole)
        msg_box.addButton(QMessageBox.Ok)
        msg_box.exec()

    def copy_to_clipboard(self, text):
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "Error details copied to clipboard!")

    def load_file(self):
        if self._loading:
            return

        self._loading = True
        try:
            self.open_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            QApplication.processEvents()

            with open(self.current_file, "r", encoding="utf-8") as f:
                compressed_data = f.read()

            decompressed = self.lz.decompressFromBase64(compressed_data)
            if not decompressed:
                raise ValueError("Invalid decompression result")

            self.data = json.loads(decompressed)
            self.tree.blockSignals(True)
            try:
                self.populate_tree()
            finally:
                self.tree.blockSignals(False)

            self.save_btn.setEnabled(True)

        except Exception as e:
            error_details = f"File: {self.current_file}\nError: {str(e)}"
            self.show_error("Error Loading File", "Failed to load file", error_details)
        finally:
            self._loading = False
            self.open_btn.setEnabled(True)

    def populate_tree(self, data=None, parent=None):
        try:
            self.tree.clear()
            data = data or self.data
            root = self.tree.invisibleRootItem()

            if isinstance(data, dict):
                self._populate_dict(data, root)
            elif isinstance(data, list):
                self._populate_list(data, root)

        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                print("Handled deleted object reference")
            else:
                raise

    def _populate_dict(self, data, parent):
        for key, value in data.items():
            item = SafeTreeWidgetItem(parent)
            item.original_key = key
            display_key = self.beautify_key(key) if self.beautify_names else key
            item.setText(0, display_key)
            self._process_value(value, item)

    def _populate_list(self, data, parent):
        for index, value in enumerate(data):
            item = SafeTreeWidgetItem(parent)
            item.original_key = str(index)
            display_index = str(index)
            item.setText(0, display_index)
            self._process_value(value, item)

    def _process_value(self, value, item):
        item.takeChildren()
        if isinstance(value, (dict, list)):
            item.setText(1, f"[{type(value).__name__.capitalize()}]")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if isinstance(value, dict):
                self._populate_dict(value, item)
            else:
                self._populate_list(value, item)
        else:
            item.setText(1, str(value))
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.takeChildren()

    def handle_item_change(self, item, column):
        if not self._loading and column == 1:
            try:
                if item.parent() or self.tree.indexOfTopLevelItem(item) >= 0:
                    self.update_data_structure(item)
            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    print("Ignoring change to deleted item")
                else:
                    raise

    def update_data_structure(self, item):
        current_item = item
        path = []
        original_text = item.text(1)

        try:
            # Build path using original keys
            while current_item and current_item != self.tree.invisibleRootItem():
                if isinstance(current_item, SafeTreeWidgetItem):
                    path.insert(0, current_item.original_key)
                else:
                    path.insert(0, current_item.text(0))
                current_item = current_item.parent()

            # Navigate through data structure
            current_data = self.data
            for i, step in enumerate(path):
                if isinstance(current_data, dict):
                    if step not in current_data:
                        available = list(current_data.keys())
                        raise KeyError(
                            f"Key '{step}' not found at position {i}.\n"
                            f"Available keys: {available}"
                        )
                    current_data = current_data[step]
                elif isinstance(current_data, list):
                    try:
                        idx = int(step)
                    except ValueError:
                        raise TypeError(f"Invalid list index '{step}' at position {i}")
                    if idx >= len(current_data) or idx < 0:
                        raise IndexError(
                            f"Index {idx} out of range (0-{len(current_data) - 1}) at position {i}"
                        )
                    current_data = current_data[idx]
                else:
                    raise TypeError(
                        f"Unexpected {type(current_data).__name__} at position {i}"
                    )

            # Value conversion and update
            old_value = current_data
            new_value = self.convert_value(item.text(1))

            if old_value != new_value:
                self.undo_stack.append(Command(path.copy(), old_value, new_value))
                self.redo_stack.clear()
                self.update_undo_redo_buttons()

                target = self.data
                for step in path[:-1]:
                    target = target[step]
                target[path[-1]] = new_value

                self.reload_tree()

        except Exception as e:
            self.tree.blockSignals(True)
            item.setText(1, str(original_text))
            self.tree.blockSignals(False)

            error_details = (
                f"Path: {' → '.join(path)}\n"
                f"Error: {str(e)}\n"
                f"Data Type at Failure: {type(current_data).__name__}\n"
                f"Full Data: {json.dumps(self.data, indent=2)}"
            )
            self.show_error("Update Failed", "Could not update value", error_details)
            print(f"Critical Update Error:\n{error_details}")

    def reload_tree(self):
        if self.data:
            expanded = self.save_expansion_states()
            self.tree.blockSignals(True)
            self.populate_tree()
            self.restore_expansion_states(expanded)
            self.tree.blockSignals(False)

    def convert_value(self, value):
        lower_val = value.lower()
        if lower_val == "true":
            return True
        if lower_val == "false":
            return False
        if lower_val in ["null", "none"]:
            return None
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    def save_file(self):
        if not self.current_file:
            return

        backup_path = self.current_file + ".bak"
        try:
            shutil.copyfile(self.current_file, backup_path)
            json_data = json.dumps(self.data, separators=(',', ':'), ensure_ascii=False)
            compressed_data = self.lz.compressToBase64(json_data)
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(compressed_data)
            QMessageBox.information(self, "Success", "Save file updated successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")

    def update_undo_redo_buttons(self):
        self.undo_action.setEnabled(len(self.undo_stack) > 0)
        self.redo_action.setEnabled(len(self.redo_stack) > 0)

    def undo(self):
        if not self.undo_stack:
            return
        cmd = self.undo_stack.pop()
        self.apply_command(cmd, undo=True)
        self.redo_stack.append(cmd)
        self.update_undo_redo_buttons()

    def redo(self):
        if not self.redo_stack:
            return
        cmd = self.redo_stack.pop()
        self.apply_command(cmd, undo=False)
        self.undo_stack.append(cmd)
        self.update_undo_redo_buttons()

    def apply_command(self, cmd, undo):
        value = cmd.old_value if undo else cmd.new_value
        path = cmd.path

        try:
            self.tree.blockSignals(True)

            if path:
                current = self.data
                for step in path[:-1]:
                    current = current[step]
                current[path[-1]] = value
            else:
                self.data = value

            self.reload_tree()

        except Exception as e:
            self.show_error("Undo/Redo Error", str(e))
        finally:
            self.tree.blockSignals(False)

    def closeEvent(self, event):
        if self.undo_stack:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Are you sure you want to quit?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
        event.accept()