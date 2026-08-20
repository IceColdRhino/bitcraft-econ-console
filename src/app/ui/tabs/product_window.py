import logging
import numpy as np

import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

# Temporary import
from ...core.models import pricing


class ProductWindow(QWidget):
    """
    Popup for looking up a particular product in the product roster.
    Not necessarily a tab per se, but good enough.
    """

    def __init__(self, app, product_id):
        # product_id = "item_1160079203"
        # product_id = "item_1010001"
        super().__init__()
        self.app = app
        detail = self.app.product_rost[product_id]
        self.setWindowTitle(detail.get("Name", "nameError"))
        self.title = QLabel(detail.get("Name", "nameError"))

        scope = self.app.settings.get("price", {}).get("scope", "global")
        self.orders = self.app.market.get(scope, {}).get(product_id, {})

        self.price = QLabel(
            f"Estimated Market Price: {detail.get('Unit Price', 'priceError')}"
        )

        self.build_charts()

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.title)
        main_layout.addWidget(self.price)
        main_layout.addWidget(self.plot_graph)

    def build_charts(self):
        self.plot_graph = pg.PlotWidget()
        self.plot_graph.setDefaultPadding(0)
        self.plot_graph.setBackground("w")
        self.plot_graph.addLegend()

        # Sell Order Book
        self.plot_graph.plot(
            x=self.orders.get("sell", {}).get("price", []),
            y=self.orders.get("sell", {}).get("cum_q", []),
            stepMode="right",
            fillLevel=0,
            brush=pg.mkBrush(245, 191, 66, 20),
            name="Sell Order Book",
        )
        # Buy Order Book
        self.plot_graph.plot(
            x=self.orders.get("buy", {}).get("price", []),
            y=self.orders.get("buy", {}).get("cum_q", []),
            stepMode="right",
            fillLevel=0,
            brush=pg.mkBrush(16, 132, 222, 20),
            name="Buy Order Book",
        )
        # Sell Unit Prices
        self.plot_graph.plot(
            x=self.orders.get("sell", {}).get("unit_price", []),
            y=self.orders.get("sell", {}).get("cum_q", []),
            pen=None,
            symbol="o",
            symbolBrush=pg.mkBrush(245, 191, 66, 80),
            name="Mean Sell Unit Price",
        )
        # Buy Unit Prices
        self.plot_graph.plot(
            x=self.orders.get("buy", {}).get("unit_price", []),
            y=self.orders.get("buy", {}).get("cum_q", []),
            pen=None,
            symbol="o",
            symbolBrush=pg.mkBrush(16, 132, 222, 20),
            name="Mean Buy Unit Price",
        )
        # # Common price level
        # p = np.linspace(0, self.orders.get("price",0) * 2, 10000)
        # # Supply curve
        # Q_s = self.orders["C_s"] * (1 - (self.orders["T_s"] / p))
        # self.plot_graph.plot(
        #     x=p, y=Q_s, pen=pg.mkPen(245, 191, 66, 100), name="Estimated Supply"
        # )
        # # Demand curve
        # Q_b = -self.orders["C_b"] * (1 - (self.orders["T_b"] / p))
        # self.plot_graph.plot(
        #     x=p, y=Q_b, pen=pg.mkPen(16, 132, 222, 100), name="Estimated Demand"
        # )

        p = np.linspace(
            start=np.min(
                [
                    self.orders.get("buy", {}).get("unit_price", [])
                    + self.orders.get("sell", {}).get("unit_price", [])
                    + [self.orders.get("price", 0)]
                ]
            ),
            stop=np.max(
                [
                    self.orders.get("buy", {}).get("unit_price", [])
                    + self.orders.get("sell", {}).get("unit_price", [])
                    + [self.orders.get("price", 0)]
                ]
            ),
            num=10000,
        )
        # Supply curve
        Q_s = self.orders.get("sell", {}).get("C", 0) * (
            1 - (self.orders.get("sell", {}).get("T", 0) / p)
        )
        self.plot_graph.plot(
            x=p, y=Q_s, pen=pg.mkPen(245, 191, 66, 100), name="Estimated Supply"
        )
        # Demand curve
        Q_b = -self.orders.get("buy", {}).get("C", 0) * (
            1 - (self.orders.get("buy", {}).get("T", 0) / p)
        )
        self.plot_graph.plot(
            x=p, y=Q_b, pen=pg.mkPen(16, 132, 222, 100), name="Estimated Demand"
        )

        # # Equilibrium point in the middle
        self.plot_graph.setXRange(0, self.orders.get("price") * 2)
        self.plot_graph.setYRange(
            0,
            np.max(
                [
                    self.orders.get("buy", {}).get("cum_q", [])
                    + self.orders.get("sell", {}).get("cum_q", [])
                ]
            )
            / 0.9,
        )

        self.plot_graph.setLabel("left", "Cumulative Quantity")
        self.plot_graph.setLabel("bottom", "Price [hc]")
