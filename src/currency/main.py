import httpx

URL = "https://www.cbr-xml-daily.ru/daily_json.js"


def get_rates(codes: list[str]) -> dict[str, float]:
    response = httpx.get(URL)
    response.raise_for_status()
    valute_info = response.json()["Valute"]

    result = {}
    for code in codes:
        if code in valute_info:                       # код есть в valute_info?
            result[code] = valute_info[code]["Value"]       # взять курс этой валюты
        else:
            print(f"Валюта {code} не найдена")
    return result

rates = get_rates(["USD", "EUR", "CNY", "XYZ"])
for code, value in rates.items():
    print(f"{code}: {value:.2f} ₽")




