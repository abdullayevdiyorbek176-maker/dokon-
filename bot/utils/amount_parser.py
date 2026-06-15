import re

_MULTIPLIERS = [
    ('mlrd', 1_000_000_000),
    ('milliard', 1_000_000_000),
    ('milion', 1_000_000),
    ('million', 1_000_000),
    ('mln', 1_000_000),
    ('ming', 1_000),
]


def parse_amount(text: str) -> tuple:
    """
    Uzbek raqam formatlarini parse qiladi.

    Misollar:
      '200ming'   → (200000.0, False)
      '250ming'   → (250000.0, False)
      '1milion'   → (1000000.0, False)
      '1.5ming'   → (1500.0, False)
      '200.000'   → (200000.0, False)   # Uzbek minglik nuqta
      '200 000'   → (200000.0, False)
      '1,500,000' → (1500000.0, False)
      '100$'      → (100.0, True)
      '200ming$'  → (200000.0, True)
      '100000'    → (100000.0, False)

    Returns: (float|None, is_usd: bool)
    """
    t = text.strip().lower()

    is_usd = '$' in t or 'usd' in t
    t = t.replace('$', '').replace('usd', '').strip()

    mult = 1
    for suffix, m in _MULTIPLIERS:
        if t.endswith(suffix):
            t = t[:-len(suffix)].rstrip()
            mult = m
            break

    # "100 000" → "100000"
    t = t.replace(' ', '')

    # Minglik nuqta: "200.000" → "200000", "1.500.000" → "1500000"
    # Qoida: nuqtadan keyin AYNAN 3 ta raqam kelsa → minglik ajratgich
    for _ in range(6):
        new_t = re.sub(r'(\d)\.(\d{3})(?!\d)', r'\1\2', t)
        if new_t == t:
            break
        t = new_t

    # Vergulni olib tashlash: "1,500,000" → "1500000"
    t = t.replace(',', '')

    # Faqat raqam va nuqta
    t = re.sub(r'[^\d.]', '', t)

    if not t or t == '.':
        return None, is_usd

    try:
        val = float(t) * mult
        if val < 0:
            return None, is_usd
        return val, is_usd
    except ValueError:
        return None, is_usd


def fmt_som(amount: float) -> str:
    """200000 → '200.000' (Uzbek minglik nuqta formati)"""
    return f"{int(round(amount)):,}".replace(",", ".")
