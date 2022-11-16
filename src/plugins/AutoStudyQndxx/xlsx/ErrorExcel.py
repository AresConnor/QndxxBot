import sqlite3
from sqlite3 import Cursor
from . import BaseSqlExcel


class ErrorExcel(BaseSqlExcel):
    def __init__(self, error_dict: dict):
        super().__init__()
        self.error_dict = error_dict
        self.sql_conn = sqlite3.connect(':memory:')
        self.cursor: Cursor = self.sql_conn.cursor()
        self.header = ['学号', '姓名(数据库)', '姓名(服务器返回)', 'laravel_session(数据库)', 'laravel_session(新)',
                       '学习失败原因']

        for class_name, failed in error_dict.items():
            self.cursor.execute(f"create table '{class_name}'("
                                f"stu_id int primary key not null ,"
                                f"name_in_db text not null ,"
                                f"name_returned text ,"
                                f"old_token text not null ,"
                                f"new_token text,"
                                f"reason text not null "
                                f");")
            for e in failed:
                self.cursor.execute(f"insert into '{class_name}' values ("
                                    f"{e['stu_id']},"
                                    f"'{e['name_in_db']}',"
                                    f"'{e['name_returned']}',"
                                    f"'{e['old_token']}',"
                                    f"'{e['new_token']}',"
                                    f"'{e['reason']}'"
                                    f");")
        self.sql_conn.commit()

    def close(self):
        self.cursor.close()
        self.sql_conn.close()
