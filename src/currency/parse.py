import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Читаем .env и кладём переменные из него в os.environ
load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Сертификат Минцифры для HTTPS лежит в корне проекта
CA_CERT = PROJECT_ROOT / "Russian_Trusted_Root_CA.cer"


class Item(BaseModel):
    code: str = Field(
        pattern=r"^[A-Z]{3}$",
        description=("Код валюты ISO 4217, 3 заглавные латинские буквы, например USD"))
    amount: float = Field(gt=0, description="Количество валюты для перевода в рубли")


class ConvertRequest(BaseModel):
    items: list[Item] = Field(default_factory=list, description="Список валют и количество валюты для перевода в рубли")
    error: Literal["not_currency", "from_rub"] | None = Field(default=None, description="Текст ошибки если она произошла, from_rub ошибка о переводи валюты из рублей, not_currency ошибка о вопросе не о переводе валют")


SYSTEM_PROMPT = (
    "Извлеки из сообщения пользователя валюты и суммы. Если целевая валюта не указана, считай, что перевод в рубли. \n"
    "Правила:\n"
    "1.Если в запросе нет валют заполни поле error literal. Пример: not_currency \n"
    "2.Если исходная валюта — рубли, заполни поле error. Пример: from_rub\n"
    "3.Если error заполнен, items должен быть пустым"
    "4.Верни один JSON-объект, который соответствует схеме,  Ответь чистым JSON без Markdown-разметки и без ```. Не повторяй схему\n"
    "Схема:\n"
    + json.dumps(ConvertRequest.model_json_schema(), ensure_ascii=False)
)


def parse_request(text: str) -> ConvertRequest:
    payload = Chat(
        messages=[Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT),
                    Messages(role=MessagesRole.USER, content=text),],
        temperature=0.1,    
    )
    with GigaChat(
        credentials=os.environ["GIGACHAT_CREDENTIALS"],  # ключ авторизации из .env
        scope="GIGACHAT_API_PERS",  # тип доступа к апи
        ca_bundle_file=str(CA_CERT),  # SDK ждёт строку, поэтому Path -> str
        model="GigaChat-2",  # какую модель вызывать; список — giga.get_models()
    ) as giga:
        response = giga.chat(payload)
    print(response.usage)
    content = response.choices[0].message.content
    print(content)           # смотрим, что вернула модель, до валидации
    return ConvertRequest.model_validate_json(content)


if __name__ == "__main__":
    #print(json.dumps(ConvertRequest.model_json_schema(), indent=2, ensure_ascii=False))
    print(parse_request("Какая сегодня погода?"))