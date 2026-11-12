"""Load private local configuration without overriding explicit shell settings."""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False, encoding='utf-8-sig')
