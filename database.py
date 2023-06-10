import sqlite3
import typing

class WorkspaceData:
    def __init__(self):
        self.conn = sqlite3.connect("database.db")
        # this makes your database a python list of Row objects that you can access in a similar fashion to dicts
        self.conn.row_factory = sqlite3.Row
        # the cursor is the object that actually makes the queries to the database
        self.cursor = self.conn.cursor()

        self.cursor.execute('CREATE TABLE IF NOT EXISTS watchlist (symbol TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS strategies (strategy_type TEXT, asset TEXT, timeframe TEXT, '
                            'balance_pct REAL, take_profit REAL, stop_loss REAL, extra_params TEXT)')

        self.conn.commit()

    def save(self, table: str, data: typing.List[typing.Tuple]):
        self.cursor.execute(f'DELETE FROM {table}')

        table_data = self.cursor.execute(f'SELECT * FROM {table}')

        columns = [description[0] for description in table_data.description]

        sql_statement = f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({", ".join(["?"] * len(columns))})'
        self.cursor.executemany(sql_statement, data)

        self.conn.commit()

    # Remember these sqlite3.Row objects can be accessed similar to python dicts
    def get(self, table: str) -> typing.List[sqlite3.Row]:
        self.cursor.execute(f'SELECT * FROM {table}')
        data = self.cursor.fetchall()
        return data
