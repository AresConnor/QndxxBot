from sqlite3 import Cursor
from . import BaseSqlExcel


class UserDbExcel(BaseSqlExcel):
    def __init__(self, cursor: Cursor):
        super().__init__()
        self.cursor = cursor
        self.header = ['姓名', '学号', 'Laravel_Session', 'Laravel_Session是否可用']

    def close(self):
        pass
