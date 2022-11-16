import logging

from nonebot.log import LoguruHandler

admin_list = ['2837434884']
class_name_list = []
# 团支部群 891844703
# 测试群 566893040
gid_allowed = [891844703, 566893040]
gid_default = 891844703
auto_fresh_job_name = '青年大学习自动刷新任务'
helper_checker_job_name = '每周青年大学习帮扶检查'

DATABASE_NAME = 'qndxx_user.db'

DATA_DIR = './data/AutoStudyQndxx/'
ERROR_XLSX_FN = '失败名单.xlsx'
USER_DB_EXCEL_FN = '总名单.xlsx'
UNAVAILABLE_IN_DB_EXCEL_FN = '失效名单.xlsx'
CONFIG_FN = 'config.json'
HELP_IMAGE_FN = 'help.png'

DEFAULT_CONFIG = {
    '白名单班级名称列表': [],
    '是否启用班级白名单': False
}


def init_logger():
    aps_logger = logging.getLogger("青年大学习自动学习插件")
    aps_logger.setLevel(30)
    aps_logger.handlers.clear()
    aps_logger.addHandler(LoguruHandler())
