"""Caminhos e constantes compartilhados pelo Data Pilot."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_CSV = DATA_DIR / "sales.csv"
CLEAN_CSV = DATA_DIR / "sales_clean.csv"

# Formato do CSV limpo (padrão brasileiro): ";" como separador e vírgula decimal.
# Escrever e ler com os mesmos parâmetros evita números virando texto.
CSV_SEP = ";"
CSV_DECIMAL = ","
CSV_ENCODING = "utf-8-sig"  # o BOM faz o Excel abrir os acentos corretamente

STATUS_CONCLUIDO = "concluído"
STATUS_CANCELADO = "cancelado"
STATUS_PENDENTE = "pendente"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/free"
