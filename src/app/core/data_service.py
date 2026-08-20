import asyncio
import json
import logging
import numpy as np
import typing
import websockets
import websockets.typing

from PySide6.QtCore import QThread, Signal, QTimer, QObject

from .data_paths import get_user_data_path
from .models import pricing


class DataService:
    """
    Manages the connection to the game client, handles data subscriptions,
    and passes data to the GUI via a thread-safe queue.

    Refactored to use MessageRouter and focused data processors while
    preserving the exact same interface and subscription patterns.
    """

    def __init__(self, app):
        self.app = app
        app.workers = []

        # "*_desc" tables are relatively static and accessible on the global database
        desc_tables = [
            "cargo",
            "crafting_recipe",
            "item",
            # "item_list",
        ]
        for table in desc_tables:
            self.start_worker(0, f"{table}_desc")
            ...

        # "*_state" tables can be static or not, but importantly, they're region-specific
        state_tables = [
            "buy_order",
            "sell_order",
        ]
        active_regions = [
            # 3,
            # 7,
            # 8,
            # 9,
            # 11,
            # 12,
            # 13,
            14,
            # 15,
            # 17,
            # 18,
            # 19,
            # 23,
        ]
        for table in state_tables:
            for region in active_regions:
                self.start_worker(region, f"{table}_state")
        # There are a *few* state tables accessible from the global server
        self.start_worker(0, f"claim_state")

    def start_worker(self, region, table):
        port = 3000 + region
        host = f"wss://relay.bitcraftsync.app:{port}"
        if region == 0:
            db = "bitcraft-live-global"
        else:
            db = f"bitcraft-live-{region}"
        uri = f"{host}/v1/database/{db}/subscribe?compression=None"

        channel_name = f"R{region}-{table}"
        queries = [f"SELECT * FROM {table}"]

        worker = WebSocketWorker(uri, channel_name, queries)
        # worker.signals.message_received.connect(self.update_ui)
        worker.signals.message_received.connect(self.update_tables)
        worker.start()
        self.app.workers.append(worker)

    def update_tables(self, channel_name, message):
        try:
            message = json.loads(message)
            if "IdentityToken" in message:
                logging.info(f"Performed initial handshake with {channel_name}")
            elif "InitialSubscription" in message:
                logging.info(f"Received initial data from {channel_name}")

                claim_check = False

                # Bulk import the entire response to the local copy of the tables...
                msg_content = message["InitialSubscription"]
                msg_update = msg_content.get("database_update", {})
                msg_tables = msg_update.get("tables", [])
                for entry in msg_tables:
                    table_name = entry.get("table_name")
                    if table_name == "claim_state":
                        claim_check = True
                    inserts = entry.get("updates", [{}])[0].get("inserts", [])
                    if table_name not in self.app.tables:
                        self.app.tables[table_name] = []

                    # Inserts table is still a string at this point, desipte the json.loads(message) at the top of the function
                    for i in range(0, len(inserts)):
                        inserts[i] = json.loads(inserts[i])
                    self.app.tables[table_name] += inserts

                # When the claim check is triggered, send an alphebetized list to the claim_completer
                if claim_check:
                    claim_list = sorted([c["name"] for c in self.app.tables["claim_state"] if "name" in c])
                    current_model = self.app.claim_completer.model()
                    current_model.setStringList(claim_list)
            elif "TransactionUpdate" in message:
                logging.debug(f"Received updated data from {channel_name}")
            else:
                logging.warning(f"Unexpected message from {channel_name}: {message}")
        except:
            logging.error(message)

    def refresh_global_prices(self):
        """Build a global queue and then run through it with delay until empty"""
        logging.info("Beginning global price refresh")
        # Temporary queue method - all items in product roster, in descending order of estimated item value
        self.global_product_queue = sorted(self.app.product_rost,
                                           key = lambda p: self.app.product_rost[p].get("Unit Price",1e-15),
                                           reverse=True)

        # Start the refresh loop
        self.global_refresh_timer = QTimer()
        self.global_refresh_timer.timeout.connect(self.check_global_queue)
        self.global_refresh_timer.start(100)

    def check_global_queue(self):
        product_id = self.global_product_queue[0]
        if not all(
            k in self.app.tables for k in ["buy_order_state", "sell_order_state"]
        ):
            logging.debug(
                f"{product_id} global price check was called before market orders were available"
            )
            return

        # Calculate price and load into table
        orders = pricing.price_calc(app=self.app,product_id=product_id)
        P_e = orders["P_e"]
        ratio = self.app.product_rost.get(product_id, {}).get("Pack Size", 1)
        pack_price = np.round(ratio * P_e, 1)
        self.app.product_rost[product_id]["Pack Price"] = float(pack_price)
        sig_figs = int(np.floor(np.log10(ratio)) + 1)
        unit_price = np.round(P_e, sig_figs)
        self.app.product_rost[product_id]["Unit Price"] = float(unit_price)

        getattr(self.app.tabs,"🪙 Prices").model.update_table()

        # Save new prices
        self.app.market["global"][product_id] = {
            "buy": {
                "price": orders["buy_order_price"].astype(float).tolist(),
                "cum_q": orders["buy_cumsum_q"].astype(float).tolist(),
                "unit_price": orders["buy_unit_p"].astype(float).tolist(),
                "C": float(orders["C_b"]),
                "T": float(orders["T_b"]),
            },
            "sell": {
                "price": orders["sell_order_price"].astype(float).tolist(),
                "cum_q": orders["sell_cumsum_q"].astype(float).tolist(),
                "unit_price": orders["sell_unit_p"].astype(float).tolist(),
                "C": float(orders["C_s"]),
                "T": float(orders["T_s"]),
            },
            "price": float(orders["P_e"]),
        }

        try:
            file_path = get_user_data_path("market.json")

            # Write prices to file
            with open(file_path, "w") as f:
                json.dump(self.app.market, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving to market.json: {e}")

        # Remove all copies of completed product id from queue
        self.global_product_queue = [p for p in self.global_product_queue if p != product_id]

        if len(self.global_product_queue) == 0:
            logging.info("Finished global price refresh")
            self.global_refresh_timer.stop()

    def refresh_claim_prices(self):
        """Build a claim-specific queue and then run through it with delay until empty"""
        logging.info("Beginning claim price refresh")
        self.claim_product_queue = sorted(self.app.product_rost,
                                          key = lambda p: self.app.product_rost[p].get("Unit Price",1e-15),
                                          reverse=True)
        # Start the refresh loop
        self.claim_refresh_timer = QTimer()
        self.claim_refresh_timer.timeout.connect(self.check_claim_queue)
        self.claim_refresh_timer.start(100)

    def check_claim_queue(self):
        claim_id = self.app.settings.get("price",{}).get("claim_id",0)
        claim_dict = self.app.market.get("claim",{})
        if claim_dict.get("claim_id",-1) != claim_id:
            self.app.market["claim"] = {"claim_id": claim_id}

        product_id = self.claim_product_queue[0]
        if not all(
            k in self.app.tables for k in ["buy_order_state", "sell_order_state"]
        ):
            logging.debug(
                f"{product_id} claim price check was called before market orders were available"
            )
            return

        # Calculate price and load into table
        orders = pricing.price_calc(app=self.app,product_id=product_id,claim_id=claim_id)
        P_e = orders["P_e"]
        ratio = self.app.product_rost.get(product_id, {}).get("Pack Size", 1)
        pack_price = np.round(ratio * P_e, 1)
        self.app.product_rost[product_id]["Pack Price"] = float(pack_price)
        sig_figs = int(np.floor(np.log10(ratio)) + 1)
        unit_price = np.round(P_e, sig_figs)
        self.app.product_rost[product_id]["Unit Price"] = float(unit_price)

        getattr(self.app.tabs,"🪙 Prices").model.update_table()

        # Save new prices
        self.app.market["claim"][product_id] = {
            "buy": {
                "price": orders["buy_order_price"].astype(float).tolist(),
                "cum_q": orders["buy_cumsum_q"].astype(float).tolist(),
                "unit_price": orders["buy_unit_p"].astype(float).tolist(),
                "C": float(orders["C_b"]),
                "T": float(orders["T_b"]),
            },
            "sell": {
                "price": orders["sell_order_price"].astype(float).tolist(),
                "cum_q": orders["sell_cumsum_q"].astype(float).tolist(),
                "unit_price": orders["sell_unit_p"].astype(float).tolist(),
                "C": float(orders["C_s"]),
                "T": float(orders["T_s"]),
            },
            "price": float(orders["P_e"]),
        }

        try:
            file_path = get_user_data_path("market.json")

            # Write prices to file
            with open(file_path, "w") as f:
                json.dump(self.app.market, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving to market.json: {e}")

        # Remove all copies of completed product id from queue
        self.claim_product_queue = [p for p in self.claim_product_queue if p != product_id]

        if len(self.claim_product_queue) == 0:
            logging.info("Finished claim price refresh")
            self.global_refresh_timer.stop()

    # def refresh_all_prices(self):
    #     """Build a queue and then run through with delay until empty"""
    #     if not hasattr(self.app, "product_rost"):
    #         logging.debug(
    #             f"Full price refresh was called before product roster was established"
    #         )
    #         return
        
    #     logging.info("Beginning full price refresh")

    #     # Temporary queue method - all items in product roster, in descending order of estimated item value
    #     self.product_queue = sorted(self.app.product_rost,
    #                                 key = lambda p: self.app.product_rost[p].get("Unit Price",1e-15),
    #                                 reverse=True)

    #     # Start the refresh queue
    #     self.refresh_timer = QTimer()
    #     self.refresh_timer.timeout.connect(self.refresh_queue_price)
    #     #self.refresh_timer.timeout.connect(self.refresh_queue_price_test)
    #     self.refresh_timer.start(100)

    # def refresh_queue_price_test(self):
    #     product_id = self.product_queue[0]
    #     if not all(
    #         k in self.app.tables for k in ["buy_order_state", "sell_order_state"]
    #     ):
    #         logging.debug(
    #             f"{product_id} price refresh was called before market orders were available"
    #         )
    #         return
    #     product_id = self.product_queue.pop(0)

    #     g_price = self.refresh_price("global")
    #     c_price = self.refresh_price("claim")
    #     if self.app.settings["price"]["scope"] == "claim":
    #         self.app.product_rost[product_id]["Pack Price"] = float(c_price["pack"])
    #         self.app.product_rost[product_id]["Unit Price"] = float(c_price["unit"])
    #     else:
    #         self.app.product_rost[product_id]["Pack Price"] = float(g_price["pack"])
    #         self.app.product_rost[product_id]["Unit Price"] = float(g_price["unit"])
    #     getattr(self.app.tabs,"🪙 Prices").model.update_table(self.app.product_rost)

    #     try:
    #         file_path = get_user_data_path("market.json")

    #         # Write prices to file
    #         with open(file_path, "w") as f:
    #             json.dump(self.app.market, f, indent=4)
    #     except Exception as e:
    #         logging.error(f"Error saving to market.json: {e}")

    #     if len(self.product_queue) == 0:
    #         logging.info("Finished price refresh")
    #         self.refresh_timer.stop()

    # def refresh_price(self,scope):
    #     product_id = self.product_queue.pop(0)
    #     if not all(
    #         k in self.app.tables for k in ["buy_order_state", "sell_order_state"]
    #     ):
    #         logging.debug(
    #             f"{product_id} price refresh was called before market orders were available"
    #         )
    #         return

    #     # Calculate price and load into table
    #     if scope == "claim":
    #         orders = pricing.price_calc(app=self.app,product_id=product_id)
    #     else:
    #         orders = pricing.price_calc(app=self.app,product_id=product_id)
    #     P_e = orders["P_e"]
    #     ratio = self.app.product_rost.get(product_id, {}).get("Pack Size", 1)
    #     pack_price = np.round(ratio * P_e, 1)
    #     #self.app.product_rost[product_id]["Pack Price"] = float(pack_price)
    #     sig_figs = int(np.floor(np.log10(ratio)) + 1)
    #     unit_price = np.round(P_e, sig_figs)
    #     #self.app.product_rost[product_id]["Unit Price"] = float(unit_price)

    #     #getattr(self.app.tabs,"🪙 Prices").model.update_table(self.app.product_rost)


    #     # Save new prices
    #     self.app.market[scope][product_id] = {
    #         "buy": {
    #             "price": orders["buy_order_price"].astype(float).tolist(),
    #             "cum_q": orders["buy_cumsum_q"].astype(float).tolist(),
    #             "unit_price": orders["buy_unit_p"].astype(float).tolist(),
    #             "C": float(orders["C_b"]),
    #             "T": float(orders["T_b"]),
    #         },
    #         "sell": {
    #             "price": orders["sell_order_price"].astype(float).tolist(),
    #             "cum_q": orders["sell_cumsum_q"].astype(float).tolist(),
    #             "unit_price": orders["sell_unit_p"].astype(float).tolist(),
    #             "C": float(orders["C_s"]),
    #             "T": float(orders["T_s"]),
    #         },
    #         "price": float(orders["P_e"]),
    #     }

    #     price_return = {"pack": pack_price, "unit": unit_price}
    #     return price_return

    # def refresh_queue_price(self):
    #     product_id = self.product_queue.pop(0)
    #     if not all(
    #         k in self.app.tables for k in ["buy_order_state", "sell_order_state"]
    #     ):
    #         logging.debug(
    #             f"{product_id} price refresh was called before market orders were available"
    #         )
    #         return

    #     # Calculate price and load into table
    #     orders = pricing.price_calc(app=self.app,product_id=product_id,claim_id=0)
    #     P_e = orders["P_e"]
    #     ratio = self.app.product_rost.get(product_id, {}).get("Pack Size", 1)
    #     pack_price = np.round(ratio * P_e, 1)
    #     self.app.product_rost[product_id]["Pack Price"] = float(pack_price)
    #     sig_figs = int(np.floor(np.log10(ratio)) + 1)
    #     unit_price = np.round(P_e, sig_figs)
    #     self.app.product_rost[product_id]["Unit Price"] = float(unit_price)

    #     getattr(self.app.tabs,"🪙 Prices").model.update_table()


    #     # Save new prices
    #     self.app.market["global"][product_id] = {
    #         "buy": {
    #             "price": orders["buy_order_price"].astype(float).tolist(),
    #             "cum_q": orders["buy_cumsum_q"].astype(float).tolist(),
    #             "unit_price": orders["buy_unit_p"].astype(float).tolist(),
    #             "C": float(orders["C_b"]),
    #             "T": float(orders["T_b"]),
    #         },
    #         "sell": {
    #             "price": orders["sell_order_price"].astype(float).tolist(),
    #             "cum_q": orders["sell_cumsum_q"].astype(float).tolist(),
    #             "unit_price": orders["sell_unit_p"].astype(float).tolist(),
    #             "C": float(orders["C_s"]),
    #             "T": float(orders["T_s"]),
    #         },
    #         "price": float(orders["P_e"]),
    #     }

    #     try:
    #         file_path = get_user_data_path("market.json")

    #         # Write prices to file
    #         with open(file_path, "w") as f:
    #             json.dump(self.app.market, f, indent=4)
    #     except Exception as e:
    #         logging.error(f"Error saving to market.json: {e}")

    #     if len(self.product_queue) == 0:
    #         logging.info("Finished price refresh")
    #         self.refresh_timer.stop()

class WebSocketSignals(QObject):
    message_received = Signal(str, str)  # (channel_name, message_content)

class WebSocketWorker(QThread):
    def __init__(self, uri, channel_name, queries):
        super().__init__()
        self.uri = uri
        self.channel_name = channel_name
        self.queries = queries
        self.signals = WebSocketSignals()
        self.loop = None
        self.running = False

    def run(self):
        self.running = True
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect_and_subscribe())

    async def connect_and_subscribe(self):
        try:
            proto = typing.cast(websockets.typing.Subprotocol, "v1.json.spacetimedb")
            payload = {
                "Subscribe": {
                    "request_id": 1,
                    "query_strings": self.queries,
                }
            }
            async with websockets.connect(
                uri=self.uri, subprotocols=[proto], max_size=None, open_timeout=None
            ) as websocket:
                await websocket.send(json.dumps(payload))
                while self.running:
                    try:
                        # Wait for message
                        message = await asyncio.wait_for(websocket.recv(), timeout=120)
                        self.signals.message_received.emit(self.channel_name, message)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        logging.warning(f"{self.channel_name} connection closed")
                        break
        except OSError as e:
            logging.error(f"OS Error in subscription {self.channel_name}: {e}")
            if e.winerror == 121:
                logging.info(
                    f"Semaphore timeoute detected on {self.channel_name}, retrying connection"
                )
                await self.connect_and_subscribe()
        except Exception as e:
            logging.error(f"Fault in subscription {self.channel_name}: {e}")
            self.signals.message_received.emit(self.channel_name, f"Error: {str(e)}")

    def stop(self):
        try:
            logging.info(f"Closing {self.channel_name} connection")
        except:
            logging.warning("Closing unnamed connetion")
        self.running = False
        if self.loop:
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            self.loop.stop()
        self.wait()
