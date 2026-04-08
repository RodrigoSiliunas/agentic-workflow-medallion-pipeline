"""Extrator de dados de veiculo (marca, modelo, ano)."""

import re

MODEL_TO_BRAND: dict[str, str] = {
    "onix": "chevrolet", "prisma": "chevrolet", "cruze": "chevrolet",
    "tracker": "chevrolet", "spin": "chevrolet", "s10": "chevrolet",
    "celta": "chevrolet", "cobalt": "chevrolet", "montana": "chevrolet",
    "gol": "volkswagen", "polo": "volkswagen", "virtus": "volkswagen",
    "t-cross": "volkswagen", "nivus": "volkswagen", "saveiro": "volkswagen",
    "fox": "volkswagen", "voyage": "volkswagen", "up": "volkswagen",
    "civic": "honda", "hr-v": "honda", "city": "honda", "fit": "honda",
    "wr-v": "honda",
    "corolla": "toyota", "yaris": "toyota", "hilux": "toyota",
    "etios": "toyota", "sw4": "toyota", "rav4": "toyota",
    "hb20": "hyundai", "creta": "hyundai", "tucson": "hyundai",
    "kicks": "nissan", "versa": "nissan", "march": "nissan",
    "renegade": "jeep", "compass": "jeep", "commander": "jeep",
    "argo": "fiat", "cronos": "fiat", "mobi": "fiat", "uno": "fiat",
    "palio": "fiat", "toro": "fiat", "strada": "fiat", "pulse": "fiat",
    "fiesta": "ford", "ka": "ford", "ecosport": "ford", "ranger": "ford",
    "kwid": "renault", "sandero": "renault", "duster": "renault",
}

MODELS_PATTERN = "|".join(re.escape(m) for m in MODEL_TO_BRAND)
YEAR_PATTERN = r"\b(19[89]\d|20[012]\d)\b"


def extract(text: str | None) -> dict[str, str | None]:
    """Extrai marca, modelo e ano do texto."""
    result: dict[str, str | None] = {"brand": None, "model": None, "year": None}
    if not text:
        return result

    text_lower = text.lower()

    model_match = re.search(MODELS_PATTERN, text_lower)
    if model_match:
        model = model_match.group()
        result["model"] = model
        result["brand"] = MODEL_TO_BRAND.get(model)

    year_match = re.search(YEAR_PATTERN, text)
    if year_match:
        result["year"] = year_match.group()

    return result
