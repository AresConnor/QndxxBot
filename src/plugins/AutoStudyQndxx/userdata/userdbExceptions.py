class DbTableMissing(Exception):
    def __init__(self, tableName):
        self.missingTableName = tableName
        super(tableName)
