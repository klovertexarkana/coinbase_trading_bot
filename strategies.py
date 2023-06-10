from models import *
from typing import *
from interfaces.logging_component import logger
import pandas as pd
import time
from threading import Timer
if TYPE_CHECKING:
    from coinbase import CoinbaseClient

TF_EQUIV = {'ONE_MINUTE': 60, 'FIVE_MINUTE': 300, 'FIFTEEN_MINUTE': 900, 'THIRTY_MINUTE': 1800, 'ONE_HOUR': 3600,
            'TWO_HOUR': 7200, 'SIX_HOUR': 21600, 'ONE_DAY': 86400}


class Strategy:
    def __init__(self, coinbase: "CoinbaseClient", asset: Asset, timeframe: str, balance_pct: float, take_profit: float,
                 stop_loss: float, strat_name):

        self.coinbase = coinbase
        self.asset = asset
        self.timeframe = timeframe
        # equal to the timeframe in milliseconds
        self.tf_equiv = TF_EQUIV[timeframe]
        self.balance_pct = balance_pct
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.strat_name = strat_name
        self.ongoing_position = False

        self.logger = logger

        self.candles: List[Candle] = []

        self.trades: List[Trade] = []
        self.logs = []

    def _add_log(self, msg: str):
        logger.info(msg)
        self.logs.append({'log': msg, 'displayed': False})

    def parse_trade(self, price: float, size: float, timestamp: int):
        """Takes incoming trade data from the market_trades websocket channel and updates the self.candles list."""
        timestamp_diff = int(time.time()) - timestamp
        if timestamp_diff >= 2000:
            # if you're seeing this message often, something in check_trades is slowing down the websocket updates
            logger.warning(f'{self.asset.symbol}: {timestamp_diff} milliseconds of difference between the current time '
                           f'and trade time')

        last_candle = self.candles[-1]

        # same candle: if timestamp of trade is not greater than the timestamp of last_candle
        if timestamp < last_candle.timestamp + self.tf_equiv:

            last_candle.close = price
            last_candle.volume += size

            if price > last_candle.high:
                last_candle.high = price
            elif price < last_candle.low:
                last_candle.low = price

            # check take profit and stop loss

            for trade in self.trades:
                if trade.status == 'open' and trade.entry_price is not None:
                    self._check_tp_sl(trade)
                    logger.info(f'Trade {trade.entry_id} - side: {trade.side}, entry price: {trade.entry_price}, '
                                f'current price: {price}, PNL: {trade.pnl}')

            return 'same_candle'

        # missing candle(s): if timestamp of trade is > next_candle + 1
        elif timestamp >= last_candle.timestamp + 2 * self.tf_equiv:
            missing_candles = int((timestamp - last_candle.timestamp) / self.tf_equiv) - 1
            logger.info(f'{missing_candles} missing candles for {self.asset.symbol}, on {self.timeframe} timeframe')

            for missing in range(missing_candles):
                new_ts = last_candle.timestamp + self.tf_equiv
                candle_info = {'start': new_ts, 'open': last_candle.close, 'high': last_candle.close,
                               'low': last_candle.close, 'close': last_candle.close, 'volume': 0}
                new_candle = Candle(candle_info)
                self.candles.append(new_candle)
                last_candle = new_candle

            new_ts = last_candle.timestamp + self.tf_equiv
            candle_info = {'start': new_ts, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': size}
            new_candle = Candle(candle_info)
            self.candles.append(new_candle)

            return 'new_candle'

        # next candle: if timestamp of trade is > end of last_candle, but < next_candle + 1
        elif timestamp >= last_candle.timestamp + self.tf_equiv:
            new_ts = last_candle.timestamp + self.tf_equiv
            candle_info = {'start': new_ts, 'open': price, 'high': price, 'low': price, 'close': price,
                           'volume': size}
            new_candle = Candle(candle_info)
            self.candles.append(new_candle)

            logger.info(f'New candle for {self.asset.symbol} on {self.timeframe} timeframe')
            return 'new_candle'

    def _check_order_status(self, order_id):

        order_status = self.coinbase.get_order_status(order_id)
        if order_status is not None:
            logger.info(f'Order status:  {order_status.status}')
            if order_status == 'FILLED':
                for trade in self.trades:
                    if trade.entry_id == order_id:
                        trade.entry_price = order_status.avg_price
                        break
                return

        t = Timer(2.0, lambda: self._check_order_status(order_id))
        t.start()

    def _open_position(self, signal_result: int):
        order_side = 'BUY' if signal_result == 1 else 'SELL'
        position_side = 'long' if signal_result == 1 else 'short'

        trade_size = self.coinbase.get_trade_size(order_side, self.asset, self.balance_pct)
        if trade_size is None:
            logger.warning('trade_size is None')
            return

        self._add_log(f'{position_side} signal on {self.asset.symbol} for {self.timeframe}')

        # if limit order will need to change
        order_status = self.coinbase.place_order(self.asset, order_side, 'MARKET', trade_size)

        if order_status is not None:
            self._add_log(f'{order_side} order placed | Status: {order_status.status}')
            self.ongoing_position = True
            avg_fill_price = None

            if order_status.status == 'FILLED':
                avg_fill_price = order_status.avg_price
            else:
                t = Timer(2.0, lambda: self._check_order_status(order_status.order_id))
                t.start()

            new_trade = Trade({'time': int(time.time()), 'entry_price': avg_fill_price, 'asset': self.asset,
                               'strategy': self.strat_name, 'side': position_side, 'status': 'open', 'pnl': 0,
                               'quantity': trade_size, 'entry_id': order_status.order_id})
            self.trades.append(new_trade)

    def _check_tp_sl(self, trade: Trade):
        tp_triggered = False
        sl_triggered = False

        price = self.candles[-1].close

        if trade.side == 'long':
            if price <= float(trade.entry_price) * (1 - (float(self.stop_loss) / 100)):
                sl_triggered = True
            elif price >= float(trade.entry_price) * (1 + (float(self.take_profit) / 100)):
                tp_triggered = True

        elif trade.side == 'short':
            if price >= float(trade.entry_price) * (1 + (float(self.stop_loss) / 100)):
                sl_triggered = True
            # I've disabled my TP on since I can't actually short, if I have a trade open and price reverses then a
            # long signal should kick in on breakout strategy, but would this be true for all strategies?
            # elif price <= float(trade.entry_price) * (1 - (float(self.take_profit) / 100)):
            #     tp_triggered = True

        if tp_triggered or sl_triggered:
            logger.info(f'{"Stop loss" if sl_triggered else "Take profit"} for {self.asset.symbol} on {self.timeframe}')
            # so here we need to figure out if we want to actually buy here or not for short's. Actually I think we do
            # once we buy we keep the same trade going and it will just sell when te trade goes the other way, correct??
            order_side = 'SELL' if trade.side == 'long' else 'BUY'

            if order_side == 'BUY':
                # trade is short and the initial trade.quantity is in base asset and needs to be converted to dollars
                trade.quantity = str(format(float(trade.quantity) *
                                            float(self.coinbase.prices[self.asset.symbol]['ask']), '.2f'))

            else:
                # trade is long and initial trade.quantity is in dollars and needs to be converted to base asset
                trade.quantity = str(format(float(trade.quantity) *
                                            (1 / float(self.coinbase.prices[self.asset.symbol]['ask'])),
                                            f'.{self.asset.base_increment}f'))

            order_status = self.coinbase.place_order(self.asset, order_side, 'MARKET', trade.quantity)

            if order_status is not None:
                logger.info(f'Exit order on {self.asset.symbol} on {self.timeframe} successfully placed')
                trade.status = 'closed'
                self.ongoing_position = False


class TechnicalStrategy(Strategy):
    def __init__(self, coinbase, asset: Asset, timeframe: str, balance_pct: float, take_profit: float, stop_loss: float,
                 rsi_length: int, ema_fast: int, ema_slow: int, ema_signal: int):
        super().__init__(coinbase, asset, timeframe, balance_pct, take_profit, stop_loss, 'Technical')

        self._rsi_length = rsi_length
        self._ema_fast = ema_fast
        self._ema_slow = ema_slow
        self._ema_signal = ema_signal

    def _rsi(self):
        close_list = []
        for candle in self.candles:
            close_list.append(candle.close)

        closes = pd.Series(close_list)
        # calculates the difference bw the close price of each candle over the time period
        delta = closes.diff().dropna()
        # create two copies of the delta list to specify if the delta is positive or negative
        up, down = delta.copy(), delta.copy()
        # for up we set the losses from one candle to the next to 0, only positive numbers in the series
        up[up < 0] = 0
        # for down we set the gains from one candle to the next to 0, only negative numbers in teh series
        down[down > 0] = 0
        # he uses com or center of mass to highlight there are multiple ways to calculate an exponential moving average
        avg_gain = up.ewm(com=(self._rsi_length - 1), min_periods=self._rsi_length).mean()
        avg_loss = down.abs().ewm(com=(self._rsi_length - 1), min_periods=self._rsi_length).mean()

        rs = avg_gain / avg_loss

        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.round(2)

        return rsi.iloc[-2]

    def _macd(self) -> Tuple[float, float]:

        close_list = []
        for candle in self.candles:
            close_list.append(candle.close)

        closes = pd.Series(close_list)

        ema_fast = closes.ewm(span=self._ema_fast).mean()
        ema_slow = closes.ewm(span=self._ema_slow).mean()

        macd_line = ema_fast - ema_slow
        macd_signal = macd_line.ewm(span=self._ema_signal).mean()

        return macd_line.iloc[-2], macd_signal.iloc[-2]

    def _check_signal(self):
        macd_line, macd_signal = self._macd()
        rsi = self._rsi()

        if rsi < 30 and macd_line > macd_signal:
            return 1
        elif rsi > 70 and macd_line < macd_signal:
            return -1
        else:
            return 0

    def check_trade(self, tick_type: str):
        """Checks the websocket feed for info to see if our parameters have been met to enter a trade."""
        if tick_type == 'new_candle' and not self.ongoing_position:
            signal_result = self._check_signal()

            if signal_result in [-1, 1]:
                self._open_position(signal_result)
        return


class BreakoutStrategy(Strategy):
    def __init__(self, coinbase, asset: Asset, timeframe: str, balance_pct: float, take_profit: float, stop_loss: float,
                 min_volume):
        super().__init__(coinbase, asset, timeframe, balance_pct, take_profit, stop_loss, 'Breakout')

        self.min_volume = min_volume

    def _check_signal(self) -> int:
        # HERE WE'LL ADD SOME SORT OF RSI PARAMETERS AS WELL
        if self.candles[-1].close > self.candles[-2].high and self.candles[-1].volume > self.min_volume:
            return 1
        elif self.candles[-1].close < self.candles[-2].low and self.candles[-1].volume > self.min_volume:
            return -1
        else:
            return 0

    def check_trade(self, tick_type: str):
        """Checks the websocket feed for signs of parameters being met to enter a trade."""
        if not self.ongoing_position:
            signal_result = self._check_signal()

            if signal_result in [-1, 1]:
                self._open_position(signal_result)
