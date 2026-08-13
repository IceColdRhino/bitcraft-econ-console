import json
import logging
import os

from PySide6.QtCore import Slot, QUrl, QObject
from PySide6 import QtWebChannel
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from PySide6.QtWidgets import QFrame, QStackedLayout


class MapTab(QFrame):
    """The tab for displaying arbitrage opportunity routes."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.browser = QWebEngineView()
        settings = self.browser.page().settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )

        current_dir = os.path.dirname(os.path.realpath(__file__))
        filename = os.path.join(current_dir, "map.html")
        logging.debug(f"Map html path: {filename}")
        url = QUrl.fromLocalFile(filename)
        self.browser.load(url)
        # self.browser.load(QUrl("https://maps.trinit.is/"))

        layout = QStackedLayout(self)
        layout.addWidget(self.browser)

        # backend = Backend()
        # channel = QtWebChannel.QWebChannel(self)
        # self.browser.page().setWebChannel(channel)
        # channel.registerObject("backend", backend)


class Backend(QObject):
    @Slot(str, result=str)
    def getRef(self, o):
        logging.info("inside getRef", o)
        py_obj = json.loads(o)
        py_obj["c"] = ("Hello", "from", "Python")
        return json.dumps(py_obj)

    @Slot(str)
    def printRef(self, o):
        py_obj = json.loads(o)
        logging.info("inside printRef", py_obj)
