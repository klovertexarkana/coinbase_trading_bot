from coinbase import CoinbaseClient
import json
from interfaces.logging_component import logger
from interfaces.strategy_component import StrategyEditor
from threading import Timer
from interfaces.watchlist_component import Watchlist


class Root:
    def __init__(self, coinbase: CoinbaseClient):
        self.coinbase = coinbase

        self.logger = logger
        self.logger.info('Root component initialized')

        self.watch_list = Watchlist(self.coinbase.assets)
        self.strategy_editor = StrategyEditor(self.coinbase)

        # if you want to add/delete strategies to what the strategy_component.trade_strategies dict already contains
        # then do it here:
        # self.strategy_editor.add_strategy('Breakout', 'ETH-USD', 'ONE_MINUTE', '1', '0.01', '0.01', '1')
        # self.strategy_editor.add_strategy('Technical', 'SOL-USD', 'ONE_MINUTE', '1', '1', '1', '14', '12', '26',
        # '9')
        # self.strategy_editor.add_strategy('Breakout', 'BTC-USD', 'ONE_MINUTE', '1', '1', '1', '1')
        # for i in range(len(self.strategy_editor.trade_strategies)):
        #     self.strategy_editor.delete_strategy(0)

        # if you want to activate/deactivate a strategy in the strategy_component.trade_strategies dict then do it here:
        # self.strategy_editor.switch_strategy(0)
        # self.strategy_editor.switch_strategy(1)

        # if you want to add/delete symbols to what the watchlist already contains do it here:
        # self.watch_list.remove_symbol('BTC-USD')
        # self.watch_list.add_symbol('SOL-USD')

        self._update_ui()

    def _update_ui(self):

        # logs
        for log in self.coinbase.logs:
            if not log['displayed']:
                self.logger.info(log['log'])
                self.coinbase.logs['displayed']: True

        # watchlist
        if len(self.watch_list.assets_to_watch) > 0:
            self.logger.info('WATCHLIST')
            for symbol in sorted(self.watch_list.assets_to_watch):
                if symbol in self.coinbase.prices.keys():
                    prices = self.coinbase.get_bid_ask(self.coinbase.assets[symbol])
                    if prices is not None:
                        precision = str(self.coinbase.assets[symbol].quote_increment)
                        bid_price = f'{prices["bid"]:.{str(precision)}f}'
                        ask_price = f'{prices["ask"]:.{str(precision)}f}'
                        self.logger.info(f'{symbol} - Bid: {bid_price} -- Ask: {ask_price}')

        # Trades and Logs

        try:
            for strategy_index, strategy in self.coinbase.strategies.items():
                for log in strategy.logs:
                    if not log['displayed']:
                        self.logger.info(log['log'])
                        log['displayed'] = True

        except RuntimeError as err:
            logger.error(f'Error while looping through coinbase strategies dictionary: {err}')

        # consider other options for a timer: https://stackoverflow.com/questions/8600161/executing-periodic-actions
        t = Timer(2, lambda: self._update_ui())
        t.start()

    def save_workspace(self):

        # Watchlist
        watch_lists = [(symbol,) for symbol in self.watch_list.assets_to_watch]
        self.watch_list.db.save('watchlist', watch_lists)

        # Strategies
        strategies = []

        for strategy in self.strategy_editor.trade_strategies.values():
            strategy_type = strategy['strategy_type']
            asset = strategy['asset']
            timeframe = strategy['timeframe']
            balance_pct = strategy['balance_pct']
            take_profit = strategy['take_profit']
            stop_loss = strategy['stop_loss']

            extra_params = dict()

            if strategy_type == 'Breakout':
                extra_params['min_volume'] = strategy['min_volume']
                strategies.append((strategy_type, asset, timeframe, balance_pct, take_profit, stop_loss,
                                   json.dumps(extra_params),))

            elif strategy_type == 'Technical':
                extra_params['rsi_length'] = strategy['rsi_length']
                extra_params['ema_fast'] = strategy['ema_fast']
                extra_params['ema_slow'] = strategy['ema_slow']
                extra_params['ema_signal'] = strategy['ema_signal']

                strategies.append((strategy_type, asset, timeframe, balance_pct, take_profit, stop_loss,
                                   json.dumps(extra_params),))

        self.strategy_editor.db.save('strategies', strategies)

        logger.info('Workspace saved')
