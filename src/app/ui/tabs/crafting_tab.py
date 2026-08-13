from PySide6.QtWidgets import QFrame


class CraftingTab(QFrame):
    """The tab for ..."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
