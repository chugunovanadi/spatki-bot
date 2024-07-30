# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import sqlite3

import spbu
import telebot

import functions


"""



В этом скрипте хранятся все методы необходимые для регистрации пользователя в боте.

Мы опрашиваем пользователя пошагово, а значит все время храним этап на котором он в данное время находится.

"""



"""
Записываем в бд на каком конкретном шаге при регистрации находится пользователь сейчас
"""

def set_next_step(user_id, next_step):
    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""UPDATE user_choice
                      SET step = ? 
                      WHERE user_id = ?""",
                   (next_step, user_id))
    sql_con.commit()
    cursor.close()
    sql_con.close()


"""
Получаем этот шаг
"""

def get_step(user_id):
    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT  step
                      FROM user_choice
                      WHERE user_id = ?""", (user_id,))
    step = cursor.fetchone()
    cursor.close()
    sql_con.close()
    if step is None:
        return None
    else:
        return step[0]

"""
Этап 1: Выбор академического направления
"""
def select_division(message):
    from app import bot

    answer = ""

    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT divisions_json 
                      FROM user_choice 
                      WHERE user_id = ?""", (message.chat.id,))
    data = cursor.fetchone()
    cursor.close()
    sql_con.close()

    divisions = json.loads(data[0])
    division_names = [division["Name"].strip() for division in divisions] # собираем названия направлений
    aliases = [division["Alias"].strip() for division in divisions] # Собираем аббревиатуры каждого направления
    if message.text in division_names:  # Если пользователь выбрал направление, то дальше создаем клавиатуру с выбором ступени обучения:
        answer += "Выбери ступень:"
        study_programs_keyboard = telebot.types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=False
        )
        index = division_names.index(message.text)
        alias = aliases[index]
        study_programs = spbu.get_program_levels(alias)

        # Заполняем клавиатуру значениями:
        for study_program in study_programs:
            study_programs_keyboard.row(study_program["StudyLevelName"])
        study_programs_keyboard.row("Другое направление")

        data = json.dumps(study_programs)
        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        # заливаем в бд все выборы, которые сделал пользователь:
        cursor.execute("""UPDATE user_choice 
                          SET alias = ?, division_name = ?, 
                              study_programs_json = ? 
                          WHERE user_id = ?""",
                       (alias, message.text, data, message.chat.id))
        sql_con.commit()
        cursor.close()
        sql_con.close()

        # отправляем сообщение пользователю обратно с новой клавиатурой
        bot.send_message(message.chat.id, answer,
                         reply_markup=study_programs_keyboard)
        set_next_step(message.chat.id, "select_study_level") # переводим пользователя на следующий этап
    else:
        answer += "Пожалуйста, укажи направление:"
        bot.send_message(message.chat.id, answer)
        set_next_step(message.chat.id, "select_division")


"""
Всё по аналогии, как и выше, но только теперь просим пользователя выбрать академическую ступень(бакалавр/магистр/и т.п.)
"""

def select_study_level(message):
    from app import bot, start_handler

    answer = ""

    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT study_programs_json 
                      FROM user_choice 
                      WHERE user_id = ?""", (message.chat.id,))
    data = cursor.fetchone()[0]
    cursor.close()
    sql_con.close()

    study_programs = json.loads(data)

    study_level_names = []
    for study_program in study_programs:
        study_level_names.append(study_program["StudyLevelName"].strip())
    if message.text in study_level_names:
        answer += "Укажи программу:"
        study_program_combinations_keyboard = telebot.types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=False
        )
        index = study_level_names.index(message.text)
        study_program_combinations = study_programs[index][
            "StudyProgramCombinations"]
        for study_program_combination in study_program_combinations:
            study_program_combinations_keyboard.row(
                study_program_combination["Name"])
        study_program_combinations_keyboard.row("Другая ступень")

        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""UPDATE user_choice 
                          SET study_level_name = ?
                          WHERE user_id = ?""",
                       (message.text, message.chat.id))
        sql_con.commit()
        cursor.close()
        sql_con.close()

        bot.send_message(message.chat.id, answer,
                         reply_markup=study_program_combinations_keyboard)
        set_next_step(message.chat.id, "select_study_program_combination")
    elif message.text == "Другое направление":
        start_handler(message)
        return
    else:
        answer += "Пожалуйста, укажи ступень:"
        bot.send_message(message.chat.id, answer)
        set_next_step(message.chat.id, "select_study_level")


"""
Теперь то же самое, но с выбором программы обучения
"""


def select_study_program_combination(message):
    from app import bot

    answer = ""

    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT study_level_name, study_programs_json 
                      FROM user_choice 
                      WHERE user_id = ?""", (message.chat.id,))
    data = cursor.fetchone()
    cursor.close()
    sql_con.close()

    study_level_name, study_programs = data[0], json.loads(data[1])
    study_level_names = []
    for study_program in study_programs:
        study_level_names.append(study_program["StudyLevelName"])
    index = study_level_names.index(study_level_name)
    study_program_combinations = study_programs[index][
        "StudyProgramCombinations"]
    study_program_combination_names = []
    for study_program_combination in study_program_combinations:
        study_program_combination_names.append(
            study_program_combination["Name"].strip())
    if message.text in study_program_combination_names:
        answer += "Укажи год поступления:"
        admission_years_keyboard = telebot.types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=False
        )
        index = study_program_combination_names.index(message.text)
        admission_years = study_program_combinations[index]["AdmissionYears"]
        for admission_year in admission_years:
            admission_years_keyboard.row(admission_year["YearName"])
        admission_years_keyboard.row("Другая программа")

        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""UPDATE user_choice
                          SET study_program_combination_name = ? 
                          WHERE user_id = ?""",
                       (message.text, message.chat.id))
        sql_con.commit()
        cursor.close()
        sql_con.close()

        bot.send_message(message.chat.id, answer,
                         reply_markup=admission_years_keyboard)
        set_next_step(message.chat.id, "select_admission_year")
    elif message.text == "Другая ступень":
        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""SELECT division_name 
                          FROM user_choice 
                          WHERE user_id = ?""", (message.chat.id,))
        data = cursor.fetchone()
        cursor.close()
        sql_con.close()

        message.text = data[0]
        select_division(message)
        return
    else:
        answer += "Пожалуйста, укажи программу:"
        bot.send_message(message.chat.id, answer)
        set_next_step(message.chat.id, "select_study_program_combination")


"""
Выбор года поступления
"""

def select_admission_year(message):
    from app import bot

    answer = ""

    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT study_programs_json, study_level_name, 
                             study_program_combination_name
                      FROM user_choice 
                      WHERE user_id = ?""", (message.chat.id,))
    data = cursor.fetchone()
    cursor.close()
    sql_con.close()

    study_programs = json.loads(data[0])
    study_level_name = data[1]
    study_program_combination_name = data[2]
    study_level_names = []
    for study_program in study_programs:
        study_level_names.append(study_program["StudyLevelName"])
    index = study_level_names.index(study_level_name)
    study_program_combinations = study_programs[index][
        "StudyProgramCombinations"]
    study_program_combination_names = []
    for study_program_combination in study_program_combinations:
        study_program_combination_names.append(
            study_program_combination["Name"])
    index = study_program_combination_names.index(
        study_program_combination_name)
    admission_years = study_program_combinations[index]["AdmissionYears"]
    admission_year_names = []
    for admission_year in admission_years:
        admission_year_names.append(admission_year["YearName"].strip())
    if message.text in admission_year_names:
        answer += "Укажи группу:"
        index = admission_year_names.index(message.text)
        study_program_id = admission_years[index]["StudyProgramId"]
        student_groups = spbu.get_groups(study_program_id)
        student_group_names = []
        for student_group in student_groups["Groups"]:
            student_group_names.append(student_group["StudentGroupName"])
        student_groups_keyboard = telebot.types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=False
        )
        for student_group_name in student_group_names:
            student_groups_keyboard.row(student_group_name)
        student_groups_keyboard.row("Другой год")
        data = json.dumps(student_groups)

        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""UPDATE user_choice 
                          SET admission_year_name = ?, 
                              student_groups_json = ? 
                          WHERE user_id = ?""",
                       (message.text, data, message.chat.id))
        sql_con.commit()
        cursor.close()
        sql_con.close()

        bot.send_message(message.chat.id, answer,
                         reply_markup=student_groups_keyboard)
        set_next_step(message.chat.id, "select_student_group")
    elif message.text == "Другая программа":
        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""SELECT study_level_name
                          FROM user_choice 
                          WHERE user_id = ?""", (message.chat.id,))
        data = cursor.fetchone()
        cursor.close()
        sql_con.close()

        message.text = data[0]
        select_study_level(message)
        return
    else:
        answer += "Пожалуйста, укажи год:"
        bot.send_message(message.chat.id, answer)
        set_next_step(message.chat.id, "select_admission_year")


"""
Выбор конкретной группы
"""

def select_student_group(message):
    from app import bot

    answer = ""

    sql_con = sqlite3.connect("Bot.db")
    cursor = sql_con.cursor()
    cursor.execute("""SELECT student_groups_json
                      FROM user_choice 
                      WHERE user_id = ?""", (message.chat.id,))
    data = cursor.fetchone()[0]
    cursor.close()
    sql_con.close()

    student_groups = json.loads(data)
    student_group_names = []
    for student_group in student_groups["Groups"]:
        student_group_names.append(student_group["StudentGroupName"].strip())
    if message.text in student_group_names:
        index = student_group_names.index(message.text)
        student_group_id = student_groups["Groups"][index]["StudentGroupId"]

        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""UPDATE user_choice 
                          SET student_group_name = ?, 
                              student_group_id = ? 
                          WHERE user_id = ?""",
                       (message.text, student_group_id, message.chat.id))
        sql_con.commit()
        cursor.execute("""SELECT division_name, study_level_name, 
                                 study_program_combination_name,
                                 admission_year_name, student_group_name 
                          FROM user_choice 
                          WHERE user_id = ?""", (message.chat.id,))
        data = cursor.fetchone()
        cursor.close()
        sql_con.close()

        text = ">> " + "\n>> ".join(data)
        answer += "Подтверди выбор:\n" + "<b>" + text + "</b>"
        choice_keyboard = telebot.types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=False
        )
        buttons = ["Все верно", "Другая группа", "Другой год",
                   "Другая программа", "Другая ступень", "Другое направление"]
        for button in buttons:
            choice_keyboard.row(button)
        bot.send_message(message.chat.id, answer, parse_mode="HTML",
                         reply_markup=choice_keyboard)
        set_next_step(message.chat.id, "confirm_choice")
    elif message.text == "Другой год":
        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""SELECT study_program_combination_name
                          FROM user_choice 
                          WHERE user_id = ?""", (message.chat.id,))
        data = cursor.fetchone()
        cursor.close()
        sql_con.close()

        message.text = data[0]
        select_study_program_combination(message)
        return
    else:
        answer += "Пожалуйста, укажи группу:"
        bot.send_message(message.chat.id, answer)
        set_next_step(message.chat.id, "select_student_group")


"""
Последний этап. Подтверждаем всё, что выбрал пользователь при регистрации. 
Если "Всё верно", то записываем в бд, если что-то захочет поменять, то адресуем его к одному из методов описаных выше
"""


def confirm_choice(message):
    from app import bot, start_handler, main_keyboard
    from constants import emoji

    if message.text == "Все верно":
        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""SELECT student_group_id
                          FROM user_choice 
                          WHERE user_id = ?""", (message.chat.id,))
        group_id = cursor.fetchone()[0]
        user_id = message.chat.id

        cursor.close()
        sql_con.close()

        functions.add_new_user(user_id, group_id)

        answer = "Главное меню\n\n" \
                 "{0} - информация о боте\n" \
                 "{1} - настройки\n" \
                 "".format(emoji["info"], emoji["settings"])

        bot.send_message(message.chat.id, answer, reply_markup=main_keyboard,
                         parse_mode="HTML")
    elif message.text == "Другая группа":
        sql_con = sqlite3.connect("Bot.db")
        cursor = sql_con.cursor()
        cursor.execute("""SELECT admission_year_name
                          FROM user_choice 
                          WHERE user_id = ?""", (message.chat.id,))
        data = cursor.fetchone()
        cursor.close()
        sql_con.close()

        message.text = data[0]
        select_admission_year(message)
        return
    elif message.text == "Другой год":
        select_student_group(message)
        return
    elif message.text == "Другая программа":
        select_admission_year(message)
        return
    elif message.text == "Другая ступень":
        select_study_program_combination(message)
        return
    elif message.text == "Другое направление":
        start_handler(message)
        return
