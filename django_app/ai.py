
import json
import logging
import random
import re
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def recommend_ids(movies, interests, mood, limit=150):
    """
    Подбирает фильмы через Gemini AI.

    Возвращает список ID фильмов в порядке рекомендаций.
    Если Gemini недоступен, возвращает [].
    """

    api_key = getattr(settings, "GEMINI_API_KEY", "")
    model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        print("AI ERROR: GEMINI_API_KEY не найден.")
        return []

    if not movies:
        print("AI: Каталог фильмов пуст.")
        return []

    # Ограничиваем каталог для уменьшения размера запроса
    movies = list(movies)[:150]

    valid_ids = {m.id for m in movies}

    # Формируем каталог
    catalog = "\n".join(
        f"{m.id}|{m.title}|{m.genre}|{(m.description or '')[:150]}"
        for m in movies
    )

    # Запрос для искусственного интеллекта
    prompt = (
        f"Интересы пользователя: {interests or 'не указаны'}\n"
        f"Настроение пользователя: {mood or 'не указано'}\n\n"
        f"Каталог фильмов (id|название|жанр|описание):\n"
        f"{catalog}\n\n"
        f"Выбери до {limit} фильмов, которые лучше всего "
        f"соответствуют интересам и настроению пользователя.\n"
        "Используй только ID из каталога.\n"
        "Верни исключительно JSON-массив чисел, "
        "например: [12, 5, 40].\n"
        "Не добавляй объяснения или Markdown."
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты профессиональный помощник по подбору фильмов. "
                    "Анализируй интересы и настроение пользователя. "
                    "Выбирай только фильмы из предоставленного каталога. "
                    "Отвечай исключительно JSON-массивом ID."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    max_retries = 3

    for attempt in range(max_retries):
        try:
            print(
                f"AI: Запрос к {model}, "
                f"попытка {attempt + 1}/{max_retries}"
            )

            response = requests.post(
                URL,
                headers=headers,
                json=payload,
                timeout=20
            )

            print("AI STATUS:", response.status_code)

            # Повторяем при временных ошибках сервера
            if response.status_code in (429, 500, 502, 503, 504):
                print("AI RESPONSE:", response.text[:1500])

                if attempt < max_retries - 1:
                    delay = (2 ** attempt) + random.uniform(0, 1)

                    print(
                        f"AI: Временная ошибка. "
                        f"Повтор через {delay:.1f} сек."
                    )

                    time.sleep(delay)
                    continue

            # Остальные HTTP-ошибки
            if not response.ok:
                print("AI RESPONSE:", response.text[:1500])

            response.raise_for_status()

            # Получаем ответ Gemini
            data = response.json()

            content = data["choices"][0]["message"]["content"]

            print("AI ANSWER:", content)

            if not isinstance(content, str):
                print("AI ERROR: Ответ не является строкой.")
                return []

            # Извлекаем JSON-массив
            match = re.search(r"\[[\s\S]*?\]", content)

            if not match:
                print("AI ERROR: JSON-массив не найден.")
                return []

            ids = json.loads(match.group())

            if not isinstance(ids, list):
                print("AI ERROR: Неверный формат JSON.")
                return []

            # Проверяем существование ID
            result = []

            for item in ids:
                try:
                    movie_id = int(item)
                except (ValueError, TypeError):
                    continue

                if movie_id in valid_ids and movie_id not in result:
                    result.append(movie_id)

                if len(result) >= limit:
                    break

            print("AI RECOMMENDED IDS:", result)

            return result

        except requests.exceptions.Timeout:
            logger.warning(
                "Gemini timeout, attempt %s/%s",
                attempt + 1,
                max_retries
            )

            if attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
                continue

        except requests.exceptions.RequestException as error:
            logger.error("Gemini API error: %s", error)
            break

        except (ValueError, KeyError, IndexError, TypeError) as error:
            logger.error("Gemini response parsing error: %s", error)
            break

    print("AI: Gemini недоступен. Переход к обычному поиску.")

    return []
