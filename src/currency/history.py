import asyncio
import datetime
import httpx

BASE = "https://www.cbr-xml-daily.ru/archive/{}/daily_json.js"


def make_url(day: datetime.date) -> str:
    return BASE.format(day.strftime("%Y/%m/%d"))   # 2026/10/23


async def fetch_usd(client: httpx.AsyncClient, day: datetime.date) -> float | None:
    try:
        response = await client.get(make_url(day))                  # запрос по make_url(day)
        response.raise_for_status()
        return response.json()["Valute"]["USD"]["Value"]                   # курс USD из ответа
    except httpx.HTTPStatusError:
        return None                              # выходной, данных нет


async def main():
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(30)]

    async with httpx.AsyncClient() as client:
        tasks = [fetch_usd(client, day) for day in days]            # задача fetch_usd для каждого дня
        results = await asyncio.gather(*tasks)

    for day, rate in zip(days, results):
        if rate is None:
            print(f"{day}: нет данных")
        else:
            print(f"{day}: {rate:.2f} ₽")


asyncio.run(main())