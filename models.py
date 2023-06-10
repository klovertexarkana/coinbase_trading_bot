
class Balance:
    def __init__(self, info):
        self.wallet_balance = float(info['available_balance']['value'])
        self.UUID = info['uuid']


class Asset:
    def __init__(self, contract_info):
        self.symbol = contract_info['product_id']
        self.base_asset = contract_info['base_currency_id']
        self.quote_asset = contract_info['quote_currency_id']
        self.quote_increment = len(contract_info['quote_increment'].split('.')[1])
        if '.' in contract_info['base_increment']:
            self.base_increment = len(contract_info['base_increment'].split('.')[1])
        else:
            self.base_increment = None


class Candle:
    def __init__(self, candle_info):

        self.timestamp = int(candle_info['start'])
        self.open = float(candle_info['open'])
        self.high = float(candle_info['high'])
        self.low = float(candle_info['low'])
        self.close = float(candle_info['close'])
        self.volume = float(candle_info['volume'])


class OrderStatus:
    def __init__(self, order_info):
        self.order_id = order_info['order_id']
        self.status = order_info['status']
        self.avg_price = order_info['average_filled_price']


class Trade:
    def __init__(self, trade_info):
        self.time: int = trade_info['time']
        self.asset: Asset = trade_info['asset']
        self.strategy: str = trade_info['strategy']
        self.side: str = trade_info['side']
        self.entry_price: float = trade_info['entry_price']
        self.status: str = trade_info['status']
        self.pnl: float = trade_info['pnl']
        self.quantity = trade_info['quantity']
        self.entry_id: int = trade_info['entry_id']
