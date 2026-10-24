import httpx
from pydantic import BaseModel
URL = "https://www.cbr-xml-daily.ru/daily_json.js"

class Currency(BaseModel):
    CharCode: str
    Nominal: int
    Name: str
    Value: float
    def rate_per_unit(self) -> float:
        return self.Value/self.Nominal                 # Value делить на Nominal (через self.)
    def convert(self, amount: float) ->float:
        return self.rate_per_unit()*amount

def get_rates(codes: list[str]) -> dict[str, Currency]:
    response = httpx.get(URL)
    response.raise_for_status()
    valute_info = response.json()["Valute"]

    result = {}
    for code in codes:
        if code in valute_info:
            result[code] = Currency(**valute_info[code])    # объект Currency из valute_info[code]
        else:
            print(f"Валюта {code} не найдена")
    return result

rates = get_rates(["USD", "EUR", "CNY", "XYZ"])
for code, cur in rates.items():
    print(f"{cur.Name}: {cur.rate_per_unit():.4f} ₽")
    print(f"{cur.Name} * 70 = {cur.convert(70):.2f} ₽")

Currency(CharCode="USD", Nominal="10", Name="Доллар", Value=80)



