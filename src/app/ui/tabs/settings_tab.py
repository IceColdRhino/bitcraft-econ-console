import json
import logging
import os
import toml

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.data_paths import get_user_data_path
from app.ui.themes import (
    get_theme_manager,
    get_theme_names,
    get_theme_info,
    get_color,
    register_theme_callback,
)


class SettingsTab(QScrollArea):
    """The tab for adjusting user preferences."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.parent = parent

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setWidgetResizable(True)

        # Get version information
        self.version_info = self._get_version_info()

        # Store UI component references for theme updates
        self.card_frames = []
        self.ui_components = {}

        # Register for theme change notifications
        register_theme_callback(self._on_theme_changed)

        # Apply current theme
        self.setStyleSheet(f"background-color: {get_color('BACKGROUND_PRIMARY')};")

        # Create UI
        self._create_widgets()

    def _create_widgets(self):
        """Create card-based settings interface."""
        self.inner = QWidget()
        self.setWidget(self.inner)
        self.vbox = QVBoxLayout(self.inner)

        # Price Section
        price_content = self._create_card_section(self, "Price Settings")
        self.vbox.addWidget(price_content)
        self._create_price_section(price_content)

        # Crafting Section
        crafting_content = self._create_card_section(self, "Crafting Settings")
        self.vbox.addWidget(crafting_content)

        # Shipping Section
        shipping_content = self._create_card_section(self, "Shipping Settings")
        self.vbox.addWidget(shipping_content)

        # Map Section
        map_content = self._create_card_section(self, "Map Settings")
        self.vbox.addWidget(map_content)

        # Debug Section
        debug_content = self._create_card_section(self, "Debug")
        self.vbox.addWidget(debug_content)
        self._create_debug_section(debug_content)

        # Theme Section
        theme_content = self._create_card_section(self, "Theme")
        self.vbox.addWidget(theme_content)
        self._create_theme_section(theme_content)

        # About Section
        about_content = self._create_card_section(self, "About")
        self.vbox.addWidget(about_content)
        self._create_about_section(about_content)

    def _create_card_section(self, parent, title):
        """Create a card-style container."""
        card_frame = QFrame(
            parent,
            frameShape=QFrame.Shape.Panel,
        )
        card_frame.setStyleSheet(
            f"background-color: {get_color('BACKGROUND_SECONDARY')}; border-color: {get_color('BORDER_DEFAULT')};"
        )

        # Card content
        content_frame = QWidget(card_frame)
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(5, 5, 5, 5)
        card_layout.addWidget(content_frame)

        # Section header inside card
        header_label = QLabel(text=title, parent=content_frame)
        header_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {get_color('TEXT_SECONDARY')}"
        )
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 5, 0, 0)
        content_layout.addWidget(header_label)

        # Store reference for theme updates
        self.card_frames.append(card_frame)

        return card_frame

    def _create_price_section(self, parent):
        """Create the price section."""

        # Scope subsection
        # (Whether estimates use global prices, or a specific claim)
        scope_section = QWidget(parent)
        scope_layout = QHBoxLayout(scope_section)
        scope_label = QLabel(
            parent=scope_section,
            text="Choose scope of price estimates: ")
        scope_label.setStyleSheet(
            f"font-size: 12px; color: {get_color('TEXT_PRIMARY')};"
        )
        scope_layout.addWidget(scope_label)
        button_style = f"""
        QRadioButton {{
            font-size: 12px;
            color: {get_color("TEXT_PRIMARY")};
        }}
        
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 9px;
            border: 2px solid {get_color("BORDER_DEFAULT")};
        }}

        QRadioButton::indicator:checked {{
            background-color: {get_color("BUTTON_ACTIVE")};
            border: 2px solid {get_color("BORDER_FOCUS")};
        }}
        """
        button_group = QButtonGroup(scope_section)
        global_button = QRadioButton("Global")
        global_button.setStyleSheet(button_style)
        claim_button = QRadioButton("Claim-specific")
        claim_button.setStyleSheet(button_style)
        if self.app.settings.get("price",{}).get("scope") == "claim":
            global_button.setChecked(False)
            claim_button.setChecked(True)
        else:
            claim_button.setChecked(False)
            global_button.setChecked(True)
        button_group.addButton(global_button)
        button_group.addButton(claim_button)
        global_button.toggled.connect(self._on_scope_change)
        scope_layout.addWidget(global_button)
        scope_layout.addWidget(claim_button)
        parent.layout().addWidget(scope_section)

        # Claim select subsection
        claim_select_section = QWidget(parent)
        claim_select_layout = QHBoxLayout(claim_select_section)
        self.claim_select_label = QLabel(
            parent=claim_select_section,
            text=f"Selected Claim: {self.app.settings.get('price',{}).get('claim_name','undefined')}"
        )
        self.claim_select_label.setStyleSheet(
            f"font-size: 12px; color: {get_color('TEXT_PRIMARY')};"
        )
        claim_select_layout.addWidget(self.claim_select_label)
        self.claim_input = QLineEdit(
            parent=claim_select_section,
            placeholderText="Claim search..."
        )
        self.claim_input.setStyleSheet(
            f"font-size: 12px; color: {get_color('TEXT_PRIMARY')};"
        )
        self.claim_input.setCompleter(self.app.claim_completer)
        self.claim_input.editingFinished.connect(self._on_claim_search)
        claim_select_layout.addWidget(self.claim_input)
        parent.layout().addWidget(claim_select_section)

    def _on_scope_change(self,global_scope):
        """Detect change in the "global scope" button specifically"""
        if global_scope:
            self.app.settings["price"]["scope"] = "global"
        else:
            self.app.settings["price"]["scope"] = "claim"
        logging.info(f"Price estimates set to {self.app.settings['price']['scope']} scope")
        self._save_settings()
        try:
            getattr(self.app.tabs, "🪙 Prices").model.update_table()
        except:
            logging.warning("Scope settings were changed before product roster was initiliazed")

    def _on_claim_search(self):
        input_text = self.claim_input.text()
        claim = next((c for c in self.app.tables.get("claim_state",[]) if c.get("name") == input_text), None)
        if claim is not None:
            self.app.settings["price"]["claim_id"] = claim["entity_id"]
            self.app.settings["price"]["claim_name"] = claim["name"]
            self._save_settings()
            logging.info(f"Switched claim of interest to: {claim['name']}")
        else:
            logging.warning(f"Unable to find searched claim: {input_text}")
        self.claim_select_label.setText(f"Selected Claim: {self.app.settings.get('price',{}).get('claim_name','undefined')}")
        getattr(self.app.tabs, "🪙 Prices").model.update_table()
        self.claim_input.clear()

    def _create_debug_section(self, parent):
        """Create the debug section."""
        # Logging level
        logging_label = QLabel(
            parent=parent,
            text="Choose your preferred logging verbosity level:",
        )
        logging_label.setStyleSheet(
            f"font-size: 12px; color: {get_color('TEXT_PRIMARY')};"
        )
        parent.layout().addWidget(logging_label)

        # Create the dropdown
        self.logging_dropdown = QComboBox(parent)
        self.logging_dropdown.wheelEvent = lambda event: event.ignore()
        self.logging_dropdown.addItems(
            [
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
            ]
        )
        self.logging_dropdown.setCurrentText(
            self.app.settings.get("debug", {}).get("logging_level", "levelError")
        )
        self.logging_dropdown.setStyleSheet(
            f"font-size: 13 px; color: {get_color('TEXT_PRIMARY')};"
        )
        parent.layout().addWidget(self.logging_dropdown)
        self.logging_dropdown.currentTextChanged.connect(self._on_logging_change)

    def _on_logging_change(self, selected_logging_level):
        try:
            logging.getLogger().setLevel(getattr(logging, selected_logging_level))
            logging.info(f"Logging level changed to {selected_logging_level}")

            self.app.settings["debug"]["logging_level"] = selected_logging_level
            self._save_settings()
        except Exception as e:
            logging.error(f"Error changing logging level: {e}")

    def _create_theme_section(self, parent):
        """Create the theme selection section."""
        # Theme description
        desc_label = QLabel(
            parent=parent,
            text="Choose your preferred color scheme (requires restart):",  # and accessibility options:",
        )
        desc_label.setStyleSheet(
            f"font-size: 12px; color: {get_color('TEXT_PRIMARY')};"
        )
        parent.layout().addWidget(desc_label)

        # Get current theme and available themes
        theme_manager = get_theme_manager()
        current_theme = theme_manager.get_current_theme_name()
        available_themes = get_theme_names()

        # Create readable theme names for display
        theme_display_names = []
        self.theme_name_mapping = {}
        for theme_name in available_themes:
            theme_info = get_theme_info(theme_name)
            display_name = theme_info["name"]
            theme_display_names.append(display_name)
            self.theme_name_mapping[display_name] = theme_name

        # Initialize the dropdown
        current_display_name = get_theme_info(current_theme)["name"]
        self.theme_dropdown = QComboBox(parent)
        self.theme_dropdown.wheelEvent = lambda event: event.ignore()
        self.theme_dropdown.addItems(theme_display_names)
        self.theme_dropdown.setCurrentText(current_display_name)
        self.theme_dropdown.setStyleSheet(
            f"font-size: 13 px; color: {get_color('TEXT_PRIMARY')};"
        )
        parent.layout().addWidget(self.theme_dropdown)

        # Call a method when a new selection is made
        self.theme_dropdown.currentTextChanged.connect(self._on_theme_change)

    def _on_theme_change(self, selected_display_name):
        """Handle theme selection change."""
        try:
            # Get the actual theme name from the display name
            theme_name = self.theme_name_mapping.get(selected_display_name)
            if not theme_name:
                logging.error(f"Invalid theme display name: {selected_display_name}")
                return

            # Apply the theme
            theme_manager = get_theme_manager()
            success = theme_manager.set_theme(theme_name)

            if success:
                logging.debug(f"Theme changed to: {theme_name}")
            else:
                logging.warning(f"Failed to change theme to: {theme_name}")

        except Exception as e:
            logging.error(f"Error changing theme: {e}")

    def _on_theme_changed(self, old_theme: str, new_theme: str):
        """Handle theme change by updating colors."""
        try:
            # TODO: Rebuild from tkinter to pyside
            # # Update window background
            # self.configure(fg_color=get_color("BACKGROUND_PRIMARY"))

            # # Update main scrollable frame background (forces scrollbar refresh)
            # if hasattr(self, "main_frame"):
            #     self.main_frame.configure(fg_color="transparent")

            # # Update close frame background
            # if hasattr(self, "close_frame"):
            #     self.close_frame.configure(fg_color="transparent")

            # # Update all card frames
            # for card_frame in self.card_frames:
            #     card_frame.configure(fg_color=get_color("BACKGROUND_SECONDARY"), border_color=get_color("BORDER_DEFAULT"))

            # # Update all buttons with theme colors
            # self.close_button.configure(fg_color=get_color("STATUS_INFO"), hover_color=get_color("BUTTON_HOVER"))

            # self.logout_button.configure(fg_color=get_color("STATUS_ERROR"), hover_color=get_color("STATUS_ERROR"))

            # self.refresh_button.configure(fg_color=get_color("STATUS_INFO"), hover_color=get_color("BUTTON_HOVER"))

            # self.export_button.configure(fg_color=get_color("STATUS_SUCCESS"), hover_color=get_color("STATUS_SUCCESS"))

            # # Force a visual refresh of the entire window
            # self.update_idletasks()

            logging.debug(
                f"Settings window theme changed from {old_theme} to {new_theme}"
            )

        except Exception as e:
            logging.error(f"Error updating settings window theme: {e}")

    def _create_about_section(self, parent):
        """Create the about section with version and debug info."""
        # Version info
        version_label = QLabel(
            parent=parent,
            text=f"Version: {self.version_info}",
        )
        version_label.setStyleSheet(
            f"font-size: 13px; color: {get_color('TEXT_PRIMARY')};"
        )
        parent.layout().addWidget(version_label)

    def _get_version_info(self):
        """Get version information from pyproject.toml."""
        try:
            # Try to read from pyproject.toml
            project_root = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                )
            )
            toml_path = os.path.join(project_root, "pyproject.toml")

            if os.path.exists(toml_path):
                with open(toml_path, "r", encoding="utf-8") as f:
                    data = toml.load(f)
                    return data.get("project", {}).get("version", "Unknown")
            else:
                return "Development Build"

        except Exception as e:
            logging.error(f"Error reading version info: {e}")
            return "Unknown"

    def _save_settings(self):
        """Save settings to persistent storage."""
        try:
            # # Update settings based on UI state (only if UI components exist)
            # if hasattr(self, "passive_crafts_enabled_var"):
            #     self.app.settings["notifications"]["passive_crafts_enabled"] = (
            #         self.passive_crafts_enabled_var.get()
            #     )
            # if hasattr(self, "active_crafts_enabled_var"):
            #     self.app.settings["notifications"]["active_crafts_enabled"] = (
            #         self.active_crafts_enabled_var.get()
            #     )
            # if hasattr(self, "stamina_recharged_enabled_var"):
            #     self.app.settings["notifications"]["stamina_recharged_enabled"] = (
            #         self.stamina_recharged_enabled_var.get()
            #     )

            # if not (
            #     hasattr(self, "passive_crafts_enabled_var")
            #     or hasattr(self, "active_crafts_enabled_var")
            #     or hasattr(self, "stamina_recharged_enabled_var")
            # ):
            #     logging.warning(
            #         "Settings UI components not yet initialized, skipping UI state update"
            #     )

            # Send updated settings to notification service
            # if (
            #     hasattr(self.app, "data_service")
            #     and self.app.data_service
            #     and hasattr(self.app.data_service, "notification_service")
            # ):
            #     self.app.data_service.notification_service.update_settings(
            #         self.app.settings
            #     )
            #     logging.debug(
            #         f"Settings sent to notification service: {self.app.settings['notifications']}"
            #     )
            # else:
            #     logging.warning(
            #         "Could not access notification service to update settings"
            #     )

            # Save to player_data.json
            try:
                file_path = get_user_data_path("player_data.json")

                # Load existing player data or create new
                player_data = {}
                try:
                    with open(file_path, "r") as f:
                        player_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    pass  # Start with empty dict if file doesn't exist or is corrupted

                # Update settings section
                player_data["settings"] = self.app.settings

                # Write back to file
                with open(file_path, "w") as f:
                    json.dump(player_data, f, indent=4)

                logging.debug("Settings saved to player_data.json")

            except Exception as e:
                logging.error(f"Error saving to player_data.json: {e}")

        except Exception as e:
            logging.error(f"Error saving settings: {e}")

    def _on_setting_change(self):
        """Called when any setting changes."""
        self._save_settings()
        logging.debug("Settings updated")
