from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.moving_average_crossover import MovingAverageCrossover
from hummingbot.strategy.moving_average_crossover.moving_average_crossover_config_map import (moving_average_crossover_config_map as c_map)


def start(self):
    try:
        connector = c_map.get("connector").value.lower()
        trading_pair = c_map.get("trading_pair").value
        order_amount = c_map.get("order_amount").value
        market_swing = c_map.get("market_swing").value
        ma_crossover = c_map.get("ma_crossover").value
        sell_markup = c_map.get("sell_markup").value
        cooling_period = c_map.get("cooling_period").value

        self._initialize_markets([(connector, [trading_pair])])
        base, quote = trading_pair.split("-")
        market_info = MarketTradingPairTuple(self.markets[connector], trading_pair, base, quote)

        exchange = self.markets[connector]

        self.strategy = MovingAverageCrossover(exchange=exchange,
                                               market_info=market_info,
                                               trading_pair=trading_pair,
                                               order_amount=order_amount,
                                               market_swing=market_swing,
                                               ma_crossover=ma_crossover,
                                               sell_markup=sell_markup,
                                               cooling_period=cooling_period,
                                               )

    except Exception as e:
        self.notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)