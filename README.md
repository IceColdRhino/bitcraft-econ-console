# BitCraft Econ Console
This tool uses a [public mirror](https://relay.bitcraftsync.app/) of BitCraft Online game data to find profitable opportunities for economically-minded players, ~~with live updates~~! Ideally, this also opens up possibilities for efficient market-based collaboration between players, rather than the common method of relying on shared storage and donations. If a smith places a buy order for logs, it immediately signals that demand to a forester using this tool, rather than relying on someone in-game just happening to come across the buy order.

## Features
### Prices
The tool opens by default on a live-updating roster of all products in-game. [Prices are estimated](#####whats-the-deal-with-the-prices) based on current buy orders and sell orders on the market, and displayed in a sortable table. You can double-click on a row to get a window popup of that product, providing more detail on the item itself and the market conditions for that item.

### Crafting: WIP
In the future, this tool will look at the price in the roster, and calculates what crafting opportunities are profitable.

### Shipping: WIP
In the future, this tool will calculate profitable shipping opportunities.

### Map
This tool displays shipping opportunities and profitable trade routes in a graphical format, for those that want to make a living as traveling merchants and chain voyages together.

Eventually, I plan to have a live map, drawing on the same data as the other tools. However, for the time being, it instead uses [this public map](https://bitcraftmap.com/?gistId=45e77efd77b455020add8581eaaf6dc3) that updates roughly hourly, drawing on data from the [BitJita](https://bitjita.com/) API.  

Lines are drawn on the map between claims where a profitable trade could be made. The yellow half of the line is on the exporter end, the blue half of the line is on the importer end. Travel to a claim with many yellow lines emanating from it if you want a [shipping](###shipping) starting point with many profitable opportunities. Line opacity is based on the profit per distance of the route. Any route with a profit per distance that's less than 10% of the best opportunity currently available isn't drawn. Click on a line to see the particular goods that make up that opportunity.

## FAQ
##### What's the deal with the prices?
The prices used in this tool are not intended to be the "*best*" prices you could possibly have for making a trade. They also have no inclination of what the price "*should*" be, based on labor or material costs. Rather, they're an estimate of a common "market price" based on currently-active market orders. Ideally, you should be able to get an order filled at the estimated price, whether that's a buy order or a sell order. In simple terms, you can think of the estimated price as just splitting the spread. If you place an order at the estimated market price, then the spread will narrow, and as the spread gets narrower the estimate gets better.

In more complicate terms, the price is based on a theoretical "offer curve" derived from a Cobb-Douglas Utility Function. The set of sell orders is placed in a coordinate space of "cumulative value" on the y-axis and "mean unit price" on the x-axis, and the offer curve is a `y=mx+b` line that rests on *top* of that set of points (it is *not* a line of best fit). That coordinate space is converted so that the x-axis remains "unit price", while the y-axis becomes "Cumulative Quantity", and the offer curve takes the form `Q(p) = C * (1 - T/p)`. In (iffy and simplified) theory, the market is willing to provide ***up to*** `Q` goods at unit price `p`, so all the current orders will lie somewhere below that line. The procedure is repeated for buy orders, with signs flipped as appropriate, and the estimated market price is the point where the buy and sell offer curves intersect.

##### Why just crafting and no gathering?
A much older (and simpler) version of this tool *did* incorporate gathering, hunting, and slaying. This was always iffy, given the movement time inherently associated with these activities. The increased prevalence of prospecting activities, placeables, gathering skills, etc. makes this an even more problematic venture. My hope is that planned product filtering features will allow gatherers to make their own judgements on what resources are worthwhile to gather, with the tool still providing a useful live look at the market.
