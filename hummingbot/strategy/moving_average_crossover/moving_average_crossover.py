
import logging
import time
from decimal import Decimal
from statistics import mean
from typing import List
import requests

from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderType, TradeType
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

    def __init__(self, exchange, market_info, trading_pair, order_amount, market_swing, ma_crossover, sell_markup):
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
        self._cool_off_interval: float = 10

    def tick(self, timestamp: float):
        if not self._connector_ready:
            self._connector_ready = self.all_markets_ready()
            if not self._connector_ready:
                self.logger().warning(f"{self._exchange.name} not ready. Please wait.")
                return
            else:
                self.logger().info(f"{self._exchange.name} ready. Happy trading!")

        # new code
        proposal: List[OrderCandidate] = self.create_proposal()
        proposal = self._budget_checker.adjust_candidates(proposal, all_or_none=False)
        if proposal:
            self.execute_proposal(proposal)

    def all_markets_ready(self):
        return all([market.ready for market in self.active_markets])

    def create_proposal(self) -> List[OrderCandidate]:
        """
        Creates and returns a proposal (a list of order candidate), in this strategy the list has 1 element at most.
        """
        daily_closes = self._get_daily_close_list(self._trading_pair)
        start_index = (-1 * int(self._ma_crossover_period)) - 1

        # Calculate the average of the X element prior to the last element
        avg_close = mean(daily_closes[start_index:-1])
        proposal = []
        # If the current price (the last close) is below the dip, add a new order candidate to the proposal
        market_dip_criteria = daily_closes[-1] > avg_close * (Decimal("1") - (Decimal(self._market_swing) / Decimal("100")))
        buy_signal = "BUY" if market_dip_criteria else "IDLE"
        print(f"AVG ({self._ma_crossover_period} day): {avg_close} | LAST: {daily_closes[-1]} | {buy_signal}")
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
                order_id = self.buy_with_specific_market(
                    market_trading_pair_tuple=self._market_info,
                    amount=order_candidate.amount,
                    order_type=order_candidate.order_type,
                    price=order_candidate.price,
                )

                self.last_ordered_ts = time.time()
                self.logger().info(f"BUY ORDER: {order_id}")
                self.logger().info(f"BUY {self._trading_pair} - {order_candidate.amount} @ {order_candidate.price}")

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
                  "interval": "1d"}
        records = requests.get(url=url, params=params).json()
        return [Decimal(str(record[4])) for record in records]

    def convert_number_to_decimal(self, number) -> Decimal:
        return Decimal(number) / Decimal("100")
