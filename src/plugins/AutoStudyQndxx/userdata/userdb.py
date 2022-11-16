import sqlite3
from sqlite3 import Cursor
from typing import Type

from nonebot.internal.matcher import Matcher
from nonebot.log import logger

from ..utils import DATABASE_NAME, DATA_DIR
from .userdbExceptions import DbTableMissing


def get_all_tables(cursor: Cursor):
    return [e[0] for e in cursor.execute('select name from sqlite_master where type="table";').fetchall()]


def get_all_rows(cursor: Cursor, constraint=""):
    rows = []
    for t in get_all_tables(cursor):
        rows.extend(cursor.execute(f"select * from '{t}'" + constraint + ";").fetchall())
    return rows


class UserDB:
    def __init__(self):
        self.dbConnection = sqlite3.Connection(DATA_DIR + DATABASE_NAME)
        self.dbCursor = self.dbConnection.cursor()
        logger.info('初始化数据库')
        self.exception = None
        self.refreshing = False
        self.column = {
            'NAME': str,
            'ID': int,
            'SESSION': str,
            'SESSION_AVAILABLE': bool
        }
        self.primary_key = 'ID'

    def create_table(self, tableName):
        if tableName in get_all_tables(self.dbCursor):
            return
        sql = f"CREATE TABLE '{tableName}'(" \
              f"NAME TEXT  NOT NULL ," \
              f"ID INT PRIMARY KEY NOT NULL ," \
              f"SESSION TEXT NOT NULL ," \
              f"SESSION_AVAILABLE BOOLEAN NOT NULL" \
              f");"
        self.dbCursor.execute(sql)

    def get_token(self, tableName):
        """
        :param tableName:
        :return: {
            学号:{
                name
                token
            },
            ...
        }
        """
        if tableName not in get_all_tables(cursor=self.dbCursor):
            raise DbTableMissing(tableName)
        tableContent = self.dbCursor.execute(f"SELECT * FROM '{tableName}';").fetchall()
        tableDict = {}
        for entry in tableContent:
            tableDict.update({
                entry[1]: {
                    'name': entry[0],
                    'token': entry[2],
                }
            })
        return tableDict

    async def add_user(self, tableName, name, stu_id, token, setting: dict, matcher: Type[Matcher]):
        if setting['是否启用班级白名单'] and tableName not in setting['班级名称列表']:
            logger.warning(tableName, '不在白名单中')
            return False
        elif tableName not in get_all_tables(self.dbCursor):
            logger.success(f'检测到表 {tableName} 不存在,已新建表')
            self.create_table(tableName)
        try:
            self.dbCursor.execute(f"insert into '{tableName}' values ('{name}',{stu_id},'{token}',true);")
            self.dbConnection.commit()
            return True
        except sqlite3.IntegrityError as e:
            self.exception = e
            logger.warning(f'表{tableName},{stu_id}已存在')
            await matcher.send('该条目已存在')
            return False
        except Exception as e:
            self.exception = e
            logger.exception('添加失败', tableName, name, stu_id, token)
            print(e)
            await matcher.send(f'添加失败, {tableName}, {name}, {stu_id}, {token}')
            return False

    async def remove_user(self, stu_id, matcher: Type[Matcher]):
        tables = get_all_tables(self.dbCursor)
        rows = get_all_rows(self.dbCursor)
        if stu_id not in {r[1] for r in rows}:
            logger.warning(f'学号{stu_id}不在数据库中')
            await matcher.send(f'学号{stu_id}不在数据库中')
            return False
        for t in tables:
            try:
                self.dbCursor.execute(f"delete from '{t}' where ID={stu_id};")
                self.dbConnection.commit()
            except Exception as e:
                self.exception = e
                logger.warning('删除错误!')
                await matcher.send(f'删除错误')
                return False
        await matcher.send('删除成功')
        return True

    def search_by_id(self, column, stu_id):
        """

        :param column:
        :param stu_id:
        :return: <索引值>,<表名> | None
        """
        for t in get_all_tables(self.dbCursor):
            rlt = self.dbCursor.execute(f"select {column} from '{t}' where ID = {stu_id};").fetchall()
            if not rlt:
                continue
            else:
                return rlt[0][0], t
        return None

    def update_user_token(self, tableName, stu_id, newToken):
        try:
            self.dbCursor.execute(
                f"update '{tableName}' set SESSION = '{newToken}',SESSION_AVAILABLE = true where ID = {stu_id};")
            self.dbConnection.commit()
        except Exception as e:
            self.exception = e
            logger.exception('更新token失败', tableName, stu_id, newToken)
            print(e)

    def change_token_availability(self, tableName, stu_id, token_availability: bool):
        try:
            self.dbCursor.execute(
                f"update '{tableName}' set SESSION_AVAILABLE = {token_availability} where ID = {stu_id};")
            self.dbConnection.commit()
        except Exception as e:
            self.exception = e
            logger.exception('更新token可用性失败', tableName, stu_id, token_availability)
            print(e)

    def set_value(self, column, stuid, newValue):
        r = self.search_by_id(column, stuid)
        if r is not None:
            rlt, table = r
            try:
                self.dbCursor.execute(
                    f"update '{table}' set '{column}' = {newValue} where ID = {stuid};")
            except Exception as e:
                self.exception = e
                logger.exception('设置值失败', column, stuid, newValue)
                print(e)
                return False
        else:
            self.exception = None
            return False
        return True

    def close(self):
        self.dbCursor.close()
        self.dbConnection.close()

    def __del__(self):
        self.close()
