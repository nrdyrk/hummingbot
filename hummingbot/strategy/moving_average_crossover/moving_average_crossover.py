
from decimal import Decimal
import logging

from hummingbot.core.event.events import OrderType
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase

hws_logger = None


class MovingAverageCrossover(StrategyPyBase):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self, exchange, trading_pair, order_amount, market_swing, ma_crossover, sell_markup):
        super().__init__()
        self._exchange = exchange
        self._trading_pair = trading_pair
        self._order_amount = order_amount
        self._market_swing = self.convert_number_to_decimal(market_swing)
        self._ma_crossover_period = ma_crossover
        self._sell_markup = self.convert_number_to_decimal(sell_markup)
        self.add_markets([exchange])
        self._connector_ready = False

    def tick(self, timestamp: float):

        if not self._exchange.ready:
            self._connector_ready = self._exchange.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._exchange.name} not ready. Please wait.")
                return
            else:
                self.logger().info(f"{self._exchange.name} ready. Happy trading!")

    def convert_number_to_decimal(self, number) -> Decimal:
        return Decimal(number) / Decimal("100")
