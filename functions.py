# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import sqlite3
from datetime import datetime, date, timedelta

import spbu
from telebot.apihelper import ApiException

from constants import emoji, subject_short_type, months, server_timedelta



# Добавление нового пользователя
def add_new_user(user_id, group_id, group_title=None):
    sql_con = sqlite3.connect("Bot.db")  # установка соединения с БД
    cursor = sql_con.cursor()
    if group_title is None:  # Ищем название группы
        group_title = spbu.get_group_events(group_id)[
                          "StudentGroupDisplayName"][7:]
    try:
        cursor.execute("""INSERT INTO groups_data 
                          (id, title)
                          VALUES (?, ?)""",
                       (group_id, group_title))  # Добавляем группу
    except sqlite3.IntegrityError:
        sql_con.rollback()  # В случае ошибки - откатываем сделанные изменения в бд
    finally:
        json_week = json.dumps(spbu.get_group_events(group_id))  # собираем инфу о группе за целую неделю
        cursor.execute("""UPDATE groups_data
                          SET json_week_data = ?
                          WHERE id = ?""",
                       (json_week, group_id))  # Исполняем запрос к бд
        sql_con.commit()  # подтверждаем выполненный запрос
    try:
        cursor.execute("""INSERT INTO user_data (id, group_id)
                          VALUES (?, ?)""",
                       (user_id, group_id))  # Получаем из бд инфу о пользователе по его id и id его группы
    except sqlite3.IntegrityError:
        sql_con.rollback()
        cursor.execute("""UPDATE user_data 
                          SET group_id = ?
                          WHERE id = ?""",
                       (group_id, user_id))
    finally:
        sql_con.commit()
        cursor.execute("""DELETE FROM user_choice WHERE user_id = ?""",
                       (user_id,))
        sql_con.commit()
        cursor.close()
        sql_con.close()


"""
Запрос на удаление пользователя из БД
"""


def delete_user(user_id, only_choice=False):
    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""DELETE FROM user_choice 
                      WHERE user_id = ?""", (user_id,))  # Удаление того, что пользователь выбирал при регистрации
    sql_con.commit()
    if not only_choice:  # если нужно удалить полностью всю инфу. Сработает, если параметр 'only_choice' равен True
        cursor.execute("""DELETE FROM user_groups 
                          WHERE user_id = ?""", (user_id,))
        sql_con.commit()
        cursor.execute("""DELETE FROM user_data 
                          WHERE id = ?""", (user_id,))
        sql_con.commit()
    cursor.close()
    sql_con.close()


"""
Конвертация переданной даты в читабельный вид
"""


def date_from_iso(iso):
    return datetime.strptime("%d%02d%d" % (iso[0], iso[1], iso[2]),
                             "%Y%W%w").date()


"""
Получение текущего календарного понедельника
"""


def get_current_monday_date():
    iso_day_date = list((date.today() + server_timedelta).isocalendar())
    if iso_day_date[2] == 7:
        iso_day_date[1] += 1
    iso_day_date[2] = 1
    monday_date = date_from_iso(iso_day_date)
    return monday_date


"""
Получение информации из бд о событиях на неделе конкретного пользователя
"""


def get_json_week_data(user_id, next_week=False, for_day=None):
    if next_week:
        return get_json_week_data_api(user_id,
                                      next_week=next_week)  # если нужна инфа за следующую неделю, то обращаемся к следующему методу
    if for_day:
        return get_json_week_data_api(user_id, for_day=for_day)  # то же самое, но за если нужна инфа за конкретный день
    else:
        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""SELECT json_week_data
                          FROM groups_data
                            JOIN user_data
                              ON groups_data.id = user_data.group_id
                          WHERE  user_data.id= ?""", (user_id,))
        data = cursor.fetchone()

        json_week_data = json.loads(data[0])
        cursor.close()
        sql_con.close()

    return delete_symbols(json_week_data)  # возвращаем полученную информацию, удалив лишние символы

"""
Получение информации о событиях на неделе для конкретного пользователя, но уже с оф сайта. 
"""

def get_json_week_data_api(user_id, next_week=False, for_day=None):
    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT group_id
                      FROM user_data 
                      WHERE  id= ?""", (user_id,))
    group_id = cursor.fetchone()[0]
    cursor.close()
    sql_con.close()

    if for_day:
        monday_date = for_day
    elif next_week:
        monday_date = get_current_monday_date()
        monday_date += timedelta(days=7)
    else:
        monday_date = get_current_monday_date()

    json_week_data = spbu.get_group_events(group_id=group_id,
                                           from_date=monday_date) # обращение к методу получения инфы с оф сайта
    return delete_symbols(json_week_data)


"""
Метод для удаления лишних символов
"""

def delete_symbols(json_obj):
    return json.loads(
        json.dumps(json_obj).replace("<", "").replace(">", "").replace("&", "")
    )


"""
Получение информации о событиях на заданный день  
"""

def get_json_day_data(user_id, day_date, json_week_data=None, next_week=False):
    if json_week_data is None:
        json_week_data = get_json_week_data(user_id, next_week)
    for day_info in json_week_data["Days"]:
        if datetime.strptime(day_info["Day"],
                             "%Y-%m-%dT%H:%M:%S").date() == day_date:
            return day_info
    return None

"""
Метод для создания сообщения с расписанием
"""
def create_schedule_answer(day_info, full_place, user_id=None, personal=True,
                           db_path="Bot.db", only_exams=False):
    if day_info is None:
        return emoji["sleep"] + " Выходной"  # Если инфы о заданном дне нет, значит это выходной


    # В переменную 'answer' складывается весь ответ поэтапно:
    answer = emoji["calendar"] + " "
    answer += day_info["DayString"].capitalize() + "\n\n"
    day_study_events = day_info["DayStudyEvents"]

    for event in day_study_events: # пробегаемся по событиям за день
        if event["IsCancelled"] or \
                (only_exams and "пересдача" in event["Subject"]) or \
                (only_exams and "консультация" in event["Subject"]) or \
                (only_exams and "комиссия" in event["Subject"]):
            continue  # Если событие попадает под критерии выше, то пропускаем этот день, не добавляя его в сообщение
        if event["IsAssigned"]:
            answer += emoji["new"] + " "
        answer += emoji["clock"] + " " + event["TimeIntervalString"]
        if event["TimeWasChanged"]:
            answer += " " + emoji["warning"]
        answer += "\n<b>"
        subject_name = ", ".join(event["Subject"].split(", ")[:-1])
        subject_type = event["Subject"].split(", ")[-1]
        stripped_subject_type = " ".join(subject_type.split()[:2])
        if stripped_subject_type in subject_short_type.keys():
            answer += subject_short_type[stripped_subject_type] + " - "
        else:
            answer += subject_type.upper() + " - "
        answer += subject_name + "</b>\n"
        # На этом месте мы уже собрали инфу о занятии, теперь собираем инфу о местоположении занятия:
        for location in event["EventLocations"]:
            if location["IsEmpty"]:
                continue
            if full_place:
                location_name = location["DisplayName"].strip(", ").strip()
            else:
                location_name = location["DisplayName"].split(", ")[-1].strip()
            answer += location_name
            if location["HasEducators"]:
                educators = [educator["Item2"].split(", ")[0] for educator in
                             location["EducatorIds"]]
                if len(educators):
                    answer += " <i>({0})</i>".format("; ".join(educators))
            if event["LocationsWereChanged"] or \
                    event["EducatorsWereReassigned"]:
                answer += " " + emoji["warning"]
            answer += "\n"
        answer += "\n"

    if len(answer.strip().split("\n\n")) == 1:  # Если в итоге ничего не добавили в 'answer', значит в этот день выходной
        return emoji["sleep"] + " Выходной"

    return answer


"""
Метод для проверки существования пользователя в нашей БД
"""

def is_user_exist(user_id):
    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT count(id) 
                      FROM user_data
                      WHERE id = ?""", (user_id,))
    data = cursor.fetchone()
    cursor.close()
    sql_con.close()
    return data[0]


"""
Метод для проверки на наличие подписки на уведомления с расписанием
"""

def is_sending_on(user_id):
    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT sending 
                      FROM user_data
                      WHERE id = ?""", (user_id,))
    data = cursor.fetchone()
    cursor.close()
    sql_con.close()
    return data[0]


"""
Метод для подписывания пользователя на уведомления с расписанием
"""

def set_sending(user_id, on=True):
    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""UPDATE user_data
                      SET sending = ?
                      WHERE id = ?""",
                   (int(on), user_id))
    sql_con.commit()
    cursor.close()
    sql_con.close()


"""
Метод для проверки "попросил ли пользователь показывать ему полный адрес места проведения занятия"
"""

def is_full_place(user_id, db_path="Bot.db"):
    sql_con = sqlite3.connect(db_path)
    cursor = sql_con.cursor()
    cursor.execute("""SELECT full_place 
                      FROM user_data
                      WHERE id = ?""", (user_id,))
    data = cursor.fetchone()
    cursor.close()
    sql_con.close()
    return data[0]


"""
Если сообщение большое, то этот метод разобьет его на части и отправит по очереди
"""

def send_long_message(bot, text, user_id, split="\n\n"):
    try:
        bot.send_message(user_id, text, parse_mode="HTML")
    except ApiException as ApiExcept: # Вот тут отлавливаем сообщение об ошибке типа "сообщение слишком длинное"
        json_err = json.loads(ApiExcept.result.text)
        if json_err["description"] == "Bad Request: message is too long":
            event_count = len(text.split(split)) # Делим сообщение на части и потом отправляем по очереди:
            first_part = split.join(text.split(split)[:event_count // 2])
            second_part = split.join(text.split(split)[event_count // 2:])
            send_long_message(bot, first_part, user_id, split)
            send_long_message(bot, second_part, user_id, split)


"""
Приводим текстовое значение даты в объект даты
"""


def text_to_date(text):
    text = text.replace(".", " ")
    if text.replace(" ", "").isalnum():
        words = text.split()[:3]
        for word in words:
            if not (
                    word.isdecimal() or (
                    word.isalpha() and (word.lower() in months.keys())
            )
            ):
                return False
        try:
            day = int(words[0])
            month = datetime.today().month
            year = datetime.today().year
            if len(words) > 1:
                month = int(words[1]) if words[1].isdecimal() else months[
                    words[1]]
                if len(words) > 2:
                    year = int(words[2])
            return datetime.today().replace(day=day, month=month,
                                            year=year).date()
        except ValueError:
            return False
    return False
