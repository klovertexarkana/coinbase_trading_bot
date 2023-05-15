# coinbase_trading_bot
This trading bot is fashioned after a bot created in the tutorial that can be found here:
https://www.udemy.com/course/cryptocurrency-trading-bot-with-user-interface-in-python/.

The bot in this repository has no tkinter components and only connects to coinbase. I wanted to 
eliminate the tkinter GUI in order to better understanding the data flows from the websocket feeds, 
other API calls, and parsing the trades. Also, as a US citizen I cannot legally interact with the 
Binance and Bitmex futures contracts.

Without a GUI, you can think of the root_component and the main python files as containing staging 
areas where you will want to input trade setup and execution. There are short commented out 
instructions along with examples of how to call the functions necessary to exectute trades.

In the future I plan to:
1. Add more trading strategies than the two strategies created in the tutorial linked above
2. Create a method for saving data in the event if the program crashing
3. Improve parsing of data from the websocket feeds

Instructions:
1. Fork the repository
2. Open the application in your IDE
3. If placing simple limit orders do this in main.py, see commented instructions
4. If setting up strategies do this in root_component.py, see commented instructions/examples
5. If executing a particular strategie that you have already set up in step 4 do this 
in root_component.py, see commented instructions/examples
6. If deleteing strategies do this in root_component.py, see commented instructions/examples

Requirements:
1. >=python3.8
2. sqlite3
3. DB Browser for Sqlite

I, of course, welcome all contributions and improvements to the code, but remember there is no 
testnet on Coinbase; make your transactions small while you're testing!
