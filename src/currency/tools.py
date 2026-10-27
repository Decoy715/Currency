import json
import os
from pathlib import Path

from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Function, FunctionParameters, Messages, MessagesRole

from main import get_rates

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Сертификат Минцифры для HTTPS лежит в корне проекта
CA_CERT = PROJECT_ROOT / "Russian_Trusted_Root_CA.cer"


def get_rate(code: str, amount: float = 1) -> dict:
    """Настоящая функция, которую вызывает наш код по просьбе модели."""
    # Аргументы от модели проверяем сами: схема — подсказка, а не гарантия
    code = code.strip().upper()
    amount = float(amount)
    if amount <= 0:
        return {"error": "Сумма должна быть больше нуля"}
    rates = get_rates([code])
    if code not in rates:
        # Ошибку возвращаем как данные: модель прочитает и объяснит пользователю
        return {"error": f"ЦБ РФ не публикует курс для {code}"}
    # rate_per_unit делит Value на Nominal: курс JPY публикуется за 100 иен
    currency = rates[code]
    return {
        "code": code,
        "amount": amount,
        "rate": currency.rate_per_unit(),
        # Считает код, а не модель: LLM ошибаются в арифметике
        "total": round(currency.convert(amount), 2),
    }


# Описание инструмента: модель увидит имя, описание и параметры
GET_RATE = Function(
    name="get_rate",
    description=(
        "Возвращает официальный курс валюты ЦБ РФ к рублю на сегодня (за 1 единицу) "
        "и стоимость заданной суммы в рублях (total). "
        "Вызывай для любого вопроса о курсе или стоимости иностранной валюты "
        "в рублях, в том числе для криптовалют. Сам курс не придумывай и не "
        "пересчитывай: бери total из результата."
    ),
    parameters=FunctionParameters(
        type="object",
        properties={
            "code": {
                "type": "string",
                "description": "Код валюты ISO 4217, например USD",
            },
            "amount": {
                "type": "number",
                "description": "Сумма в этой валюте. Если пользователь не назвал сумму, не передавай",
            },
        },
        required=["code"],
    ),
)

# Какая функция Python стоит за каким именем инструмента
TOOLS = {"get_rate": get_rate}


def ask(question: str) -> str:
    # История диалога: в каждый запрос уходит целиком, модель ничего не помнит
    messages = [Messages(role=MessagesRole.USER, content=question)]

    with GigaChat(
        credentials=os.environ["GIGACHAT_CREDENTIALS"],  # ключ авторизации из .env
        scope="GIGACHAT_API_PERS",  # тип доступа: PERS — физлицо, CORP — юрлицо
        ca_bundle_file=str(CA_CERT),  # SDK ждёт строку, поэтому Path -> str
        model="GigaChat-2",  # какую модель вызывать; список — giga.get_models()
    ) as giga:
        # Запрос 1: модель видит вопрос и список инструментов
        response = giga.chat(
            Chat(messages=messages, functions=[GET_RATE], function_call="auto")
        )
        choice = response.choices[0]

        if choice.finish_reason == "function_call":
            call = choice.message.function_call
            print(f"   [модель просит: {call.name}({call.arguments})]")

            # Вызываем настоящую функцию; ** распаковывает {"code": "USD"} в code="USD"
            result = TOOLS[call.name](**call.arguments)
            print(f"   [результат: {result}]")

            # В историю: сначала просьба модели, потом ответ функции
            messages.append(choice.message)
            messages.append(
                Messages(
                    role=MessagesRole.FUNCTION,
                    name=call.name,
                    content=json.dumps(result, ensure_ascii=False),
                )
            )

            # Запрос 2: модель видит всю историю и пишет ответ человеку
            response = giga.chat(Chat(messages=messages, functions=[GET_RATE]))
            choice = response.choices[0]

    return choice.message.content


if __name__ == "__main__":
    questions = [
        "Сколько сейчас стоит доллар?",
        "Почём 100 юаней?",
        "Почём 1537,25 юаня?",
        "Какой курс биткоина?",
        "Привет! Как дела?",
    ]
    for question in questions:
        print(">>", question)
        print(ask(question))
