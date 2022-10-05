from decimal import Decimal
from hummingbot.client.config.config_validators import validate_decimal
from hummingbot.client.config.config_var import ConfigVar


# Returns a market prompt that incorporates the connector value set by the user
def market_prompt() -> str:
    connector = moving_average_crossover_config_map.get("connector").value
    return f"Enter the token trading pair on {connector} >>> "

# Order amount


def order_amount_prompt() -> str:
    trading_pair = moving_average_crossover_config_map["trading_pair"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {quote_asset} per order? >>> "


# List of parameters defined by the strategy
moving_average_crossover_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="moving_average_crossover",
                  ),
    "connector":
        ConfigVar(key="connector",
                  prompt="Enter the name of the exchange >>> ",
                  prompt_on_new=True,
                  ),
    "trading_pair": ConfigVar(
        key="trading_pair",
        prompt=market_prompt,
        prompt_on_new=True,
        ),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt=order_amount_prompt,
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
                  prompt_on_new=True,
                  ),
    "market_swing":
        ConfigVar(key="market_swing",
                  prompt="Market downturn swing percentage (Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True,
                  ),
    "ma_crossover":
        ConfigVar(key="ma_crossover",
                  prompt="buy when the price drops below x days moving average (Enter days) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, min_value=Decimal("1"), inclusive=False),
                  prompt_on_new=True),
    "sell_markup":
        ConfigVar(key="sell_markup",
                  prompt="Profit markup percentage (Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True,
                  ),
}
