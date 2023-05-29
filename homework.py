import telegram
import time
import requests
import logging
import os
import sys
from http import HTTPStatus
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
    encoding = 'UTF-8',
    filemode='w'
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Telegram чат"""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение не отправлено в Telegram чат: {telegram_error}')


def get_api_answer(timestamp):
    """Запрос к API сервиса."""
    time = timestamp or int(time.time())
    params = {
        'url':ENDPOINT,
        'headers':HEADERS,
        'params': {'from_date': time}
    }
    try:
        response = requests.get(**params)
    except Exception as error:
        logger.error(f'Ошибка при запросе к API сервиса: {error}')
    else:
        if response.status_code != HTTPStatus.OK:
            error_message = 'Статус страницы не равен 200'
            raise requests.HTTPError(error_message)
        return response.json()


def check_response(response):
    """Проверяет API на соответствие."""
    logger.info("Ответ от сервера получен")
    homeworks_response = response['homeworks']
    logger.info("Список домашних работ получен")
    if not homeworks_response:
        message_status = ("Отсутствует статус homeworks")
        raise LookupError(message_status)
    if not isinstance(homeworks_response, list):
        message_list = ("Невернй тип входящих данных")
        raise TypeError(message_list)
    if 'homeworks' not in response.keys():
        message_homeworks = 'Ключ "homeworks" отсутствует в словаре'
        raise KeyError(message_homeworks)
    if 'current_date' not in response.keys():
        message_current_date = 'Ключ "current_date" отсутствует в словаре'
        raise KeyError(message_current_date)
    return homeworks_response


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS[homework_status]
    if 'homework_name' not in homework:
        raise KeyError('В ответе отсуствует ключ homework_name')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы - {homework_status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


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
            homework = check_response(response)[0]
            if homework:
                message = parse_status(homework)
                current_report[response.get("homework_name")] = response.get("status")
                if current_report != prev_report:
                    send_message(bot, message)
                    prev_report = current_report.copy()
                    current_report[response.get("homework_name")] = response.get("status")
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
