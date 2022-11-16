from sqlite3 import Cursor

from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from .UserDbExcel import UserDbExcel


class UnavailableEntryExcel(UserDbExcel):
    def __init__(self, cursor: Cursor):
        super().__init__(cursor)
        self.header = ['班级', '姓名', '学号', 'Laravel_Session', 'Laravel_Session状态']
        self.sheet_name = '失效名单'
        self.sql_constraint = f" where SESSION_AVAILABLE = false"

    def _data_to_workbook(self):
        """
        :return: class Workbook
        """
        if self.excel_dict == {}:
            return None
        wb = Workbook()
        header = {i + 1: self.header[i] for i in range(len(self.header))}
        ws: Worksheet = wb.create_sheet(title=self.sheet_name)
        # 写入表头
        ws.append(header)
        for class_name, rows in self.excel_dict.items():
            # 写入数据
            for row in rows:
                row_data = {1: class_name}
                row_data.update({i + 2: row[i] for i in range(len(row) - 1)})
                row_data.update({len(row) + 1: '不可用'})
                ws.append(row_data)
        wb.remove_sheet(wb.get_sheet_by_name('Sheet'))
        return wb
