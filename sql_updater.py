#!/home/user_name/myvenv/bin/python3.6
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import sqlite3

import requests

"""
Скрипт для обновления базы данных. Сначала удаляет всю информацию, 
потом запрашивает её с официального сайта и заполняет базу снова.

"""


# В качестве параметра передается путь до базы данных с названием базы.
def schedule_update(db_path="Bot.db"):
    sql_con = sqlite3.connect(db_path)  # Устанавливается соединение с базой
    cursor = sql_con.cursor()
    cursor.execute("""DELETE
                      FROM groups_data
                      WHERE id in (
                        SELECT
                          groups_data.id
                        FROM groups_data
                          LEFT OUTER JOIN user_data
                            ON groups_data.id = user_data.group_id
                          LEFT OUTER JOIN user_groups
                            ON groups_data.id = user_groups.group_id
                        WHERE user_data.id ISNULL
                          AND user_groups.group_id ISNULL
                      )""")  # Исполняется запрос к базе на удаление информации
    sql_con.commit()  # Подтверждение выполненного запроса
    cursor.execute("""SELECT id FROM groups_data""")  # Берем idшники всех групп
    groups = cursor.fetchall()
    for group in groups:  # Проходим по каждой группе
        group_id = group[0]
        url = "https://timetable.spbu.ru/api/v1/groups/{0}/events".format(
            group_id)
        res = requests.get(url)  # Отправляем запрос к офф сайту на получение информации о группе
        if res.status_code != 200:  # Если запрос не удался, то выбрасываем ошибку
            print("ERROR:", group_id, res.json())
            continue    # пропускаем текущую группу в случае ошибки
        json_week_data = res.json() # Если ошибки не было, то получаем результат запроса к сайту
        data = json.dumps(json_week_data)   # Переводим информацию из json-формата и складываем в 'data'
        cursor.execute("""UPDATE groups_data
                          SET json_week_data = ?
                          WHERE id = ?""",
                       (data, group_id))    # Добавляем в базу информацию
        sql_con.commit()    # Подтверждаем операцию добавления
        print(group_id)
    cursor.close()
    sql_con.close() #   Закрываем соединение


if __name__ == '__main__':
    schedule_update()   # Если скрипт sql_updater.py запускается как самостоятельный, то вызывается этот метод
