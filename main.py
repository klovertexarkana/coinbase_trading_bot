import atexit
from coinbase import CoinbaseClient
from dotenv import load_dotenv
from interfaces.root_component import Root
import os
import signal

load_dotenv()

if __name__ == '__main__':
    coinbase = CoinbaseClient(os.getenv('API_Key'), os.getenv('API_Secret'))

    # create limit orders here, see coinbase.py for instructions in the place_order method

    root = Root(coinbase)
    atexit.register(root.save_workspace)
    # signal.signal(signal.SIGTERM, root.save_workspace)
    # signal.signal(signal.SIGKILL, root.save_workspace)












