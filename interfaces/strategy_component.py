from database import *
from coinbase import CoinbaseClient
import json
from interfaces.root_component import logger
from strategies import TechnicalStrategy, BreakoutStrategy
# from trades_component import TradesWatch


class StrategyEditor:
    def __init__(self, coinbase: CoinbaseClient):

        self.coinbase = coinbase
        self.logger = logger

        self.db = WorkspaceData()

        self._all_assets = [key for key in self.coinbase.get_assets().keys()]
        self._all_timeframes = ['ONE_MINUTE', 'FIVE_MINUTE', 'FIFTEEN_MINUTE', 'THIRTY_MINUTE', 'ONE_HOUR', 'TWO_HOUR',
                                'SIX_HOUR', 'ONE_DAY']

        # self.body_widgets in original course
        self.trade_strategies = dict()
        # is a dict that has a strategy_index as the key relating to one of the strategies, but holds the additional
        # parameters that would be validated in the popup window. See add_strategy method
        self._additional_parameters = dict()

        self._strategy_index = 0
        self.load_workspace()

    def add_strategy(self, strategy_type: str, asset: str, time_frame: str, balance_pct: str, take_profit: str,
                     stop_loss: str, *args):
        """Add a strategy to the self.trade_strategies dictionary, called in the root_component"""
        if strategy_type == 'Breakout' and len(args) != 1:
            self.logger.warn(f'You did not input the correct number of additional parameters for {strategy_type} '
                             f'strategy.')
            return
        elif strategy_type == 'Technical' and len(args) != 4:
            self.logger.warn(f'You did not input the correct number of additional parameters for {strategy_type} '
                             f'strategy.')
            return

        # create new entry into self.trade_strategies
        strategy_index = self._strategy_index
        # add the basic parameters to self.trade_strategies
        self.trade_strategies[strategy_index] = {'strategy_type': strategy_type, 'asset': asset,
                                                 'timeframe': time_frame, 'balance_pct': balance_pct,
                                                 'take_profit': take_profit, 'stop_loss': stop_loss}

        # add the additional parameters to self.trade strategies, based on type of strategy desired
        if self.trade_strategies[strategy_index]['strategy_type'] == 'Breakout':
            self.trade_strategies[strategy_index].update({'min_volume': args[0]})

        elif self.trade_strategies[strategy_index]['strategy_type'] == 'Technical':
            self.trade_strategies[strategy_index].update({
                'rsi_length': args[0],
                'ema_fast': args[1],
                'ema_slow': args[2],
                'ema_signal': args[3]})

        self._strategy_index += 1

    def switch_strategy(self, strategy_index: int):
        """Activate/deactivate a trade strategies that exists in your self.trade_strategies dictionary."""
        strat_selected = self.trade_strategies[strategy_index]
        symbol = strat_selected['asset']

        asset = self.coinbase.assets[symbol]
        timeframe = strat_selected['timeframe']
        balance_pct = float(strat_selected['balance_pct'])
        take_profit = float(strat_selected['take_profit'])
        stop_loss = float(strat_selected['stop_loss'])

        if strat_selected['strategy_type'] == 'Technical':
            rsi_length = int(strat_selected['rsi_length'])
            ema_fast = int(strat_selected['ema_fast'])
            ema_slow = int(strat_selected['ema_slow'])
            ema_signal = int(strat_selected['ema_signal'])
            new_strategy = TechnicalStrategy(self.coinbase, asset, timeframe, balance_pct, take_profit, stop_loss,
                                             rsi_length, ema_fast, ema_slow, ema_signal)

        elif strat_selected['strategy_type'] == 'Breakout':
            min_volume = int(strat_selected['min_volume'])
            new_strategy = BreakoutStrategy(self.coinbase, asset, timeframe, balance_pct, take_profit, stop_loss,
                                            min_volume)
        else:
            self.logger.warn(f'{strat_selected["strategy_type"]} is not a valid strategy type.')

        self.logger.info(f'{strat_selected["strategy_type"]} strategy ACTIVATED on {symbol} {timeframe}')

        new_strategy.candles = self.coinbase.get_historical_candles(asset, timeframe)
        new_strategy.candles.reverse()

        if len(new_strategy.candles) == 0:
            self.logger.warn(f'No historical data retrieved for {asset.symbol}')
            return

        # add your newly created strategy to the strategies dict created in coinbase.py
        self.coinbase.strategies[strategy_index] = new_strategy

    def delete_strategy(self, strategy_index: int):
        """Build new self.trade_strategies dict w/o strategy indicated by strategy_index."""
        # delete indicated entry in old self.trade_strategies dict
        del self.trade_strategies[strategy_index]

        # build new self.trade_strategies dict
        old_values = list(self.trade_strategies.values())
        self._strategy_index = 0
        self.trade_strategies = {}
        for i in range(len(old_values)):
            self.add_strategy(*old_values[i].values())

    def load_workspace(self):
        """Load self.trade_strategies dict w/ trades that were saved during last shutdown."""
        data = self.db.get('strategies')

        for row in data:
            if row['strategy_type'] == 'Breakout':
                extra_params = json.loads(row['extra_params'])
                self.add_strategy(row['strategy_type'], row['asset'], row['timeframe'], row['balance_pct'],
                                   row['take_profit'], row['stop_loss'], extra_params['min_volume'])

            elif row['strategy_type'] == 'Technical':
                extra_params = json.loads(row['extra_params'])
                self.add_strategy(row['strategy_type'], row['asset'], row['timeframe'], row['balance_pct'],
                                   row['take_profit'], row['stop_loss'], extra_params['rsi_length'],
                                   extra_params['ema_fast'], extra_params['ema_slow'], extra_params['ema_signal'])


