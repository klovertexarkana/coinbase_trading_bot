from models import *
from database import *


class Watchlist:
    def __init__(self, assets: typing.Dict[str, Asset]):

        self.symbols = list(assets.keys())
        self.assets_to_watch = []

        self.db = WorkspaceData()
        saved_symbols = self.db.get('watchlist')

        for symbol in saved_symbols:
            self.add_symbol(symbol['symbol'])

    def add_symbol(self, symbol: str):
        """Takes asset symbols and adds to the assets_to_watch list which gets price updates logged to the terminal."""
        if symbol in self.symbols:
            self.assets_to_watch.append(symbol)

    def remove_symbol(self, symbol: str):
        """Removes specified symbol from the assets_to_watch list."""
        if symbol in self.assets_to_watch:
            self.assets_to_watch.remove(symbol)
