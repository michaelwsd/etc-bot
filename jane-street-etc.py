#!/usr/bin/env python3
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py --test prod-like; sleep 1; done

import argparse
from collections import deque
from enum import Enum
import time
import socket
import json

# ~~~~~============== CONFIGURATION  ==============~~~~~
# Replace "REPLACEME" with your team name!
team_name = "ABRA"

# ~~~~~============== MAIN LOOP ==============~~~~~

# You should put your code here! We provide some starter code as an example,
# but feel free to change/remove/edit/update any of it as you'd like. If you
# have any questions about the starter code, or what to do next, please ask us!
#
# To help you get started, the sample code below tries to buy BOND for a low
# price, and it prints the current prices for VALE every second. The sample
# code is intended to be a working example, but it needs some improvement
# before it will start making good trades!

def counter():
    n = 0
    while True:
        yield n
        n += 1

class StateManager:
    def __init__(self, exchange):
        """Set up data structures to keep track of various trading bot states,
        like positions, orders and so on"""
        self.exchange = exchange
        self.position = {}
        for asset in exchange.read_message()['symbols']:
            self.position[asset['symbol']] = asset['position']
        self.orders = {}
        self.count = counter()

    def next_id(self):
        """Returns a fresh order id for the next order"""
        return next(self.count)

    def new_order(self, symbol, dir_, price, size):
        """Sends a new order and keeps track of it in our state"""
        order_id = self.next_id()
        self.exchange.send_add_message(order_id=order_id, symbol=symbol, dir=dir_, price=price, size=size)
        self.orders[order_id] = {'symbol': symbol, 'size': size}

    def cancel_order(self, order_id):
        self.exchange.send_cancel_message(order_id)
        del self.orders[order_id]

    def on_fill(self, message):
        """Handle a fill by decrementing the open size of the order and updating our
        positions"""
        order_id = message['order_id']
        fill_size = message['size']
        symbol = message['symbol']
        dir_ = message['dir']

        if dir_ == Dir.BUY:
            self.position[symbol] += fill_size
        else:
            self.position[symbol] -= fill_size
        
        self.orders[order_id]['size'] -= fill_size
        if self.orders[order_id]['size'] == 0:
            del self.orders[order_id]
            
        if symbol == 'BOND':
            self.reset_all_bond_orders()

    def reset_all_bond_orders(self):
        oid = list(self.orders.keys())
        for order_id in oid:
            if self.orders[order_id]['symbol'] == 'BOND':
                self.cancel_order(order_id)

        curr_pos = self.position['BOND']
        if -100 < curr_pos < 100:
            buy_size = 100 - curr_pos
            sell_size = 100 + curr_pos
            self.new_order('BOND', Dir.BUY, 999, buy_size)
            self.new_order('BOND', Dir.SELL, 1001, sell_size)

def execute_taking_strategy(state_manager, prices):
    vale_bid = prices['VALE']['bid']
    vale_ask = prices['VALE']['ask']
    valbz_bid = prices['VALBZ']['bid']
    valbz_ask = prices['VALBZ']['ask']

    if vale_bid is not None and valbz_ask is not None and vale_bid > valbz_ask:
        size = min(10, state_manager.position['VALBZ'])
        state_manager.new_order('VALBZ', Dir.BUY, valbz_ask, size)
        state_manager.new_order('VALE', Dir.SELL, vale_bid, size)
    elif vale_ask is not None and valbz_bid is not None and vale_ask < valbz_bid:
        size = min(10, state_manager.position['VALE'])
        state_manager.new_order('VALE', Dir.BUY, vale_ask, size)
        state_manager.new_order('VALBZ', Dir.SELL, valbz_bid, size)

def execute_providing_strategy(state_manager, prices):
    vale_bid = prices['VALE']['bid']
    vale_ask = prices['VALE']['ask']
    valbz_bid = prices['VALBZ']['bid']
    valbz_ask = prices['VALBZ']['ask']

    if valbz_bid is not None and vale_bid is not None and valbz_bid > vale_bid:
        state_manager.new_order('VALE', Dir.BUY, vale_bid + 1, 10)
    if valbz_ask is not None and vale_ask is not None and valbz_ask < vale_ask:
        state_manager.new_order('VALE', Dir.SELL, vale_ask - 1, 10)

def main():
    args = parse_arguments()
    exchange = ExchangeConnection(args=args)
    state_manager = StateManager(exchange)

    # Store and print the "hello" message received from the exchange. 
    print("First message from exchange:", state_manager.position)

    # track bids/asks
    prices = {
        'VALE': {'bid': None, 'ask': None},
        'VALBZ': {'bid': None, 'ask': None}
    }

    # Here is the main loop of the program. It will continue to read and
    # process messages in a loop until a "close" message is received. You
    # should write to code handle more types of messages (and not just print
    # the message). Feel free to modify any of the starter code below.
    while True:
        message = exchange.read_message()

        if message["type"] == "close":
            print("The round has ended")
            break

        elif message["type"] == "error":
            print(message['error'])

        elif message["type"] == "reject": 
            print(f'Order {message['order_id']} is rejected for the following reason: {message['error']}')

        elif message["type"] == "fill":
            state_manager.on_fill(message)

        elif message["type"] == "book":
            symbol = message['symbol']
            if symbol in prices:
                prices[symbol]['bid'] = message['buy'][0][0] if message['buy'] else None
                prices[symbol]['ask'] = message['sell'][0][0] if message['sell'] else None
                # Execute taking strategy
                execute_taking_strategy(state_manager, prices)
                # Execute providing strategy
                execute_providing_strategy(state_manager, prices)

            elif symbol == 'BOND':
                # execute bond strategy
                curr_pos = state_manager.position['BOND']
                send = True
                for order in state_manager.orders.values():
                    if order['symbol'] == 'BOND':
                        send = False

                if send and -100 < curr_pos < 100:
                    buy_size = 100 - curr_pos
                    sell_size = 100 + curr_pos
                    state_manager.new_order('BOND', Dir.BUY, 999, buy_size)
                    state_manager.new_order('BOND', Dir.SELL, 1001, sell_size)

# ~~~~~============== PROVIDED CODE ==============~~~~~

# You probably don't need to edit anything below this line, but feel free to
# ask if you have any questions about what it is doing or how it works. If you
# do need to change anything below this line, please feel free to

class Dir(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExchangeConnection:
    def __init__(self, args):
        self.message_timestamps = deque(maxlen=500)
        self.exchange_hostname = args.exchange_hostname
        self.port = args.port
        exchange_socket = self._connect(add_socket_timeout=args.add_socket_timeout)
        self.reader = exchange_socket.makefile("r", 1)
        self.writer = exchange_socket

        self._write_message({"type": "hello", "team": team_name.upper()})

    def read_message(self):
        """Read a single message from the exchange"""
        message = json.loads(self.reader.readline())
        if "dir" in message:
            message["dir"] = Dir(message["dir"])
        return message

    def send_add_message(
        self, order_id: int, symbol: str, dir: Dir, price: int, size: int
    ):
        """Add a new order"""
        self._write_message(
            {
                "type": "add",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "price": price,
                "size": size,
            }
        )

    def send_convert_message(self, order_id: int, symbol: str, dir: Dir, size: int):
        """Convert between related symbols"""
        self._write_message(
            {
                "type": "convert",
                "order_id": order_id,
                "symbol": symbol,
                "dir": dir,
                "size": size,
            }
        )

    def send_cancel_message(self, order_id: int):
        """Cancel an existing order"""
        self._write_message({"type": "cancel", "order_id": order_id})

    def _connect(self, add_socket_timeout):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if add_socket_timeout:
            # Automatically raise an exception if no data has been recieved for
            # multiple seconds. This should not be enabled on an "empty" test
            # exchange.
            s.settimeout(5)
        s.connect((self.exchange_hostname, self.port))
        return s

    def _write_message(self, message):
        print(message)
        what_to_write = json.dumps(message)
        if not what_to_write.endswith("\n"):
            what_to_write = what_to_write + "\n"

        length_to_send = len(what_to_write)
        total_sent = 0
        while total_sent < length_to_send:
            sent_this_time = self.writer.send(
                what_to_write[total_sent:].encode("utf-8")
            )
            if sent_this_time == 0:
                raise Exception("Unable to send data to exchange")
            total_sent += sent_this_time

        now = time.time()
        self.message_timestamps.append(now)
        if len(
            self.message_timestamps
        ) == self.message_timestamps.maxlen and self.message_timestamps[0] > (now - 1):
            print(
                "WARNING: You are sending messages too frequently. The exchange will start ignoring your messages. Make sure you are not sending a message in response to every exchange message."
            )


def parse_arguments():
    test_exchange_port_offsets = {"prod-like": 0, "slower": 1, "empty": 2}

    parser = argparse.ArgumentParser(description="Trade on an ETC exchange!")
    exchange_address_group = parser.add_mutually_exclusive_group(required=True)
    exchange_address_group.add_argument(
        "--production", action="store_true", help="Connect to the production exchange."
    )
    exchange_address_group.add_argument(
        "--test",
        type=str,
        choices=test_exchange_port_offsets.keys(),
        help="Connect to a test exchange.",
    )

    # Connect to a specific host. This is only intended to be used for debugging.
    exchange_address_group.add_argument(
        "--specific-address", type=str, metavar="HOST:PORT", help=argparse.SUPPRESS
    )

    args = parser.parse_args()
    args.add_socket_timeout = True

    if args.production:
        args.exchange_hostname = "production"
        args.port = 25000
    elif args.test:
        args.exchange_hostname = "test-exch-" + team_name
        args.port = 22000 + test_exchange_port_offsets[args.test]
        if args.test == "empty":
            args.add_socket_timeout = False
    elif args.specific_address:
        args.exchange_hostname, port = args.specific_address.split(":")
        args.port = int(port)

    return args

if __name__ == "__main__":
    # Check that [team_name] has been updated.
    assert (
        team_name != "REPLAC" + "EME"
    ), "Please put your team name in the variable [team_name]."

    main()
