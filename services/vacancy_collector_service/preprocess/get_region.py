# GEO_service/get_region.py
import sys
from pathlib import Path

import requests

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config import configs

def get_region_dadata(city_name):
    """
    Получение региона и ISO кода региона по названию города через DaData API"""
    if not city_name:
        return None

    try:
        url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
        headers = {
            "Authorization": f"Token {configs.GEO_TOKEN}",
            "Content-Type": "application/json",
        }
        data = {"query": city_name}

        response = requests.post(url, headers=headers, json=data, timeout=5)
        response.raise_for_status()

        result = response.json()

        if result.get("suggestions"):
            suggestion = result["suggestions"][0]
            data_obj = suggestion.get("data", {})
            region = data_obj.get("region_with_type")
            if not region:
                region = data_obj.get("region")
            region_code = data_obj.get("region_iso_code")
            if region and region_code:
                return {
                    "region": region,
                    "region_code": region_code
                }
            if region:
                return {
                    "region": region,
                    "region_code": None
                }

        return None

    except requests.RequestException as e:
        print(f"Ошибка запроса к DaData для '{city_name}': {e}")
        return None


print(get_region_dadata("Ижевск, Пушкинская улица, 136А"))
