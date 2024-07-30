# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import logging
import sqlite3
from datetime import datetime
from random import choice

import spbu
import telebot

import functions as func
import registration_functions as reg_func
from bots_constants import bot_token
from constants import *

# создаем объект бота, передавая ему переменную, в которой содержится токен
bot = telebot.TeleBot(bot_token, threaded=False)

# модуль для записи логов
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

############
# КЛАВИАТУРЫ
############
# Для главного меню
main_keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True,
                                                  one_time_keyboard=False)
main_keyboard.row("Расписание")
main_keyboard.row(emoji["info"], emoji["settings"])

# Для меню расписания
schedule_keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True,
                                                      one_time_keyboard=False)
schedule_keyboard.row("Сегодня", "Завтра", "Неделя")
schedule_keyboard.row(emoji["back"], emoji["alarm_clock"])

# Для меню настроек
settings_keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True,
                                                      one_time_keyboard=False)
settings_keyboard.row("Сменить группу", "Завершить")
settings_keyboard.row("Назад")


############
# Обработчики команд от пользователей
############

"""
Все обработчики  делаются:
.

Навешивается декоратор '@bot.message_handler()', который в качестве параметра принимает название команды, 
которую мы пишем боту. Например: команда '/start'. 

Дополнительно будет навешиваться ещё один обработчик, который в качестве параметра принимает строку и реагирует на неё.
Реакция будет на сообщение, содержащее строку "Сменить группу".

Все действия исполняются методом на который повесили один и более обрабочиков. 
Метод 'start_handler' сработает, если хотя бы 1 из навешанных на него сверху обработчиков отреагирует.


В качестве параметра к методу принимаем объект сообщения от пользователя. Объект 'message', в нем 
хранится само сообщение, которое пользователь написал боту. Получить к нему доступ: 'message.text'

Ещё объект message хранит текущий чат и телеграмный idшник пользователя. 
К нему  получить доступ: 'message.chat.id'. 
 
"""

@bot.message_handler(commands=["start"])
@bot.message_handler(func=lambda mess: mess.text.capitalize() == "Сменить группу",
                     content_types=["text"])
def start_handler(message):
    answer = ""

    if message.text == "/start":
        answer = "Приветствую!\n"
    elif "/start" in message.text:
        answer = "Приветствую!\nДобавляю тебя в группу..."
        bot_msg = bot.send_message(message.chat.id, answer) # просим бота отправить сообщение
        try:
            group_id = int(message.text.split()[1])
        except ValueError:
            answer = "Ошибка в id группы."
            bot.edit_message_text(answer, message.chat.id,
                                  bot_msg.message_id) # просим бота изменить уже отправленное сообщение
            message.text = "/start"
            start_handler(message)
            return

        try:
            res = spbu.get_group_events(group_id)
        except spbu.ApiException:
            answer = "Ошибка в id группы."
            bot.edit_message_text(answer, message.chat.id, bot_msg.message_id)
            message.text = "/start"
            start_handler(message)
            return

        group_title = res["StudentGroupDisplayName"][7:]
        func.add_new_user(message.chat.id, group_id, group_title)
        answer = "Готово!\nГруппа <b>{0}</b>".format(group_title)
        bot.edit_message_text(answer, message.chat.id, bot_msg.message_id,
                              parse_mode="HTML")
        answer = "Главное меню\n\n" \
                 "{0} - информация о боте\n" \
                 "{1} - настройки\n".format(emoji["info"], emoji["settings"])
        bot.send_message(chat_id=message.chat.id, text=answer,
                         reply_markup=main_keyboard,
                         parse_mode="HTML")
        return
    answer += "Загружаю список направлений..."
    bot_msg = bot.send_message(message.chat.id, answer)
    bot.send_chat_action(message.chat.id, "typing")
    answer = "Укажи свое направление:"
    divisions = spbu.get_study_divisions()
    division_names = [division["Name"] for division in divisions]
    divisions_keyboard = telebot.types.ReplyKeyboardMarkup(True, False)
    for division_name in division_names:
        divisions_keyboard.row(division_name)
    divisions_keyboard.row("Завершить")
    data = json.dumps(divisions)

    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""DELETE FROM user_choice WHERE user_id = ?""",
                   (message.chat.id,))
    sql_con.commit()
    cursor.execute("""INSERT INTO user_choice (user_id, divisions_json)
                      VALUES (?, ?)""", (message.chat.id, data))
    sql_con.commit()
    cursor.close()
    sql_con.close()
    bot.edit_message_text(text="Готово!", chat_id=message.chat.id,
                          message_id=bot_msg.message_id)
    bot.send_message(message.chat.id, answer, reply_markup=divisions_keyboard)
    reg_func.set_next_step(message.chat.id, "select_division")


@bot.message_handler(commands=["exit"])
@bot.message_handler(func=lambda mess: mess.text.capitalize() == "Завершить",
                     content_types=["text"])
def exit_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    func.delete_user(message.chat.id, only_choice=False)
    remove_keyboard = telebot.types.ReplyKeyboardRemove(True)
    answer = "До встречи!"
    bot.send_message(message.chat.id, answer, reply_markup=remove_keyboard)


@bot.message_handler(func=lambda mess: reg_func.get_step(mess.chat.id) == "select_division" and
                                    mess.text != "/home" and mess.text.capitalize() != "Назад",
                                    content_types=["text"])
def select_division_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    reg_func.select_division(message)
    return


@bot.message_handler(func=lambda mess: reg_func.get_step(mess.chat.id) == "select_study_level" and
                                       mess.text != "/home" and mess.text.capitalize() != "Назад",
                                       content_types=["text"])
def select_study_level_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    reg_func.select_study_level(message)
    return


@bot.message_handler(func=lambda mess: reg_func.get_step(
    mess.chat.id) == "select_study_program_combination" and
                                       mess.text != "/home" and mess.text.capitalize() != "Назад",
                     content_types=["text"])
def select_study_program_combination_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    reg_func.select_study_program_combination(message)
    return


@bot.message_handler(func=lambda mess: reg_func.get_step(mess.chat.id) == "select_admission_year" and
                                       mess.text != "/home" and
                                       mess.text.capitalize() != "Назад",
                                       content_types=["text"])
def select_admission_year_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    reg_func.select_admission_year(message)
    return


@bot.message_handler(func=lambda mess: reg_func.get_step(mess.chat.id) == "select_student_group" and
                                       mess.text != "/home" and mess.text.capitalize() != "Назад",
                     content_types=["text"])
def select_student_group_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    reg_func.select_student_group(message)
    return


@bot.message_handler(func=lambda mess: reg_func.get_step(mess.chat.id) == "confirm_choice" and
                                       mess.text != "/home" and mess.text.capitalize() != "Назад",
                     content_types=["text"])
def confirm_choice_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    reg_func.confirm_choice(message)
    return


@bot.message_handler(func=lambda mess: not func.is_user_exist(mess.chat.id),
                     content_types=["text"])
def not_exist_user_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    answer = "Чтобы начать пользоваться сервисом, необходимо " \
             "зарегистрироваться.\nВоспользуйся коммандой /start"
    bot.send_message(message.chat.id, answer)


@bot.message_handler(commands=["help"])
@bot.message_handler(func=lambda mess: mess.text == emoji["info"],
                     content_types=["text"])
def help_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    answer = briefly_info_answer
    bot.send_message(message.chat.id, answer,
                     parse_mode="HTML",
                     disable_web_page_preview=True)


@bot.message_handler(commands=["home"])
@bot.message_handler(func=lambda mess: mess.text.capitalize() == "Назад" or
                                       mess.text == emoji["back"], content_types=["text"])
def home_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    func.delete_user(message.chat.id, only_choice=True)
    answer = "Главное меню"
    bot.send_message(message.chat.id, answer, reply_markup=main_keyboard)


@bot.message_handler(commands=["settings"])
@bot.message_handler(func=lambda mess: mess.text == emoji["settings"],
                     content_types=["text"])
def settings_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    func.delete_user(message.chat.id, only_choice=True)
    answer = "Настройки"
    bot.send_message(message.chat.id, answer, reply_markup=settings_keyboard)


@bot.message_handler(func=lambda mess: mess.text.capitalize() == "Расписание",
                     content_types=["text"])
def schedule_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    answer = "Меню расписания"
    bot.send_message(message.chat.id, answer, reply_markup=schedule_keyboard)


@bot.message_handler(func=lambda mess: mess.text.capitalize() == "Сегодня",
                     content_types=["text"])
def today_schedule_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    today_moscow_datetime = datetime.today() + server_timedelta
    today_moscow_date = today_moscow_datetime.date()
    json_day = func.get_json_day_data(message.chat.id, today_moscow_date)
    full_place = func.is_full_place(message.chat.id)
    answer = func.create_schedule_answer(json_day, full_place, message.chat.id)
    func.send_long_message(bot, answer, message.chat.id)


@bot.message_handler(func=lambda mess: mess.text.capitalize() == "Завтра",
                     content_types=["text"])
def tomorrow_schedule_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    tomorrow_moscow_datetime = datetime.today() + server_timedelta + \
                               timedelta(days=1)
    tomorrow_moscow_date = tomorrow_moscow_datetime.date()
    json_day = func.get_json_day_data(message.chat.id, tomorrow_moscow_date)
    full_place = func.is_full_place(message.chat.id)
    answer = func.create_schedule_answer(json_day, full_place, message.chat.id)
    func.send_long_message(bot, answer, message.chat.id)


@bot.message_handler(func=lambda mess: mess.text.capitalize() == "Неделя",
                     content_types=["text"])
def calendar_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    answer = "Выбери день:"
    week_day_calendar = telebot.types.InlineKeyboardMarkup()
    week_day_calendar.row(
        *[telebot.types.InlineKeyboardButton(text=name, callback_data=name) for
          name in week_day_number.keys()])
    week_day_calendar.row(
        *[telebot.types.InlineKeyboardButton(text=name, callback_data=name) for
          name in ["Вся неделя"]])
    bot.send_message(message.chat.id, answer, reply_markup=week_day_calendar)


@bot.message_handler(func=lambda mess: mess.text == emoji["alarm_clock"],
                     content_types=["text"])
def sending_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    answer = "Здесь ты можешь <b>подписаться</b> на рассылку расписания на " + \
             "следующий день или <b>отписаться</b> от неё.\n" + \
             "Рассылка производится в 21:00"
    sending_keyboard = telebot.types.InlineKeyboardMarkup(True)
    if func.is_sending_on(message.chat.id):
        sending_keyboard.row(
            *[telebot.types.InlineKeyboardButton(text=name,
                                                 callback_data="Отписаться")
              for name in [emoji["cross_mark"] + " Отписаться"]])
    else:
        sending_keyboard.row(
            *[telebot.types.InlineKeyboardButton(text=name,
                                                 callback_data="Подписаться")
              for name in [emoji["check_mark"] + " Подписаться"]])
    bot.send_message(message.chat.id, answer, parse_mode="HTML",
                     reply_markup=sending_keyboard)


@bot.message_handler(func=lambda mess: mess.text.title() == "Сейчас",
                     content_types=["text"])
@bot.message_handler(func=lambda mess: mess.text.capitalize() == "Что сейчас?",
                     content_types=["text"])
def now_lesson_handler(message):
    answer = "Наверно, какая-то пара #пасхалочка"
    func.send_long_message(bot, answer, message.chat.id)


@bot.message_handler(func=lambda mess: func.text_to_date(mess.text.lower()),
                     content_types=["text"])
def schedule_for_day(message):
    bot.send_chat_action(message.chat.id, "typing")
    day = func.text_to_date(message.text.lower())
    json_week = func.get_json_week_data(message.chat.id, for_day=day)
    json_day = func.get_json_day_data(message.chat.id, day_date=day,
                                      json_week_data=json_week)
    full_place = func.is_full_place(message.chat.id)
    answer = func.create_schedule_answer(json_day, full_place,
                                         user_id=message.chat.id,
                                         personal=True)
    func.send_long_message(bot, answer, message.chat.id)


@bot.message_handler(func=lambda mess: mess.text.title() in
                                       week_day_titles.keys(),
                     content_types=["text"])
@bot.message_handler(func=lambda mess: mess.text.title() in
                                       week_day_titles.values(),
                     content_types=["text"])
def schedule_for_weekday(message):
    bot.send_chat_action(message.chat.id, "typing")
    message.text = message.text.title()
    if message.text in week_day_titles.values():
        week_day = message.text
    else:
        week_day = week_day_titles[message.text]
    iso_day_date = list((datetime.today() + server_timedelta).isocalendar())
    if iso_day_date[2] == 7:
        iso_day_date[1] += 1
    iso_day_date[2] = week_day_number[week_day]
    day_date = func.date_from_iso(iso_day_date)
    json_day = func.get_json_day_data(message.chat.id, day_date)
    full_place = func.is_full_place(message.chat.id)
    answer = func.create_schedule_answer(json_day, full_place,
                                         message.chat.id)
    func.send_long_message(bot, answer, message.chat.id)


@bot.message_handler(func=lambda mess: True, content_types=["text"])
def other_text_handler(message):
    bot.send_chat_action(message.chat.id, "typing")
    answer = "Не понимаю"
    func.send_long_message(bot, answer, message.chat.id)


############
# Коллбэки
############

"""

Коллбэки -  методы, которые срабатывают после нажатия на кнопки на клавиатуре.

"""

@bot.callback_query_handler(func=lambda call_back: not func.is_user_exist(call_back.message.chat.id))
def not_exist_user_callback_handler(call_back):
    answer = "Чтобы пользоваться сервисом, необходимо " \
             "зарегистрироваться.\nВоспользуйся коммандой /start"
    bot.edit_message_text(text=answer,
                          chat_id=call_back.message.chat.id,
                          message_id=call_back.message.message_id,
                          parse_mode="HTML")


@bot.callback_query_handler(func=lambda call_back: call_back.data in week_day_number.keys() or
                                                   call_back.data == "Вся неделя")
def select_week_day_schedule_handler(call_back):
    day = ""
    if call_back.data == "Вся неделя":
        day += "Неделя"
    else:
        day += [item[0] for item in week_day_titles.items() if
                item[1] == call_back.data][0]
    answer = "Расписание на: <i>{0}</i>\n".format(day)
    week_type_keyboard = telebot.types.InlineKeyboardMarkup()
    week_type_keyboard.row(
        *[telebot.types.InlineKeyboardButton(text=name, callback_data=name) for
          name in ["Текущее", "Следующее"]]
    )
    bot.edit_message_text(text=answer,
                          chat_id=call_back.message.chat.id,
                          message_id=call_back.message.message_id,
                          parse_mode="HTML",
                          reply_markup=week_type_keyboard)


@bot.callback_query_handler(func=lambda call_back: "Расписание на: Неделя"
                                                   in call_back.message.text)
def all_week_schedule_handler(call_back):
    user_id = call_back.message.chat.id
    bot_msg = bot.edit_message_text(
        text="{0}\U00002026".format(choice(loading_text["schedule"])),
        chat_id=call_back.message.chat.id,
        message_id=call_back.message.message_id
    )
    if call_back.data == "Текущее":
        json_week = func.get_json_week_data(user_id)
    else:
        json_week = func.get_json_week_data(user_id, next_week=True)
    inline_answer = json_week["WeekDisplayText"]
    bot.answer_callback_query(call_back.id, inline_answer, cache_time=1)
    is_smth_send = False
    if len(json_week["Days"]):
        for day in json_week["Days"]:
            full_place = func.is_full_place(call_back.message.chat.id)
            answer = func.create_schedule_answer(day, full_place,
                                                 call_back.message.chat.id)
            if "Выходной" in answer:
                continue
            if json_week["Days"].index(day) == 0 or not is_smth_send:
                try:
                    bot.edit_message_text(text=answer,
                                          chat_id=user_id,
                                          message_id=bot_msg.message_id,
                                          parse_mode="HTML")
                except telebot.apihelper.ApiException:
                    func.send_long_message(bot, answer, user_id)
            else:
                func.send_long_message(bot, answer, user_id)
            is_smth_send = True
    if not is_smth_send or not len(json_week["Days"]):
        answer = "{0} Выходная неделя".format(emoji["sleep"])
        bot.edit_message_text(text=answer,
                              chat_id=user_id,
                              message_id=bot_msg.message_id)


@bot.callback_query_handler(func=lambda call_back: call_back.data == "Текущее" or
                                                   call_back.data == "Следующее")
def week_day_schedule_handler(call_back):
    bot_msg = bot.edit_message_text(
        text="{0}\U00002026".format(choice(loading_text["schedule"])),
        chat_id=call_back.message.chat.id,
        message_id=call_back.message.message_id
    )
    is_next_week = False
    iso_day_date = list((datetime.today() + server_timedelta).isocalendar())
    if iso_day_date[2] == 7:
        iso_day_date[1] += 1
    if call_back.data == "Следующее":
        iso_day_date[1] += 1
        is_next_week = True
    iso_day_date[2] = week_day_number[
        week_day_titles[call_back.message.text.split(": ")[-1]]]
    day_date = func.date_from_iso(iso_day_date)
    json_day = func.get_json_day_data(call_back.message.chat.id, day_date,
                                      next_week=is_next_week)
    full_place = func.is_full_place(call_back.message.chat.id)
    answer = func.create_schedule_answer(json_day, full_place,
                                         call_back.message.chat.id)
    try:
        bot.edit_message_text(text=answer,
                              chat_id=call_back.message.chat.id,
                              message_id=bot_msg.message_id,
                              parse_mode="HTML")
    except telebot.apihelper.ApiException:
        func.send_long_message(bot, answer, call_back.message.chat.id)


@bot.callback_query_handler(func=lambda call_back: call_back.data == "Подписаться")
def sending_on_handler(call_back):
    func.set_sending(call_back.message.chat.id, True)
    answer = "{0} Рассылка <b>активирована</b>\nЖди рассылку в 21:00" \
             "".format(emoji["mailbox_on"])
    bot.edit_message_text(text=answer,
                          chat_id=call_back.message.chat.id,
                          message_id=call_back.message.message_id,
                          parse_mode="HTML")


@bot.callback_query_handler(func=lambda call_back: call_back.data == "Отписаться")
def sending_off_handler(call_back):
    func.set_sending(call_back.message.chat.id, False)
    answer = "{0} Рассылка <b>отключена</b>".format(emoji["mailbox_off"])
    bot.edit_message_text(text=answer,
                          chat_id=call_back.message.chat.id,
                          message_id=call_back.message.message_id,
                          parse_mode="HTML")


@bot.callback_query_handler(func=lambda call_back: call_back.data == "Отмена")
def cancel_handler(call_back):
    answer = "Отмена"
    try:
        bot.edit_message_text(text=answer, chat_id=call_back.message.chat.id,
                              message_id=call_back.message.message_id)
    except telebot.apihelper.ApiException:
        pass


@bot.callback_query_handler(func=lambda call_back: call_back.data == "Сменить группу")
def change_group_handler(call_back):
    answer = "{0}\nДля отмены используй /home".format(call_back.data)
    bot.edit_message_text(text=answer,
                          chat_id=call_back.message.chat.id,
                          message_id=call_back.message.message_id,
                          parse_mode="HTML")
    call_back.message.text = call_back.data
    start_handler(call_back.message)
    return


if __name__ == '__main__':
    from sql_creator import create_sql, copy_from_db
    """
    Создаем базу данных
    """
    create_sql("Bot.db")
    copy_from_db("Bot_db", "Bot.db")

    """
    Запускаем бота и просим начать слушать команды пользователей
    """
    bot.polling(none_stop=True, interval=0)
