# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sqlite3
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler

import telebot

from bots_constants import bot_token
from functions import get_json_day_data, create_schedule_answer, \
    is_full_place, send_long_message


"""


Метод для отправки уведомлений с раписанием пользователям бота. 

Логика: 
1. Собираем ID'шники пользователей, которые подписались на рассылку и пробегаемся по каждому:
    2. Получаем инфу о наличии пар на следующий день
    3. Если пары есть, то создаем сообщение с расписанием
    4. Отправляем  

"""

def schedule_sender():
    bot = telebot.TeleBot(bot_token)
    db_path = "Bot.db"
    sql_con = sqlite3.connect(db_path)
    cursor = sql_con.cursor()
    cursor.execute("""SELECT id
                      FROM user_data
                      WHERE sending = 1""")
    data = cursor.fetchall()
    cursor.close()
    sql_con.close()

    tomorrow_moscow_datetime = datetime.today() + timedelta(days=1, hours=3)
    tomorrow_moscow_date = tomorrow_moscow_datetime.date()
    for user_data in data:
        user_id = user_data[0]
        json_day = get_json_day_data(user_id, tomorrow_moscow_date)
        full_place = is_full_place(user_id, db_path=db_path)
        answer = create_schedule_answer(json_day, full_place, user_id,
                                        db_path=db_path)
        if "Выходной" in answer:
            continue
        print(user_id, answer)
        try:
            answer = "Расписание на завтра:\n\n" + answer
            send_long_message(bot, answer, user_id)
        except Exception as err:
            print(err)
            continue


if __name__ == '__main__':
    """
    1 раз запускаем метод для отправки расписаний пользователям
    """
    schedule_sender()

    """
    Теперь активируем постоянную отправку с заданной частотой(на пятой секунде раз в минуту отправка)
    """
    scheduler = BlockingScheduler()
    scheduler.add_job(schedule_sender, 'cron', minute='*', second=5)
    # запускаем постоянную отправку:
    scheduler.start()
