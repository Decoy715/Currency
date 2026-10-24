import os
from pathlib import Path

from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

# Читаем .env и кладём переменные из него в os.environ
load_dotenv()

# Корень проекта: llm.py -> src/currency -> src -> корень.
# Путь считается от самого файла, а не от папки, из которой запущен скрипт.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Сертификат Минцифры для HTTPS лежит в корне проекта
CA_CERT = PROJECT_ROOT / "Russian_Trusted_Root_CA.cer"

# Системный промпт: задаёт роль и стиль ответов модели.
# Отправляется в каждом запросе, поэтому тратит токены каждый раз.
SYSTEM_PROMPT = (
    "Ты помощник BI-аналитика. Отвечай кратко, по-русски, "
    "без лишних вступлений. Если не знаешь ответа, так и скажи."
)


def ask(question: str) -> str:
    # Запрос к модели — это список сообщений с ролями:
    # SYSTEM — инструкция для модели, USER — вопрос человека
    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT),
            Messages(role=MessagesRole.USER, content=question),
        ],
    )
    # with закрывает соединение с API после выхода из блока
    with GigaChat(
        credentials=os.environ["GIGACHAT_CREDENTIALS"],  # ключ авторизации из .env
        scope="GIGACHAT_API_PERS",  # тип доступа к апи
        ca_bundle_file=str(CA_CERT),  # SDK ждёт строку, поэтому Path -> str
        model="GigaChat-2",  # какую модель вызывать; список — giga.get_models()
    ) as giga:
        response = giga.chat(payload)

    # Сколько токенов ушло на вопрос (prompt) и ответ (completion)
    print(response.usage)
    # Ответ вложенный: список вариантов -> первый -> сообщение -> текст
    return response.choices[0].message.content


if __name__ == "__main__":
    print(ask("Что такое ключевая ставка ЦБ РФ?"))
