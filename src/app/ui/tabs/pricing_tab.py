import logging
import numpy as np

from PySide6.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .product_window import ProductWindow


class PricingTab(QWidget):
    """The tab for displaying product prices."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Create ui
        self._create_widgets()

    def _create_widgets(self):
        self.main_layout = QVBoxLayout(self)

        self._create_top_panel()
        self._create_table()

    def _create_top_panel(self):
        self.top_panel = QWidget(self)
        self.main_layout.addWidget(self.top_panel)

        panel_layout = QVBoxLayout(self.top_panel)
        self.info_pane = QWidget(self.top_panel)
        info_layout = QHBoxLayout(self.info_pane)
        self.scope_label = QLabel("undefined Prices")
        info_layout.addWidget(self.scope_label)
        panel_layout.addWidget(self.info_pane)

        self.filter_pane = QWidget(self.top_panel)
        panel_layout.addWidget(self.filter_pane)

    def _create_table(self):
        headers = [
            "Name",
            "Type",
            "Tag",
            "Tier",
            "Rarity",
            "Pack Size",
            "Pack Price",
            "Unit Price",
        ]
        default_data = {"Filler": {}}
        for key in headers:
            default_data["Filler"][key] = "Loading..."

        self.model = PriceTableModel(self.app, headers, default_data)

        self.proxy_model = PriceFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(7, Qt.DescendingOrder) # pyright: ignore[reportAttributeAccessIssue]
        self.table.doubleClicked.connect(self.on_double_click)

        self.main_layout.addWidget(self.table)

    def on_double_click(self, proxy_index):
        if not hasattr(self.app, "product_rost"):
            logging.warning(
                "Pricing table was double-clicked before roster was initialized. Please wait and try again"
            )
            return

        row = proxy_index.row()
        product_id = self.proxy_model.data(
            self.proxy_model.index(row, 8),
            Qt.ItemDataRole.DisplayRole,
        )

        self.detail_window = ProductWindow(app=self.app, product_id=product_id)
        self.detail_window.show()


class PriceFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        return True


class PriceTableModel(QAbstractTableModel):
    def __init__(self, app, headers, data):
        super().__init__()
        self.app = app
        self._headers = headers
        list_data = []
        for product_id in data:
            entry = data[product_id]
            entry_list = []
            for key in self._headers:
                entry_list.append(entry.get(key, "Loading..."))
            entry_list.append(product_id)
            list_data.append(entry_list)
        self._data = list_data
        self._headers.append("Product ID")

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return self._data[index.row()][index.column()]

    def update_table(self, new_data):
        logging.debug("Updating price table")
        self.layoutAboutToBeChanged.emit()

        if self.app.settings.get("price",{}).get("scope") == "claim":
            getattr(self.app.tabs, "🪙 Prices").scope_label.setText(f"{self.app.settings.get("price",{}).get("claim_name","undefined")} Prices")
        else:
            getattr(self.app.tabs, "🪙 Prices").scope_label.setText("Global Prices")

        list_data = []
        for product_id in new_data:
            entry = new_data[product_id]

            if self.app.market["claim"]["claim_id"]==self.app.settings["price"]["claim_id"] and self.app.settings["price"]["scope"]=="claim":
                # If saved prices claim_id doesn't match search claim_id, revert to global prices
                P_e = self.app.market["claim"].get(product_id,{}).get("price")
            else:
                P_e = self.app.market["global"].get(product_id,{}).get("price")
            if P_e is not None:
                ratio = self.app.product_rost.get(product_id,{}).get("Pack Size",1)
                sig_figs = int(np.floor(np.log10(ratio)) + 1)
                pack_price = float(np.round(ratio * P_e, 1))
                unit_price = float(np.round(P_e, sig_figs))
            else:
                pack_price = "Loading..."
                unit_price = "Loading..."
            entry_list = []
            for key in self._headers:
                if key == "Product ID":
                    entry_list.append(product_id)
                elif key == "Pack Price":
                    entry_list.append(pack_price)
                elif key == "Unit Price":
                    entry_list.append(unit_price)
                else:
                    entry_list.append(entry.get(key, "Loading..."))
            list_data.append(entry_list)
        self._data = list_data
        self.layoutChanged.emit()

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._headers[section]
