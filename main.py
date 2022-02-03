import threading
from time import sleep
import datetime

import db

import telebot
from telebot import types

from settings import TOKEN, MAX_PINS, TEACHER

bot = telebot.TeleBot(TOKEN)


def run_continuously(interval=1):
    """Настройка потока для асинхронного контроля за расписанием"""
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                # основная функция контроля расписания
                check_scheduled_event()
                # print('async')
                sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


def check_scheduled_event():
    """Ищем события по расписанию и реализуем, 'просрочку' отменяем"""
    pins = db.pin_get_nearest()
    for pin in pins:

        expired = db.pin_get_expired(pin['own'])
        for e in expired:
            if e == pin:
                continue
            cancel_scheduled_event_without_save(e)
            db.pin_update(e)
            send_message(e, f'Задача "{e["title"]}" просрочена.. (')

        send_kick(pin)


def gen_kb(btn_list):
    """Генерация кнопок markup тг"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                       one_time_keyboard=True,
                                       row_width=1)
    for answ in btn_list:
        markup.add(types.KeyboardButton(answ))
    return markup


kb_stage = [
    # 0 "title"!
    [],

    # 1 "title"!
    [
        'Ок. Я приступил!',  # Положительный +1
        '',  # Нейтральный +0
        'Позже. Дай 10 мин.',  # Отрицательный -1
        'Форс-мажор. Сегодня пропустим!',  # Отрицательный -2
    ],

    # 2 Выполнено?
    [
        'Готово!',  # Положительный +1
        'Делаю. Дай 10 мин.',  # Нейтральный +0
        '',  # Отрицательный -1
    ],

    # 3 Отчет?
    [
        'Да! Сейчас пришлю фото и текстовое описание.',  # Положительный +1
        '',  # Нейтральный +0
        'Нет. Я не делал. Сейчас начинаю..',  # Отрицательный -1
    ],

    # 4 - прием файлов, фото и текста
    [],

    # 5 Ещё?
    [
        'Это всё!',  # Положительный +1
        '',  # Нейтральный +0
        'Сейчас пришлю ещё.',  # Отрицательный -1
    ],
]


def send_message(pin, text, _callback=None, markup=None):
    """Отправляем напоминание с настройками: текст, ф-ия и клава"""
    bot.clear_step_handler_by_chat_id(int(pin['own']))
    message = bot.send_message(pin['own'], text, reply_markup=markup)
    if _callback is not None:
        bot.register_next_step_handler(message, _callback, pin)


def update_event(pin, timeout, stage):
    """Добавляем время отправления след сообщения (текст от этапа)"""
    pin['next_time_to_kick'] = datetime.datetime.today() + timeout
    pin['current_stage'] = stage
    db.pin_update(pin)


def send_kick(pin):
    if pin['current_stage'] == 0:
        pin['current_stage'] += 1
        db.pin_update(pin)
        send_message(pin, pin["title"], _callback=callback_answer,
                     markup=gen_kb(kb_stage[pin['current_stage']]))
        update_event(pin, datetime.timedelta(minutes=5), pin['current_stage'])
    elif pin['current_stage'] == 1:
        send_message(pin, pin["title"] + "!!!!!", _callback=callback_answer,
                     markup=gen_kb(kb_stage[pin['current_stage']]))
        update_event(pin, datetime.timedelta(minutes=1), pin['current_stage'])
    elif pin['current_stage'] == 2:
        send_message(pin, "Выполнено?", _callback=callback_answer,
                     markup=gen_kb(kb_stage[pin['current_stage']]))
        update_event(pin, datetime.timedelta(minutes=1), pin['current_stage'])
    elif pin['current_stage'] == 3:
        send_message(pin, "Отчет?", _callback=callback_answer,
                     markup=gen_kb(kb_stage[pin['current_stage']]))
        update_event(pin, datetime.timedelta(seconds=4), pin['current_stage'])
    elif pin['current_stage'] == 4:
        send_message(pin, "Я жду текст, фото или документ..",
                     _callback=callback_answer, markup=None)
        update_event(pin, datetime.timedelta(minutes=2), pin['current_stage'])
    elif pin['current_stage'] == 5:
        send_message(pin, "Еще пришлешь?", _callback=callback_answer,
                     markup=gen_kb(kb_stage[pin['current_stage']]))
        update_event(pin, datetime.timedelta(minutes=2), pin['current_stage'])
    elif pin['current_stage'] == 6:
        if reset_scheduled_event_without_save(pin):
            db.pin_update(pin)
            send_message(pin, "Молодцом.")
        else:
            send_message(pin, "Ошибка завершения.")

    elif pin['current_stage'] < 0:
        if pin['reset_counter'] - 2 * pin['cancel_counter'] > 0:
            if cancel_scheduled_event_without_save(pin):
                send_message(pin, "Ок, но в след. раз придется сделать.")
                db.pin_update(pin)
        else:
            send_message(pin, "Слишком часто пропускаешь..",
                         _callback=None, markup=None)
            update_event(pin, datetime.timedelta(seconds=4), 0)


def callback_answer(message, pin):
    # print(message.chat.id, "callback_answer", pin)
    try:
        bot.clear_step_handler_by_chat_id(message.chat.id)

        # Положительный увеличивает этап
        # Нейтральный добавляет 10 минут
        # Отрицательный возвращает на пред. этап

        cs = pin['current_stage']  # current_stage

        if cs == 1 and message.content_type == "text" and message.text in kb_stage[cs]:
            i = kb_stage[cs].index(message.text)
            if i == 0:
                update_event(pin, datetime.timedelta(minutes=30), pin['current_stage']+1)
            elif i == 1:
                update_event(pin, datetime.timedelta(minutes=10), pin['current_stage'])
            elif i == 2:
                update_event(pin, datetime.timedelta(minutes=10), pin['current_stage']-1)
            elif i == 3:
                update_event(pin, datetime.timedelta(seconds=2), pin['current_stage']-2)

        elif cs == 2 and message.content_type == "text" and message.text in kb_stage[cs]:
            i = kb_stage[cs].index(message.text)
            if i == 0:
                update_event(pin, datetime.timedelta(seconds=4), pin['current_stage']+1)
            elif i == 1:
                update_event(pin, datetime.timedelta(minutes=10), pin['current_stage'])
            elif i == 2:
                update_event(pin, datetime.timedelta(seconds=4), pin['current_stage']-1)
            elif i == 3:
                update_event(pin, datetime.timedelta(seconds=2), pin['current_stage']-2)

        elif cs == 3 and message.content_type == "text" and message.text in kb_stage[cs]:
            i = kb_stage[cs].index(message.text)
            if i == 0:
                update_event(pin, datetime.timedelta(seconds=0), pin['current_stage']+1)
            elif i == 1:
                update_event(pin, datetime.timedelta(minutes=10), pin['current_stage'])
            elif i == 2:
                update_event(pin, datetime.timedelta(minutes=15), pin['current_stage']-1)
            elif i == 3:
                update_event(pin, datetime.timedelta(seconds=2), pin['current_stage']-2)

        elif cs == 4:
            print(message.chat.id, 'ЭТО ОТВЕТ')
            pin['current_stage'] += 1
            send_kick(pin)

        elif cs == 5 and message.content_type == "text" and message.text in kb_stage[cs]:
            i = kb_stage[cs].index(message.text)
            if i == 0:
                update_event(pin, datetime.timedelta(seconds=1), pin['current_stage'] + 1)
            elif i == 1:
                update_event(pin, datetime.timedelta(minutes=10), pin['current_stage'])
            elif i == 2:
                pin['current_stage'] -= 1
                send_kick(pin)
            elif i == 3:
                update_event(pin, datetime.timedelta(seconds=2), pin['current_stage'] - 2)

        else:
            send_message(pin, "Моя твоя не понимать...",
                         _callback=None, markup=None)
            update_event(pin, datetime.timedelta(seconds=1), pin['current_stage'])

    except Exception as e:
        if len(f'{e}') > 0:
            print(e)
            bot.send_message(message.chat.id, f'{e}')


def check_title_in_pin(pin: dict):
    all_titles = db.pin_get_all_titles(pin['own'])
    while [pin['title']] in all_titles:
        pin['title'] += "!"
    return True


def set_pin_day(pin: dict, day):
    if day[:3] == "Пон":
        pin['mon'] = not pin['mon']
    elif day[:3] == "Вто":
        pin['tue'] = not pin['tue']
    elif day[:3] == "Сре":
        pin['wed'] = not pin['wed']
    elif day[:3] == "Чет":
        pin['tru'] = not pin['tru']
    elif day[:3] == "Пят":
        pin['fri'] = not pin['fri']
    elif day[:3] == "Суб":
        pin['sat'] = not pin['sat']
    elif day[:3] == "Вос":
        pin['sun'] = not pin['sun']
    else:
        return False
    return True


def gen_kb_titles(own):
    # Using the ReplyKeyboardMarkup class
    # It's constructor can take the following optional arguments:
    # - resize_keyboard: True/False (default False)
    # - one_time_keyboard: True/False (default False)
    # - selective: True/False (default False)
    # - row_width: integer (default 3)
    # row_width is used in combination with the add() function.
    # It defines how many buttons are fit on each row before continuing on the next row.
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                       one_time_keyboard=True,
                                       row_width=1)

    for title in db.pin_get_all_titles(own):
        markup.add(types.KeyboardButton(title[0]))

    markup.add(types.KeyboardButton('+'))

    return markup


def gen_kb_days(pin: dict):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                       one_time_keyboard=True,
                                       row_width=1)
    day = 'Понедельник'
    day += ' 📍' if pin['mon'] else ''
    markup.add(types.KeyboardButton(day))

    day = 'Вторник'
    day += ' 📍' if pin['tue'] else ''
    markup.add(types.KeyboardButton(day))

    day = 'Среда'
    day += ' 📍' if pin['wed'] else ''
    markup.add(types.KeyboardButton(day))

    day = 'Четверг'
    day += ' 📍' if pin['tru'] else ''
    markup.add(types.KeyboardButton(day))

    day = 'Пятница'
    day += ' 📍' if pin['fri'] else ''
    markup.add(types.KeyboardButton(day))

    day = 'Суббота'
    day += ' 📍' if pin['sat'] else ''
    markup.add(types.KeyboardButton(day))

    day = 'Воскресенье'
    day += ' 📍' if pin['sun'] else ''
    markup.add(types.KeyboardButton(day))

    markup.add(types.KeyboardButton('Далее'))

    return markup


def gen_kb_time():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                       one_time_keyboard=True,
                                       row_width=1)

    for h in range(0, 24, 1):
        for m in range(0, 60, 30):
            markup.add(types.KeyboardButton(f"{h}:{m}"))

    return markup


def reset_scheduled_event_without_save(pin: dict):
    """Планирование ближайшей даты и сброс этапа"""
    # print('reset_scheduled_event')
    now = datetime.datetime.today()
    d = datetime.datetime(now.year,
                          now.month,
                          now.day,
                          hour=pin['time'].hour,
                          minute=pin['time'].minute)
    timeout = 0
    while True:
        # print(now)
        # print(d)
        if (d.weekday() + 1) in (pin['mon'] * 1,
                                 pin['tue'] * 2,
                                 pin['wed'] * 3,
                                 pin['tru'] * 4,
                                 pin['fri'] * 5,
                                 pin['sat'] * 6,
                                 pin['sun'] * 7) and (now <= d):
            nearest = d
            break
        else:
            d += datetime.timedelta(days=1)

        timeout += 1
        if timeout > 50:
            print("reset False timeout")
            return False

    pin['next_time_to_kick'] = nearest
    pin['current_stage'] = 0
    pin['reset_counter'] += 1
    # print("reset True")
    return True


def cancel_scheduled_event_without_save(pin: dict):
    """То же, что и reset, только со счетчиком cancel"""
    if reset_scheduled_event_without_save(pin):
        pin['cancel_counter'] += 1
        return True
    return False


# Начало. Вывод текущих напоминаний. Кнопки их отключения, создание новой.
@bot.message_handler(commands=['start'])
def f_start(message):
    own = message.chat.id
    print(message)
    try:
        s = ''
        s += f'Здравствуй!\n\nЯ твой персональный помощник.\n'

        titles = db.pin_get_all_titles(own)
        if len(titles) > 0:
            s += f'\nТапни на напоминалку, чтобы удалить её.\n'
        else:
            s += f'\nЧтобы начать нажми + на клавиатуре\n'

        # Запрашиваем название напоминаний для удаления или +
        bot.send_message(own, s, reply_markup=gen_kb_titles(own))
        bot.register_next_step_handler(message, f_get_title_to_del)

    except Exception as e:
        print(e)
        bot.send_message(own,
                         f'{e}\noooops, попробуй еще раз..\n\nВведите /start для продолжения')


def gen_kb_title_example():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                       one_time_keyboard=True,
                                       row_width=1)
    markup.add(types.KeyboardButton("Начать решать очередную задачу для подготовки к ГИА"))
    return markup


# Получаем название напоминания для удаления или +
def f_get_title_to_del(message):
    own = message.chat.id
    try:
        if message.content_type != "text":
            raise Exception("Ожидалось текстовое сообщение")
        title = message.text

        if title == "+" and len(db.pin_get_all_titles(own))<MAX_PINS:
            bot.send_message(own, 'Название напоминания?\n\nМожешь выбрать шаблон или ввести собственное название.',
                             reply_markup=gen_kb_title_example())
            bot.register_next_step_handler(message, f_get_title_to_add)
        elif title == "+":
            raise Exception(f"Текущее ограничение сервера {MAX_PINS} напоминалок")
        elif db.pin_delete(own, title):
            name = f"{message.from_user.first_name} {message.from_user.last_name}"
            nick = f"{message.from_user.username}"
            snitch_pin_delete(title, name, nick)
            bot.send_message(own, 'Удалено\n\nВведите /start для продолжения')
        else:
            bot.send_message(own, '"Напоминание" не найдено\n\nВведите /start для продолжения')

    except Exception as e:
        print(e)
        bot.send_message(own,
                         f'{e}\noooops, попробуйте еще раз..\n\nВведите /start для продолжения')


# Получаем название напоминания для добавления
def f_get_title_to_add(message):
    own = message.chat.id
    try:
        if message.content_type != "text":
            raise Exception("Ожидалось текстовое сообщение")

        # создаем образ напоминания
        pin = dict(db.pin_template)

        pin['own'] = own
        pin['datetime'] = datetime.datetime.today()
        pin['title'] = message.text

        check_title_in_pin(pin)

        # Запрашиваем расписание
        bot.send_message(own, 'По каким дням?', reply_markup=gen_kb_days(pin))
        bot.register_next_step_handler(message, f_get_days, pin)

    except Exception as e:
        print(e)
        bot.send_message(own,
                         f'{e}\noooops, попробуйте еще раз..\n\nВведите /start для продолжения')


# Добавляем дни недели
def f_get_days(message, pin):
    own = message.chat.id
    try:
        if message.content_type != "text":
            raise Exception("Ожидалось текстовое сообщение")

        day = message.text

        if day == 'Далее' and any([pin['mon'],
                                   pin['tue'],
                                   pin['wed'],
                                   pin['tru'],
                                   pin['fri'],
                                   pin['sat'],
                                   pin['sun']]):
            bot.send_message(own, 'В какое время?', reply_markup=gen_kb_time())
            bot.register_next_step_handler(message, f_get_time, pin)
        else:
            set_pin_day(pin, day)
            # Запрашиваем расписание
            bot.send_message(own, 'Еще?', reply_markup=gen_kb_days(pin))
            bot.register_next_step_handler(message, f_get_days, pin)

    except Exception as e:
        print(e)
        bot.send_message(own,
                         f'{e}\noooops, попробуйте еще раз..\n\nВведите /start для продолжения')


# Добавляем время
def f_get_time(message, pin):
    own = message.chat.id
    try:
        if message.content_type != "text":
            raise Exception("Ожидалось текстовое сообщение")

        time = message.text
        time = time.replace('.', ':')
        h, m = map(int, time.split(":"))

        pin['time'] = datetime.time(h, m)

        if not reset_scheduled_event_without_save(pin):
            raise Exception("Ошибка планирования")

        db.pin_insert(pin)

        bot.send_message(own, 'Готово!')

    except Exception as e:
        print(e)
        bot.send_message(own,
                         f'{e}\noooops, попробуйте еще раз..\n\nВведите /start для продолжения')


def snitch_pin_delete(title, name, nick):
    bot.send_message(TEACHER, f'Псс.. Парень, тут один перец отписался от нашей напоминалки\n\n{title}\n\n'
                              f'Это {name}\n\n'
                              f'Найти его можно тут @{nick}')


def snitch_pin_ignore(pin, name, nick):
    bot.send_message(TEACHER, f'Псс.. Парень, тут один перец упорно сопротивляется. \n\nДавай напомним ему \n\n{pin["title"]}\n\n'
                              f'Это {name}\n\n'
                              f'Найти его можно тут @{nick}')


if __name__ == "__main__":
    # Start the background thread
    stop_run_continuously = run_continuously()
    print('start bot')
    bot.polling(none_stop=True)
    stop_run_continuously.set()
    print('stop bot')
