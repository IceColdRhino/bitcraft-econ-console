import logging
import numpy as np
import pandas as pd

np.seterr(divide="ignore", invalid="ignore")


def price_calc(app, product_id, claim_id=0):
    """Given market data (stored in 'app'), return price modeling for the given product within the given scope."""
    logging.debug(f"Finding price for {product_id} in claim {claim_id}")
    # Grab order data from current standing orders
    all_buys = pd.DataFrame(app.tables["buy_order_state"])
    all_sells = pd.DataFrame(app.tables["sell_order_state"])
    type_map = {"item": 0, "cargo": 1}

    # Optionally filter for a particular claim
    if claim_id != 0:
        all_buys = all_buys[all_buys["claim_entity_id"]==claim_id]
        all_sells = all_sells[all_sells["claim_entity_id"]==claim_id]

    # Filter for a particular item
    item_buys = item_filter(all_buys, product_id)
    item_sells = item_filter(all_sells, product_id)

    # Do a "virtual unpack" of any packed goods
    ratio = 1
    pack = app.pack_lookup.get(product_id)
    if pack is not None:
        pack_id = pack["pair"]
        ratio = pack["ratio"]
        pack_buys = item_filter(all_buys, pack_id)
        pack_sells = item_filter(all_sells, pack_id)

        pack_buys["price_threshold"] = pack_buys["price_threshold"] / ratio
        pack_sells["price_threshold"] = pack_sells["price_threshold"] / ratio
        pack_buys["quantity"] = pack_buys["quantity"] * ratio
        pack_sells["quantity"] = pack_sells["quantity"] * ratio

        # Join dfs together...
        buy_df = pd.concat([item_buys, pack_buys])
        sell_df = pd.concat([item_sells, pack_sells])
    else:
        # or don't.
        buy_df = item_buys.copy()
        sell_df = item_sells.copy()

    # Whittle the dataframe down to just the particular components that matter to me
    buy_df = buy_df[["quantity", "price_threshold"]]
    sell_df = sell_df[["quantity", "price_threshold"]]
    # Group same-priced orders together
    buy_df = buy_df.groupby("price_threshold", as_index=False).sum()
    sell_df = sell_df.groupby("price_threshold", as_index=False).sum()

    # Sort in the "natural" order
    buy_df = buy_df.sort_values("price_threshold", ascending=False, ignore_index=True)
    sell_df = sell_df.sort_values("price_threshold", ascending=True, ignore_index=True)

    # Calculate raw metrics of order book
    # There's probably a better way to do this...
    orders = {}
    orders["buy_order_price"] = np.array(buy_df["price_threshold"])
    orders["sell_order_price"] = np.array(sell_df["price_threshold"])
    orders["buy_order_quantity"] = np.array(buy_df["quantity"])
    orders["sell_order_quantity"] = np.array(sell_df["quantity"])
    orders["buy_value"] = orders["buy_order_price"] * orders["buy_order_quantity"]
    orders["sell_value"] = orders["sell_order_price"] * orders["sell_order_quantity"]
    orders["buy_cumsum_q"] = np.cumsum(orders["buy_order_quantity"])
    orders["sell_cumsum_q"] = np.cumsum(orders["sell_order_quantity"])
    orders["buy_cumsum_v"] = np.cumsum(orders["buy_value"])
    orders["sell_cumsum_v"] = np.cumsum(orders["sell_value"])
    orders["buy_unit_p"] = orders["buy_cumsum_v"] / orders["buy_cumsum_q"]
    orders["sell_unit_p"] = orders["sell_cumsum_v"] / orders["sell_cumsum_q"]

    # Estimate supply/demand curves
    if len(buy_df) == 0:
        # No-orders case:
        # Offer curve flatlines, and sellers fully control the market
        m_b = 0
        b_b = 0
    elif len(buy_df) == 1:
        # One-order case:
        # Parameters are set such that T_b is twice as much as the listed price
        m_b = -(orders["buy_cumsum_v"][0]) / (
            orders["buy_unit_p"][0] - (2 * orders["buy_unit_p"][0])
        )
        b_b = -(orders["buy_cumsum_v"][0] + (m_b * orders["buy_unit_p"][0]))
    else:
        # General case:
        # Offer curve is the steepest line that just barely "contains" all orders
        # Some degree of choice here - but steepest means that the order closest to the spread is most influential
        m_options = (orders["buy_cumsum_v"] - orders["buy_cumsum_v"][0]) / (
            orders["buy_unit_p"] - orders["buy_unit_p"][0]
        )
        buy_index = np.nanargmax(-m_options)
        m_b = -m_options[buy_index]
        b_b = -(orders["buy_cumsum_v"][0] + (m_b * orders["buy_unit_p"][0]))
    C_b = m_b
    T_b = -b_b / (m_b + 1e-12)

    if len(sell_df) == 0:
        # No-orders case:
        # Offer curve flatlines, and buyers fully control the market
        m_s = 0
        b_s = 0
    elif len(sell_df) == 1:
        # One-order case:
        # Parameters are set such that T_s is half as much as the listed price
        m_s = (orders["sell_cumsum_v"][0]) / (
            orders["sell_unit_p"][0] - (orders["sell_unit_p"][0] / 2)
        )
        b_s = orders["sell_cumsum_v"][0] - (m_s * orders["sell_unit_p"][0])
    else:
        # General case:
        # Offer curve is the steepest line that just barely "contains" all orders
        m_options = (orders["sell_cumsum_v"] - orders["sell_cumsum_v"][0]) / (
            orders["sell_unit_p"] - orders["sell_unit_p"][0]
        )
        sell_index = np.nanargmax(m_options)
        m_s = m_options[sell_index]
        b_s = orders["sell_cumsum_v"][0] - (m_s * orders["sell_unit_p"][0])
    C_s = m_s
    T_s = -b_s / (m_s + 1e-12)

    if C_b + C_s == 0:
        # Zero-division case that should only come up when a product has no market orders at all
        P_e = 0
    else:
        P_e = ((C_b * T_b) + (C_s * T_s)) / (C_b + C_s)

    # There's probably a cleaner way to pack and return this...
    orders["C_b"] = C_b
    orders["C_s"] = C_s
    orders["T_b"] = T_b
    orders["T_s"] = T_s
    orders["P_e"] = P_e

    logging.debug(f"Estimate price for {product_id}: {P_e:,.3f}")
    return orders


def item_filter(df, product_id):
    """Filters a pandas dataframe for a given item"""
    type_map = {"item": 0, "cargo": 1}

    item_type, item_id = product_id.split("_")
    item_type = type_map[item_type]
    item_id = int(item_id)
    df = df[(df["item_type"] == item_type) & (df["item_id"] == item_id)]
    return df
