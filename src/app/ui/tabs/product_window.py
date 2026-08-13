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

        # This isn't where I want to ultimately calculate things, I don't think...
        # orders = self.app.price_calc(product_id,0)
        orders = pricing.price_calc(app=self.app, product_id=product_id, claim_id=0)
        self.orders = orders

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
        self.plot_graph.setBackground("w")
        self.plot_graph.addLegend()

        # Sell Order Book
        self.plot_graph.plot(
            x=self.orders["sell_order_price"],
            y=self.orders["sell_cumsum_q"],
            stepMode="right",
            fillLevel=0,
            brush=pg.mkBrush(245, 191, 66, 20),
            name="Sell Order Book",
        )
        # Buy Order Book
        self.plot_graph.plot(
            x=self.orders["buy_order_price"],
            y=self.orders["buy_cumsum_q"],
            stepMode="right",
            fillLevel=0,
            brush=pg.mkBrush(16, 132, 222, 20),
            name="Buy Order Book",
        )
        # Sell Unit Prices
        self.plot_graph.plot(
            x=self.orders["sell_unit_p"],
            y=self.orders["sell_cumsum_q"],
            pen=None,
            symbol="o",
            symbolBrush=pg.mkBrush(245, 191, 66, 80),
            name="Mean Sell Unit Price",
        )
        # Buy Unit Prices
        self.plot_graph.plot(
            x=self.orders["buy_unit_p"],
            y=self.orders["buy_cumsum_q"],
            pen=None,
            symbol="o",
            symbolBrush=pg.mkBrush(16, 132, 222, 20),
            name="Mean Buy Unit Price",
        )
        # Common price level
        p = np.linspace(0, self.orders["P_e"] * 2, 10000)
        # Supply curve
        Q_s = self.orders["C_s"] * (1 - (self.orders["T_s"] / p))
        self.plot_graph.plot(
            x=p, y=Q_s, pen=pg.mkPen(245, 191, 66, 100), name="Estimated Supply"
        )
        # Demand curve
        Q_b = -self.orders["C_b"] * (1 - (self.orders["T_b"] / p))
        self.plot_graph.plot(
            x=p, y=Q_b, pen=pg.mkPen(16, 132, 222, 100), name="Estimated Demand"
        )

        # Equilibrium point in the middle
        self.plot_graph.setXRange(0, self.orders["P_e"] * 2, padding=0)
        C_lim = max([self.orders["C_b"], self.orders["C_s"]])
        self.plot_graph.setYRange(0, C_lim, padding=0)

        self.plot_graph.setLabel("left", "Cumulative Quantity")
        self.plot_graph.setLabel("bottom", "Price [hc]")
