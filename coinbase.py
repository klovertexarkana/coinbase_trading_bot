from models import *
import dateutil.parser
import hashlib
import hmac
import json
from interfaces.logging_component import logger
import numpy as np
import requests
from strategies import TechnicalStrategy, BreakoutStrategy
import threading
import time
import typing
import websocket


class CoinbaseClient:
    def __init__(self, public_key: str, secret_key: str):
        self._public_key = public_key
        self._secret_key = secret_key

        self._base_url = 'https://api.coinbase.com'
        self._ws_url = 'wss://advanced-trade-ws.coinbase.com'
        # dict that contains the 'product-id' of each asset as a key and Asset object further defined in models.py
        self.assets = self.get_assets()
        # dictionary that has contract name ('BTC-USDT') as a key and values is a dict containing the best bid and ask
        # price, the get_bid_ask method fills this dict
        self.prices = dict()
        # dict containing the product_id and your account balances represented by a Balance object (models.py) as value
        self.balances = self.get_balances()
        # dict that holds the strategy index as a key and a strategy object as a value
        self.strategies: typing.Dict[int, typing.Union[TechnicalStrategy, BreakoutStrategy]] = dict()

        self._ws = websocket.WebSocketApp
        self._reconnect = True

        self.logger = logger
        self.logs = []

        self.logger.info('Coinbase Client successfully initialized')

        t = threading.Thread(target=self._start_ws)
        t.start()

    def _add_log(self, msg: str):
        self.logs.append({'log': msg, 'displayed': False})

    def _create_signature(self, method: str, endpoint: str, timestamp, data) -> str:
        """Creates the signature for the CB-ACCESS-SIGN header required by all requests."""
        # https://docs.cloud.coinbase.com/advanced-trade-api/docs/rest-api-auth
        if method == 'POST':
            message = timestamp + method + endpoint + str(json.dumps(data))
        else:
            message = timestamp + method + endpoint

        signature = hmac.new(self._secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
        return signature

    def _make_request(self, method: str, endpoint: str, data: typing.Dict):
        """Method to make all requests."""
        timestamp = str(int(time.time()))
        headers = dict()
        headers['CB-ACCESS-KEY'] = self._public_key
        headers['CB-ACCESS-TIMESTAMP'] = str(int(time.time()))
        headers['CB-ACCESS-SIGN'] = self._create_signature(method, endpoint, timestamp, data)
        headers['accept'] = 'application/json'

        if method == 'GET':
            try:
                response = requests.get(self._base_url + endpoint, params=data, headers=headers)
            except Exception as err:
                logger.error(f'Connection error while making {method} request to {endpoint}: {err}')
                return None

        elif method == 'POST':
            try:
                response = requests.post(self._base_url + endpoint, json=data, headers=headers)
            except Exception as err:
                logger.error(f'Connection error while making {method} request to {endpoint}: {err}')
                return None

        elif method == 'DELETE':
            try:
                response = requests.delete(self._base_url + endpoint, params=data, headers=headers)
            except Exception as err:
                logger.error(f'Connection error while making {method} request to {endpoint}: {err}')
                return None

        else:
            return ValueError()

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'Error while making {method} reqeust to {endpoint}: (error code: {response.status_code})')
            return None

    def get_assets(self) -> typing.Dict[str, Asset]:
        """Creates a dictionary with the asset's symbol as the key and an Asset object that is defined in models.py as
        the value. This correlates to get_contracts() in the original course."""
        raw_assets = self._make_request('GET', '/api/v3/brokerage/products', dict())
        assets = dict()
        if raw_assets is not None:
            for asset in raw_assets['products']:
                # pare down the number of assets I'm interested in, of course the quote currencies can be changed to
                # suit individual needs
                if '-' + asset['product_id'].split('-')[1] in ['-EUR', '-GBP', '-BTC', '-ETH', '-USDT', '-DAI']:
                    continue
                else:
                    assets[asset['product_id']] = Asset(asset)

        return assets

    def get_historical_candles(self, asset: Asset, interval: str) -> typing.List[Candle]:
        """Creates a list of 300 Candle objects."""
        timeframes = {'ONE_MINUTE': int(time.time() - 18000),
                      'FIVE_MINUTE': int(time.time() - 90000),
                      'FIFTEEN_MINUTE': int(time.time() - 270000),
                      'THIRTY_MINUTE': int(time.time() - 540000),
                      'ONE_HOUR': int(time.time() - 1080000),
                      'TWO_HOUR': int(time.time() - 2160000),
                      'SIX_HOUR': int(time.time() - 6480000),
                      'ONE_DAY': int(time.time() - 25920000)}
        data = dict()
        data['start'] = timeframes[interval]
        data['end'] = int(time.time())
        data['granularity'] = interval

        candles = []
        raw_candles = self._make_request('GET', '/api/v3/brokerage/products/' + asset.symbol + '/candles', data)

        if raw_candles is not None:
            for raw_candle in raw_candles['candles']:
                candles.append(Candle(raw_candle))

        return candles

    def get_bid_ask(self, asset: Asset) -> typing.Dict[str, float]:
        """Returns the specific bid/ask prices for the asset within the self.prices dict."""
        price_data = self._make_request('GET', '/api/v3/brokerage/products/' + asset.symbol + '/ticker', dict())

        if price_data is not None:
            try:
                if asset.symbol not in self.prices:
                    self.prices[asset.symbol] = {'bid': float(price_data['best_bid']),
                                                 'ask': float(price_data['best_ask'])}
                else:
                    self.prices[asset.symbol]['bid'] = float(price_data['best_bid'])
                    self.prices[asset.symbol]['ask'] = float(price_data['best_ask'])
            except ValueError as err:
                self.logger.error(f'Value error using get_bid_ask method: {err}')

        return self.prices[asset.symbol]

    def get_balances(self) -> typing.Dict[str, Balance]:
        """Creates a dictionary named balances where key is the asset symbol and the value is a Balance object defined
        in models.py"""
        list_of_balances = self._make_request('GET', '/api/v3/brokerage/accounts/', dict())
        balances = dict()

        if list_of_balances is not None:
            for raw_balance in list_of_balances['accounts']:
                balances[raw_balance['available_balance']['currency']] = Balance(raw_balance)

        return balances

    def place_order(self, asset: Asset, side: str, order_type: str, quantity: str, limit=None) -> OrderStatus:
        """Place an order. For MARKET order, quantity is in quote currency for BUY orders and base currency for SELL
        orders. For LIMIT order quantity is amount of base currency and limit equals the ceiling price the order
        should get filled."""
        data = dict()
        data['client_order_id'] = str(np.random.randint(2**63))
        data['product_id'] = asset.symbol
        data['side'] = side

        if side == 'BUY':
            if order_type == 'MARKET':
                data['order_configuration'] = {'market_market_ioc': {'quote_size': quantity}}
            elif order_type == 'LIMIT':
                data['order_configuration'] = {'limit_limit_gtc': {'base_size': quantity,
                                                                   'limit_price': limit,
                                                                   'post_only': False}}

        elif side == 'SELL':
            if order_type == 'MARKET':
                data['order_configuration'] = {'market_market_ioc': {'base_size': quantity}}
            elif order_type == 'LIMIT':
                data['order_configuration'] = {'limit_limit_gtc': {'base_size': quantity,
                                                                   'limit_price': limit,
                                                                   'post_only': False}}

        order = self._make_request('POST', '/api/v3/brokerage/orders', data)

        if order['success'] is True:
            order_id = order['order_id']
            time.sleep(0.5)
            order_status = self.get_order_status(order_id)
            return order_status
        else:
            print(order)
            self.logger.warning(f'Failure of place_order method for {data["side"]} order on {data["product_id"]}  due '
                                f'to {order["error_response"]["message"]}')

    def get_order_status(self, order_id: str) -> OrderStatus:
        """Takes a coinbase order_id and returns and OrderStatus object"""
        order_status = self._make_request('GET', '/api/v3/brokerage/orders/historical/' + order_id, dict())

        if order_status is not None:
            order_status = OrderStatus(order_status['order'])

        return order_status

    def cancel_order(self, order_id):
        """Cancel an order or multiple orders by order_id"""
        data = dict()
        data['order_ids'] = [order_id]

        order = self._make_request('POST', "/api/v3/brokerage/orders/batch_cancel", data)

        if order['results'][0]['success'] is not False:
            time.sleep(0.5)
            order_status = self.get_order_status(order['results'][0]['order_id'])
            return order_status
        else:
            self.logger.warning(f'Failure of cancel_order method for order_id: {data["order_ids"]}')

    def _start_ws(self):
        self._ws = websocket.WebSocketApp(self._ws_url, on_open=self._on_open, on_close=self._on_close,
                                          on_error=self._on_error, on_message=self._on_message)
        while True:
            try:
                if self._reconnect:
                    self._ws.run_forever()
                else:
                    break

            except Exception as err:
                self.logger.error(f'Coinbase websocket error in run_forever method: {err}')
            time.sleep(2)

    def _on_open(self, ws):
        self.logger.info('Coinbase connection opened')

        self.subscribe_channel(list(self.assets.values())[:len(self.assets) - 2], 'ticker')
        self.subscribe_channel(list(self.assets.values())[:len(self.assets) - 2], 'market_trades')

    def _on_close(self, ws):
        self.logger.warning('Coinbase connection closed')

    def _on_error(self, ws, msg: str):
        self.logger.error(f'Coinbase connection error: {msg}')

    def _on_message(self, ws, msg: str):
        """Currently fills the self.prices w/ the best bid/ask prices"""
        data = json.loads(msg)

        if 'channel' in data and data['channel'] == 'ticker':
            symbol = data['events'][0]['tickers'][0]['product_id']

            if symbol not in self.prices:

                self.prices[symbol] = {'bid': float(data['events'][0]['tickers'][0]['price']),
                                       'ask': float(data['events'][0]['tickers'][0]['price'])}
            else:
                self.prices[symbol]['bid'] = float(data['events'][0]['tickers'][0]['price'])
                self.prices[symbol]['ask'] = float(data['events'][0]['tickers'][0]['price'])

            # PNL Calculation
            # THIS CALCULATION DOES NOT TAKE INTO ACCOUNT FEES FOR TRANSACTIONS

            try:
                for strategy_index, strategy in self.strategies.items():
                    if strategy.asset.symbol == symbol:
                        for trade in strategy.trades:
                            if trade.status == 'open' and trade.entry_price is not None:
                                if trade.side == 'long':
                                    trade.pnl = (self.prices[symbol]['bid'] - float(trade.entry_price)) * \
                                                (float(trade.quantity) / float(trade.entry_price))
                                elif trade.side == 'short':
                                    trade.pnl = (float(trade.entry_price) - self.prices[symbol]['ask']) * \
                                                float(trade.quantity)

            except RuntimeError:
                logger.error('Error while looping through strategies dict to calculate the PNL')

        # IF THERE IS A PROBLEM LATER ON, NOTED HERE THAT THIS CHANNEL GIVEs SELL SIDE INFO, NOT SURE HOW THIS WILL
        # AFFECT FINAL PRODUCT
        elif 'channel' in data and data['channel'] == 'market_trades':
            symbol = data['events'][0]['trades'][0]['product_id']
            # convert iso8601 datetime format to a unix timestamp in milliseconds
            ts = int(dateutil.parser.isoparse(data['timestamp']).timestamp())

            for key, strategy in self.strategies.items():
                if strategy.asset.symbol == symbol:
                    # In strategies.py this method results in "same_candle" or "new_candle" based on the feed
                    res = strategy.parse_trade(float(data['events'][0]['trades'][0]['price']),
                                               float(data['events'][0]['trades'][0]['size']), ts)
                    # In strategies.py checks to see if our parameters have been met to enter a trade
                    strategy.check_trade(res)

    def subscribe_channel(self, assets: typing.List[Asset], channel: str):
        data = dict()
        data['type'] = 'subscribe'
        data['product_ids'] = []
        for asset in assets:
            data['product_ids'].append(asset.symbol)
        data['channel'] = channel
        data['api_key'] = self._public_key
        data['timestamp'] = str(int(time.time()))
        data['signature'] = self._create_signature(data['channel'], ','.join(data['product_ids']), data['timestamp'],
                                                   dict())

        try:
            self._ws.send(json.dumps(data))
        except Exception as err:
            self.logger.error(f'Websocket error while subscribing to {len(assets) - 2} {channel} updates: {err}')

    def get_trade_size(self, side: str, asset: Asset, balance_pct: float):
        # will need to add conditional if limit orders are to be utilized
        """Market/BUY orders trade_size must be calculated in quote currency. Market/SELL orders trade_size calculated
        in base currency. No limit orders yet"""
        balance = self.get_balances()

        if balance is not None:
            if side == 'BUY':
                if 'USD' in balance:
                    balance = balance['USD'].wallet_balance
                    trade_size = round(balance * (balance_pct / 100), asset.quote_increment)
                    logger.info(f'Current balance of USD: {balance} | trade size: {trade_size}')
                else:
                    return None
            elif side == 'SELL':
                # make sure you own enough of the asset to sell
                if asset.symbol.split('-')[0] in balance:
                    balance = balance[asset.symbol.split('-')[0]].wallet_balance
                    trade_size = round(balance * (balance_pct / 100), asset.base_increment)
                    logger.info(f'Current balance of {asset.symbol.split("-")[0]}: {balance} | trade size: '
                                f'{trade_size}')
                else:
                    return None
        else:
            return None

        return str(trade_size)
