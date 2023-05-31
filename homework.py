import os
import time
import sys
import logging
import json
from http import HTTPStatus

import telegram
import requests
from telegram import TelegramError
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    encoding='UTF-8',
    filemode='w'
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        logger.debug(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as error:
        logger.error(error)


def get_api_answer(timestamp):
    """Запрос к API сервиса."""
    times = timestamp or int(time.time())
    params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': times}
    }
    try:
        response = requests.get(**params)
    except requests.exceptions.RequestException as error:
        return SystemExit(error)
    else:
        if response.status_code != HTTPStatus.OK:
            error_message = 'Статус страницы не равен 200'
            raise requests.HTTPError(error_message)
        try:
            return response.json()
        except json.decoder.JSONDecodeError:
            raise ("N'est pas JSON")


def check_response(response):
    """Проверяет API на соответствие."""
    if not isinstance(response, dict):
        raise TypeError('Ожидаемый тип данных — словарь!')
    if 'homeworks' not in response and 'current_date' not in response:
        raise KeyError('В ответе от API отсутствует ключ homeworks')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ожидаемый тип данных — список!')
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if not isinstance(homework, dict):
        raise TypeError('Ожидаемый тип данных — словарь!')
    if 'homework_name' not in homework:
        raise KeyError('Не найден ключ homework_name!')
    if 'status' not in homework:
        raise KeyError('Не найден ключ status!')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы - {homework_status}')
    return ('Изменился статус проверки работы "{homework_name}". {verdict}'
            ).format(homework_name=homework_name,
                     verdict=HOMEWORK_VERDICTS.get(homework_status)
                     )


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    if not check_tokens():
        logger.critical('Ошибка в получении токенов!')
        sys.exit()
    current_report = {}
    prev_report = {}
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                if homework:
                    message = parse_status(homework)
                    current_report[
                        response.get("homework_name")] = response.get("status")
                    if current_report != prev_report:
                        send_message(bot, message)
                        prev_report = current_report.copy()
                        current_report[
                            response.get("homework_name")
                        ] = response.get("status")
                timestamp = response.get("current_date")
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        else:
            logger.error("Сбой, ошибка не найдена")
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
