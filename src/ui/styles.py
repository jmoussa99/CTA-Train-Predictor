from src.config import BG_COLOR, FADE_DURATION_MS, HEADER_BG, PURPLE_COLOR, RED_COLOR

FONT_FAMILY = "Helvetica Neue"
FONT_DESTINATION_SIZE = 28
FONT_MINUTES_SIZE = 32
FONT_METADATA_SIZE = 14
FONT_HEADER_SIZE = 16

AMBER_COLOR = "#ff9500"
DIMMED_TEXT = "#666666"
WHITE = "#ffffff"

MAIN_STYLESHEET = f"""
    QMainWindow, QWidget#central {{
        background-color: {BG_COLOR};
    }}
"""

HEADER_STYLESHEET = f"""
    QWidget#header {{
        background-color: {HEADER_BG};
        border-bottom: 1px solid #444444;
    }}
    QLabel#headerStation {{
        color: {WHITE};
        font-family: "{FONT_FAMILY}";
        font-size: {FONT_HEADER_SIZE}pt;
        font-weight: bold;
    }}
    QLabel#headerWalk {{
        color: {DIMMED_TEXT};
        font-family: "{FONT_FAMILY}";
        font-size: {FONT_METADATA_SIZE}pt;
    }}
"""

STATUS_STYLESHEET = f"""
    QLabel#status {{
        color: {DIMMED_TEXT};
        font-family: "{FONT_FAMILY}";
        font-size: 11pt;
        padding: 4px 8px;
    }}
"""
