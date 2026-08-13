import json
import logging
import os
import platform
import sys

from PySide6.QtWidgets import QApplication

from app.core.data_paths import get_user_data_path
from app.ui.main_window import MainWindow

# Clear any existing logging configuration and set up fresh
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Try to pre-load logging settings
try:
    file_path = get_user_data_path("player_data.json")
    with open(file_path, "r") as f:
        player_data = json.load(f)
    logging_level = (
        player_data.get("settings", {}).get("debug", {}).get("logging_level", "DEBUG")
    )
    allowed_levels = [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]
    if logging_level not in allowed_levels:
        raise ValueError
except:
    logging_level = "DEBUG"

# Configure logging to both console and file
logging.basicConfig(
    level=getattr(logging, logging_level),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bc-econ-console.log", mode="w", encoding="utf-8"),
    ],
    force=True,  # Force reconfiguration if logging was already configured
)


def log_system_environment():
    """Log comprehensive system environment information for debugging."""
    try:
        logging.info("=== BitCraft Econ Console Starting ===")

        # Python environment
        logging.info(f"Python version: {sys.version}")
        logging.debug(f"Python executable: {sys.executable}")
        logging.info(f"Python platform: {platform.platform()}")

        # System info
        logging.info(f"Operating System: {platform.system()} {platform.release()}")
        logging.info(f"Architecture: {platform.machine()}")
        logging.info(f"Processor: {platform.processor()}")

        # Environment variables that might affect UI
        env_vars_to_check = ["DISPLAY", "QT_SCALE_FACTOR", "GDK_SCALE", "GDK_DPI_SCALE"]
        for env_var in env_vars_to_check:
            value = os.environ.get(env_var)
            if value:
                logging.debug(f"Environment {env_var}: {value}")

        # Execution context
        if getattr(sys, "frozen", False):
            logging.debug("Running from executable (frozen)")
            logging.debug(f"Executable path: {sys.executable}")
        else:
            logging.debug("Running from source code")
            logging.debug(f"Script path: {__file__}")

        logging.info("System environment logged successfully")

    except Exception as e:
        logging.error(f"Error logging system environment: {e}")


if __name__ == "__main__":
    # Log system environment at startup
    log_system_environment()

    # Begin running the app
    sys.argv.append("--webEngineArgs")
    sys.argv.append("--remote-allow-origins=*")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
