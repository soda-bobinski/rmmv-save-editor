import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from editor import SaveFileEditor


def load_styles(app):
    # Load fonts
    font_dir = Path(__file__).parent / "resources" / "fonts"
    QFontDatabase.addApplicationFont(str(font_dir / "Inter-Regular.ttf"))

    # Load styles
    style_path = Path(__file__).parent / "styles" / "style.qss"
    with open(style_path, "r") as f:
        style = f.read()
        # Add basic animation compatibility
        style += """
        QToolButton, QPushButton {
            transition: none; /* Disable CSS transitions */
        }
        """
        app.setStyleSheet(style)

    # Set default font
    app.setFont(QFont("Inter", 10))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    load_styles(app)
    window = SaveFileEditor()
    window.show()
    sys.exit(app.exec())