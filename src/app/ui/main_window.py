import json
import logging
import numpy as np
import pandas as pd
import sys

np.seterr(divide="ignore", invalid="ignore")

from PySide6.QtCore import QSize, QStringListModel, Qt, QTimer
from PySide6.QtWidgets import QCompleter, QMainWindow, QTabWidget

from app.core.data_paths import get_user_data_path
from app.core.data_service import DataService
from app.ui.tabs.pricing_tab import PricingTab
from app.ui.tabs.crafting_tab import CraftingTab
from app.ui.tabs.shipping_tab import ShippingTab
from app.ui.tabs.map_tab import MapTab
from app.ui.tabs.settings_tab import SettingsTab
from app.ui.themes import get_color


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        logging.info("Initializing main application window")

        # self.app = MainApplication()
        self._load_settings()
        self._load_old_market()
        self.tables = {}

        # Display information
        try:
            # Get screen resolution
            screen = self.screen()
            screen_width, screen_height = screen.size().toTuple()
            dpi = screen.physicalDotsPerInch()
            logging.debug(f"Display: {screen_width}x{screen_height} @ {dpi:.0f} DPI")
        except Exception as e:
            logging.debug(f"Display info error: {e}")

        self.setWindowTitle("BitCraft Econ Console")
        self.resize(QSize(900, 600))
        logging.debug("Main window geometry set to 900x600")

        # Shutdown tracking
        self.is_shutting_down = False
        self.shutdown_dialog = None

        # Building the GUI
        claim_model = QStringListModel([])
        self.claim_completer = QCompleter()
        self.claim_completer.setModel(claim_model)
        self.tabs = TabWidget(app=self)
        self.setCentralWidget(self.tabs)

        # Starting data-handling
        self.data_service = DataService(app=self)

        delay_time_ms = 60000
        logging.info(
            f"Waiting {int(delay_time_ms / 1000)} s to perform full price refresh"
        )
        #QTimer.singleShot(delay_time_ms, self.data_service.refresh_all_prices)

    def _load_settings(self):
        """Load settings, with fallback default values"""
        default_settings = {
            "price": {
                "scope": "global",
                "claim_id": -1,
                "claim_name": "undefined",
            },
            "debug": {
                "logging_level": "DEBUG",
            },
            "theme": {"current_theme": "dark"},
        }

        try:
            file_path = get_user_data_path("player_data.json")
            with open(file_path, "r") as f:
                player_data = json.load(f)

            # Extract settings from player_data, merge with defaults
            saved_settings = player_data.get("settings", {})
            if saved_settings:
                # Deep merge: update defaults with saved settings
                for category, options in saved_settings.items():
                    if category in default_settings and isinstance(options, dict):
                        default_settings[category].update(options)
                    else:
                        default_settings[category] = options
            logging.debug("Settings loaded from player_data.json")

        except FileNotFoundError:
            logging.info("No player_data.json found, using default settings")
        except json.JSONDecodeError:
            logging.warning("player_data.json is malformed, using default settings")
        except Exception as e:
            logging.error(f"Error reading player_data.json: {e}, using defaults")
        self.settings = default_settings

    def _load_old_market(self):
        default_market = {
            "global": {},
            "claim": {"claim_id": -1},
        }
        try:
            file_path = get_user_data_path("market.json")
            with open(file_path, "r") as f:
                saved_market = json.load(f)

            # Deep merge: update defaults with saved market
            for scope, details in saved_market.items():
                if scope in default_market and isinstance(scope, str):
                    default_market[scope].update(details)
                else:
                    default_market[scope] = details

            logging.debug("Loaded market from previous session")
        except FileNotFoundError:
            logging.info("No market.json found, calculating market from scratch")
        except json.JSONDecodeError:
            logging.warning("market.json is malformed, calculating market from scratch")
        except Exception as e:
            logging.error(f"Error reading market.json: {e}, calculating market from scratch")
        self.market = default_market

    def initialize_roster(self):
        logging.info("Initializing product roster")
        self.product_rost = {}
        # Roster keys are "human readable"/display-table-ready
        rarity_lookup = {
            0: "Default",
            1: "Common",
            2: "Uncommon",
            3: "Rare",
            4: "Epic",
            5: "Legendary",
            6: "Mythic",
        }

        self.pack_lookup = {}

        for entry in self.tables["item_desc"]:
            # Item lists get omitted from the roster
            if entry.get("item_list_id") != 0:
                continue

            entry_dict = {
                "Name": entry.get("name", "nameError"),
                "Type": "Item",
                "Tag": entry.get("tag", "tagError"),
                "Tier": entry.get("tier", "tierError"),
                "Rarity": rarity_lookup.get(
                    entry.get("rarity", -1)[0], "rarityError"
                ),  # Hopefully the "enum" format stays the same...
                "Pack Size": 1,
                "Description": entry.get("description", "descriptionError"),
                "Volume": entry.get("volume", "volumeError"),
            }
            self.product_rost[f"item_{entry.get('id', 'idError')}"] = entry_dict

        for entry in self.tables["cargo_desc"]:
            product_id = f"cargo_{entry.get('id', 'idError')}"
            # Packages get saved in reference to their base item instead
            if entry.get("tag", "tagError") == "Package":
                for craft in self.tables["crafting_recipe_desc"]:
                    crafted_stack = craft.get("crafted_item_stacks", [])
                    consumed_stack = craft.get("consumed_item_stacks", [])
                    # Packing involves exactly 1 inptu and output
                    if len(crafted_stack) != 1 or len(consumed_stack) != 1:
                        continue
                    # I'm looking for the craft recipe that yields the pack
                    if crafted_stack[0][2] != [1, []] or consumed_stack[0][2] != [
                        0,
                        [],
                    ]:  # That list encodes item/cargo type
                        continue
                    if crafted_stack[0][0] != entry.get("id"):
                        continue

                    ratio = consumed_stack[0][1]
                    item_id = f"item_{consumed_stack[0][0]}"
                    self.pack_lookup[product_id] = {
                        "pair": item_id,
                        "ratio": ratio,
                    }
                    self.pack_lookup[item_id] = {
                        "pair": product_id,
                        "ratio": ratio,
                    }

                    self.product_rost[item_id]["Pack Size"] = ratio
                continue

            entry_dict = {
                "Name": entry.get("name", "nameError"),
                "Type": "Cargo",
                "Tag": entry.get("tag", "tagError"),
                "Tier": entry.get("tier", "tierError"),
                "Rarity": rarity_lookup.get(
                    entry.get("rarity", -1)[0], "rarityError"
                ),  # Hopefully the "enum" format stays the same...
                "Pack Size": 1,
                "Description": entry.get("description", "descriptionError"),
                "Volume": entry.get("volume", 6000),
            }
            self.product_rost[product_id] = entry_dict

        # This is fucking gross...
        getattr(self.tabs, "🪙 Prices").model.update_table(self.product_rost)

    def closeEvent(self, event):
        # Clean up threads gracefully on app exit
        if self.is_shutting_down:
            return  # Already shutting down

        logging.info("[MainWindow] Closing application...")
        self.is_shutting_down = True

        # for worker in self.app.workers:
        #    worker.stop()

        event.accept()


class TabWidget(QTabWidget):
    """Setting up and formatting the tabs widget."""

    def __init__(self, app):
        super(TabWidget, self).__init__()
        self.app = app
        self._create_tabs()

        style = f"""
        QTabBar::tab {{
            background: {get_color("BACKGROUND_SECONDARY")};
            color: {get_color("TEXT_PRIMARY")};
            border: 1px solid {get_color("BORDER_DEFAULT")};
            font-size: 12pt;
            padding: 6px 12px;
            }}
            
        QTabBar::tab:selected{{
            background: {get_color("BACKGROUND_TERTIARY")};
            color: {get_color("TEXT_SECONDARY")};
            border: 1px solid {get_color("BORDER_FOCUS")};
            font-size: 12pt;
            padding: 6px 12px;
            }}"""
        self.tabBar().setStyleSheet(style)

    def _create_tabs(self):
        """Create all tab instances."""
        tab_classes = {
            "🪙 Prices": PricingTab,
            "⚒️ Crafting": CraftingTab,
            "⛵ Shipping": ShippingTab,
            "🗺️ Map": MapTab,
            "⚙️ Settings": SettingsTab,
        }
        for name, TabClass in tab_classes.items():
            setattr(self, name, TabClass(self, self.app))
            self.addTab(getattr(self, name), name)
            logging.info(f"Created tab: {name}")

    def resizeEvent(self, event):
        """Make tabs span full width of the window"""
        self.tabBar().setFixedWidth(self.width())
        super(TabWidget, self).resizeEvent(event)
