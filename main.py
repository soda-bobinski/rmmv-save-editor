import sys
from PySide6.QtWidgets import QApplication
from editor import SaveFileEditor

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SaveFileEditor()
    window.show()
    sys.exit(app.exec())