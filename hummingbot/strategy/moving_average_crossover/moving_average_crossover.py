
import logging
import statistics
import time
from decimal import Decimal
from statistics import mean
from typing import List
import requests

import pandas as pd
from hummingbot.client.performance import PerformanceMetrics

from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import LimitOrderStatus, OrderFilledEvent, OrderType, TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.budget_checker import BudgetChecker

hws_logger = None


class MovingAverageCrossover(StrategyPyBase):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self, exchange, market_info, trading_pair, order_amount, market_swing, ma_crossover, sell_markup, cooling_period, stop_loss):
        super().__init__()
        self._market_info = market_info
        self._exchange = exchange
        self._trading_pair = trading_pair
        self._order_amount = order_amount
        self._market_swing = self.convert_number_to_decimal(market_swing)
        self._ma_crossover_period = ma_crossover
        self._sell_markup = self.convert_number_to_decimal(sell_markup)
        self.add_markets([exchange])
        self._connector_ready = False
        self._budget_checker = BudgetChecker(exchange=exchange)
        self.last_ordered_ts: float = 0
        self._cool_off_interval: float = float(cooling_period)
        self._stop_loss = self.convert_number_to_decimal(stop_loss)

    def tick(self, timestamp: float):
        if not self._connector_ready:
            self._connector_ready = self.all_markets_ready()
            if not self._connector_ready:
                self.logger().warning(f"{self._exchange.name} not ready. Please wait.")
                return
            else:
                self.logger().info(f"{self._exchange.name} ready. Happy trading!")

        # Create buy orders (Proposals)
        proposal: List[OrderCandidate] = self.create_proposal()
        proposal = self._budget_checker.adjust_candidates(proposal, all_or_none=False)
        if proposal:
            self.execute_proposal(proposal)

        # Run stop loss check
        self.stop_loss_check()

    def all_markets_ready(self):
        return all([market.ready for market in self.active_markets])

    def create_proposal(self) -> List[OrderCandidate]:
        """
        Creates and returns a proposal (a list of order candidates), in this strategy the list has 1 element at most.
        """
        daily_closes = self._get_daily_close_list(self._trading_pair)
        start_index = (-1 * int(self._ma_crossover_period)) - 1

        # Calculate the average of the X element prior to the last element
        avg_close = mean(daily_closes[start_index:-1])
        proposal = []

        # If the current price (the last close) is below the dip, add a new order candidate to the proposal
        market_dip_criteria = daily_closes[-1] < avg_close * (Decimal("1") - Decimal(self._market_swing))
        # market_dip_criteria = daily_closes[-1] < avg_close

        # buy_signal = "BUY" if market_dip_criteria else "IDLE"
        # print(f"AVG ({self._ma_crossover_period} day): {avg_close} | LAST: {daily_closes[-1]} | {buy_signal}")

        if market_dip_criteria:
            order_price = self._exchange.get_price(self._trading_pair, False)
            amount = self._order_amount / order_price
            proposal.append(OrderCandidate(self._trading_pair, False, OrderType.LIMIT, TradeType.BUY, amount, order_price))
        return proposal

    def execute_proposal(self, proposal: List[OrderCandidate]):
        """
        Places the order candidates on the exchange, if it is not within cool off period and order candidate is valid.
        """
        if self.last_ordered_ts > time.time() - self._cool_off_interval:
            return
        for order_candidate in proposal:
            if order_candidate.amount > Decimal("0"):
                self.buy_with_specific_market(
                    market_trading_pair_tuple=self._market_info,
                    amount=order_candidate.amount,
                    order_type=order_candidate.order_type,
                    price=order_candidate.price,
                )

                self.last_ordered_ts = time.time()

    def create_sell_order_candidate(self, order_completed_event):
        """
        Places sell order based on buy amount and price.
        """
        order_id: str = order_completed_event.order_id
        market_info = self.order_tracker.get_market_pair_from_order_id(order_id)

        if market_info is not None:
            limit_order_record = self.order_tracker.get_limit_order(market_info, order_id)
            if limit_order_record.is_buy:
                sell_price = limit_order_record.price + (Decimal(limit_order_record.price) * Decimal(self._sell_markup))
                # print(f"orig amount: {limit_order_record.quantity}")
                # amount = (limit_order_record.price * limit_order_record.quantity) / sell_price
                # print(f"sell amount: {amount}")
                last_trade_value_usd = Decimal(limit_order_record.quantity) / Decimal(limit_order_record.price)
                trade_amount = last_trade_value_usd / sell_price
                minimum_trade_amount = Decimal(limit_order_record.quantity) - Decimal("0.00001")
                calculated_trade_amount = trade_amount if trade_amount > minimum_trade_amount else minimum_trade_amount
                # print(f"min amount: {minimum_trade_amount}")
                order_id = self.sell_with_specific_market(
                    market_trading_pair_tuple=self._market_info,
                    amount=calculated_trade_amount,
                    order_type=OrderType.LIMIT,
                    price=sell_price,
                )

    def _get_daily_close_list(self, trading_pair: str) -> List[Decimal]:
        """
        Fetches binance candle stick data and returns a list daily close
        This is the API response data structure:
        [
          [
            1499040000000,      // Open time
            "0.01634790",       // Open
            "0.80000000",       // High
            "0.01575800",       // Low
            "0.01577100",       // Close
            "148976.11427815",  // Volume
            1499644799999,      // Close time
            "2434.19055334",    // Quote asset volume
            308,                // Number of trades
            "1756.87402397",    // Taker buy base asset volume
            "28.46694368",      // Taker buy quote asset volume
            "17928899.62484339" // Ignore.
          ]
        ]
        :param trading_pair: A market trading pair to
        :return: A list of daily close
        """

        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": trading_pair.replace("-", ""),
                  "interval": "15m"}
        records = requests.get(url=url, params=params).json()
        return [Decimal(str(record[4])) for record in records]

    def convert_number_to_decimal(self, number) -> Decimal:
        return Decimal(number) / Decimal("100")

    def log_complete_order(self, order_completed_event):
        """
        Output log for completed order.
        :param order_completed_event: Order completed event
        """
        order_id: str = order_completed_event.order_id
        market_info = self.order_tracker.get_market_pair_from_order_id(order_id)

        if market_info is not None:
            limit_order_record = self.order_tracker.get_limit_order(market_info, order_id)
            order_type = "buy" if limit_order_record.is_buy else "sell"
            self.log_with_clock(
                logging.INFO,
                f"({market_info.trading_pair}) Limit {order_type} order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been filled."
            )

    def did_complete_buy_order(self, order_completed_event):
        """
        Output log for completed buy order. This method will also trigger sell order creation.
        """
        self.log_complete_order(order_completed_event)
        self.create_sell_order_candidate(order_completed_event)

    def did_create_sell_order(self, order_created_event):
        """
        Output log for created sell order.
        """
        order_id: str = order_created_event.order_id
        market_info = self.order_tracker.get_market_pair_from_order_id(order_id)

        if market_info is not None:
            limit_order_record = self.order_tracker.get_limit_order(market_info, order_id)
            order_type = "buy" if limit_order_record.is_buy else "sell"
            self.log_with_clock(
                logging.INFO,
                f"({market_info.trading_pair}) Limit {order_type} order {order_id} "
                f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                f"{limit_order_record.price} {limit_order_record.quote_currency}) has been created."
            )

    def did_complete_sell_order(self, order_completed_event):
        """
        Output log for completed sell order.
        :param order_completed_event: Order completed event
        """
        self.log_complete_order(order_completed_event)

    def filled_trades(self):
        """
        Returns a list of all filled trades generated from limit orders with the same trade type the strategy
        has in its configuration
        """
        trade_type = TradeType.SELL
        return [trade
                for trade
                in self.trades
                if trade.trade_type == trade_type.name and trade.order_type == OrderType.LIMIT]

    @property
    def active_orders(self) -> List[LimitOrderStatus]:
        limit_orders: List[LimitOrder] = self.order_tracker.active_limit_orders
        return [o[1] for o in limit_orders]

    async def format_status(self) -> str:
        """
        Method called by the `status` command. Generates the status report for this strategy.
        Outputs the best bid and ask prices of the Order Book.
        """
        if not self._connector_ready:
            return f"{self._exchange.name} connector is not ready..."

        lines = []

        lines.extend(["", "  NRDYRK"])

        lines.extend(["", f"  Market: {self._exchange.name} | {self._trading_pair}"])

        daily_closes = self._get_daily_close_list(self._trading_pair)
        start_index = (-1 * int(self._ma_crossover_period)) - 1
        avg_close = mean(daily_closes[start_index:-1])
        target_price = avg_close * (Decimal("1") - Decimal(self._market_swing))

        lines.extend(["", f"  AVG({int(self._ma_crossover_period)}d): {avg_close} | BUY: {target_price} | LAST: {daily_closes[-1]}"])

        assets_df = self.wallet_balance_data_frame([self._market_info])
        lines.extend(["", "  Assets:"] + ["    " + line for line in str(assets_df).split("\n")])

        filled_trades = self.filled_trades()
        lines.extend(["", f"  Closed Trades: {len(filled_trades)}"])

        if len(self.active_orders) > 0:
            columns = ["Type", "Price", "Amount", "Spread(%)", "Age"]
            data = []
            coin_price = self._exchange.get_price(self._trading_pair, False)
            for order in self.active_orders:
                spread = abs(order.price - coin_price) / coin_price
                data.append([
                    # "BUY" if self._is_buy else "SELL",
                    "ORDER",
                    float(order.price),
                    float(order.quantity),
                    f"{spread:.3%}",
                    pd.Timestamp(int(time.time() - (order.creation_timestamp * 1e-6)),
                                 unit='s').strftime('%H:%M:%S')
                ])

            df = pd.DataFrame(data=data, columns=columns)
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])

        else:
            lines.extend(["", "  No active orders."])

        return "\n".join(lines)

    def stop_loss_check(self):
        max_spread: float = self._stop_loss
        coin_price = self._exchange.get_price(self._trading_pair, False)
        for order in self.active_orders:
            order_spread = abs(order.price - coin_price) / coin_price
            if order_spread > max_spread:
                # Cancel order
                self.cancel_order(self._market_info, order.client_order_id)
                # Sell off order
                self.sell_with_specific_market(
                    market_trading_pair_tuple=self._market_info,
                    amount=order.quantity,
                    order_type=OrderType.LIMIT,
                    price=coin_price,
                )
