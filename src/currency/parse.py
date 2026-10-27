import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from pydantic import BaseModel, Field

from main import Currency, get_rates

# Читаем .env и кладём переменные из него в os.environ
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Сертификат Минцифры для HTTPS лежит в корне проекта
CA_CERT = PROJECT_ROOT / "Russian_Trusted_Root_CA.cer"

# Регулярка для кода валюты: ровно 3 заглавные латинские буквы
CURRENCY_CODE = r"^[A-Z]{3}$"


class Item(BaseModel):
    code: str = Field(
        pattern=CURRENCY_CODE,
        description="Исходная валюта (что есть у пользователя), код ISO 4217, например USD",
    )
    amount: float = Field(
        gt=0,
        description="Сумма в исходной валюте",
    )
    target: str = Field(
        default="RUB",
        pattern=CURRENCY_CODE,
        description="Целевая валюта (во что перевести), код ISO 4217. Если не указана — RUB",
    )


class ConvertRequest(BaseModel):
    items: list[Item] = Field(
        default_factory=list,
        description="Список переводов из сообщения пользователя",
    )
    error: Literal["not_currency"] | None = Field(
        default=None,
        description="not_currency — сообщение не про перевод валют. Иначе null",
    )


# Результат для пользователя: все поля Item + причина отказа.
# Отдельная модель, чтобы reason не попал в схему для LLM
class ItemResult(Item):
    reason: str | None = Field(
        default=None,
        description="None — конвертация принята, иначе причина отказа",
    )


# Тексты для пользователя пишет код, а не модель
MESSAGES = {
    "not_currency": "Вопрос не связан с конвертацией валют",
    "not_to_rub": "Доступна только конвертация валюты в рубли",
    "unknown_currency": "ЦБ РФ не публикует курс для: {}",
}

SYSTEM_PROMPT = (
    "Извлеки из сообщения пользователя переводы валют: исходную валюту, сумму "
    "и целевую валюту.\n"
    "Правила:\n"
    "1. Если целевая валюта не указана, target = RUB.\n"
    "2. Записывай валюты как есть, даже если это рубли. Ничего не проверяй и не отказывай.\n"
    "3. Если сообщение не про перевод валют, верни только error = not_currency. "
    "Других значений error не бывает.\n"
    "4. Ответь чистым JSON без Markdown-разметки. Не повторяй схему.\n"
    "Примеры:\n"
    'Сообщение: Переведи 20 фунтов\n'
    'Ответ: {"items": [{"code": "GBP", "amount": 20, "target": "RUB"}]}\n'
    'Сообщение: Сколько будет 10 тугриков\n'
    'Ответ: {"items": [{"code": "MNT", "amount": 10, "target": "RUB"}]}\n'
    'Сообщение: Сколько долларов за 3000 рублей?\n'
    'Ответ: {"items": [{"code": "RUB", "amount": 3000, "target": "USD"}]}\n'
    'Сообщение: Посоветуй фильм\n'
    'Ответ: {"error": "not_currency"}\n'
    "Схема:\n"
    + json.dumps(ConvertRequest.model_json_schema(), ensure_ascii=False)
)


def check_item(item: Item, rates: dict[str, Currency]) -> ItemResult:
    """Поштучная проверка одной конвертации."""
    # Бизнес-правило проверяет код, а не модель.
    # Идёт первым, иначе RUB из "рубли в евро" получил бы причину про ЦБ
    if item.target != "RUB":
        return ItemResult(**item.model_dump(), reason=MESSAGES["not_to_rub"])
    # Валюта должна быть у ЦБ: проверяем по живым данным
    if item.code not in rates:
        return ItemResult(
            **item.model_dump(),
            reason=MESSAGES["unknown_currency"].format(item.code),
        )
    return ItemResult(**item.model_dump())


def parse_request(text: str) -> list[ItemResult]:
    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT),
            Messages(role=MessagesRole.USER, content=text),
        ],
        temperature=0.1,  # для извлечения данных нужна стабильность, а не творчество
    )
    with GigaChat(
        credentials=os.environ["GIGACHAT_CREDENTIALS"],  # ключ авторизации из .env
        scope="GIGACHAT_API_PERS",  # тип доступа: PERS — физлицо, CORP — юрлицо
        ca_bundle_file=str(CA_CERT),  # SDK ждёт строку, поэтому Path -> str
        model="GigaChat-2",  # какую модель вызывать; список — giga.get_models()
    ) as giga:
        response = giga.chat(payload)

    print(response.usage)
    content = response.choices[0].message.content

    # Страховка в коде: если модель всё же обернула ответ в ```json ... ```
    content = content.strip().removeprefix("```json").removesuffix("```").strip()

    # Модель сломалась (не JSON, чужой код ошибки) -> ValidationError
    result = ConvertRequest.model_validate_json(content)

    # Проверки уровня запроса: разбирать нечего -> ValueError
    if result.error:
        raise ValueError(MESSAGES[result.error])
    # Пустой список без ошибки: модель не нашла валюты и не сказала почему
    if not result.items:
        raise ValueError(MESSAGES["not_currency"])

    # Проверки уровня элемента: каждый Item отдельно, без raise
    rates = get_rates([item.code for item in result.items])
    return [check_item(item, rates) for item in result.items]


if __name__ == "__main__":
    phrases = [
        "Переведи 100 долларов и 50 евро в рубли",
        "Сколько будет полтинник юаней?",
        "Переведи 1,5 тысячи рублей в доллары",
        "Какая сегодня погода?",
        "Переведи 100 долларов в рубли и 200 рублей в евро",
        "Переведи 100 тугриков",
        "Переведи 2 биткоина",
        "Переведи 100 долларов и 2 биткоина",
    ]
    for phrase in phrases:
        print(">>", phrase)
        try:
            for item in parse_request(phrase):
                status = "OK" if item.reason is None else f"отказ: {item.reason}"
                print(f"   {item.amount} {item.code} -> {item.target}: {status}")
        except ValueError as e:
            print("Отказ:", e)
