"""Loads MySQL database schema via information_schema."""

from urllib.parse import quote_plus

import pymysql

from askdata.core.errors import DataError
from askdata.schemas.bird import BirdColumn, BirdDatabase, BirdTable


class MySQLLoader:
    """Loads MySQL schema and sample questions into normalized objects."""

    def __init__(self, host, port, user, password, database):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def LoadSchema(self):
        """Loads all tables and columns from MySQL and returns BirdDatabase."""
        conn = self._Connect()
        try:
            tables = self._LoadTables(conn)
            foreignKeys = self._LoadForeignKeys(conn)
            primaryKeys = [{"tableName": col.tableName, "columnName": col.columnName}
                          for table in tables for col in table.columns if col.isPrimary]
            return BirdDatabase(
                databaseId=self.database,
                databasePath=f"mysql+pymysql://{self.user}:{quote_plus(self.password)}@{self.host}:{self.port}/{self.database}",
                tables=tables,
                primaryKeys=primaryKeys,
                foreignKeys=foreignKeys,
            )
        finally:
            conn.close()

    def _Connect(self):
        try:
            return pymysql.connect(
                host=self.host, port=self.port, user=self.user,
                password=self.password, database=self.database, charset="utf8mb4",
            )
        except Exception as e:
            raise DataError(f"Failed to connect to MySQL: {e}") from e

    def _LoadTables(self, conn):
        cursor = conn.cursor()
        cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME", (self.database,))
        tableNames = [row[0] for row in cursor.fetchall()]
        tables = []
        for name in tableNames:
            columns = self._LoadColumns(conn, name)
            tables.append(BirdTable(tableName=name, columns=columns))
        return tables

    def _LoadColumns(self, conn, tableName):
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_KEY FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
            (self.database, tableName),
        )
        return [BirdColumn(tableName=tableName, columnName=row[0], columnType=row[1] or "text", isPrimary=(row[2] == "PRI")) for row in cursor.fetchall()]

    def _LoadForeignKeys(self, conn):
        cursor = conn.cursor()
        cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL",
            (self.database,),
        )
        keys = []
        for row in cursor.fetchall():
            keys.append({"leftTable": row[0], "leftColumn": row[1], "rightTable": row[2], "rightColumn": row[3]})
        return keys
