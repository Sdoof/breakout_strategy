#Nick Schmandt (n.schmandt@gmail.com), CloudQuant, 10/31/17

#This is a strategy designed to follow major market movements (up or down). It goes long on stocks that are well above their 
#average from previous days, and short on stocks that are well below.

from cloudquant.interfaces import Strategy
from cloudquant.util import dt_from_muts
import numpy as np

lime_midpoint_limit_buy = "4e69745f-5410-446c-9f46-95ec77050aa5"
lime_midpoint_limit_sell = "23d56e4a-ca4e-47d0-bf60-7d07da2038b7"

end_delay = 20 # in minutes, how long before the end of the day to stop trading.
start_delay = 10 # in minutes, how long after market open before we start trading

index=5 # how many days of highs to average over
purchase_atr_ratio=.33 # what fraction of the atr for a stock to be bought/shorted
sell_atr_ratio=.66 # what fraction of the atr for a stock to be exited from

class breakout_purchase(Strategy):
    @classmethod
    def is_symbol_qualified(cls, symbol, md, service, account):
        
        handle_list = service.symbol_list.get_handle('9a802d98-a2d7-4326-af64-cea18f8b5d61') #this is all stocks on S&P500
        return service.symbol_list.in_list(handle_list,symbol)
        
        #return symbol in ['AAPL', 'EBAY', 'AMZN', 'ORCL', 'WMT']
    
    def __init__(self):  

        self.IsPositionOn = False  # do we have a position on?
        self.entry_price = 0  # estimated price of our position
        self.model_start = 0 # time to start, set in on_start
        self.IsShort=False # are we short?
        self.IsPurchasable=True # OK to purchase? (not repurchasing what we already sold)
    
    def on_finish(self, md, order, service, account):
        pass
    
    def on_minute_bar(self, event, md, order, service, account, bar):
        
        #make sure it's not too late in the day
        if service.system_time < md.market_close_time - service.time_interval(minutes=end_delay, seconds=1):
            
            #gather some statistics
            md_daily=md.bar.daily(start=-index)
            md_high=md_daily.high
            average_high=np.mean(md_high)
            md_low=md_daily.low
            average_low=np.mean(md_low)
            
            bar_1 = bar.minute()
            bar_close = bar_1.close
            
            if len(bar_close)>0 and bar_close[0]!=0:
            
                #if the stock has returned to its normal values, we would consider rentering a position on it.
                if (average_high+purchase_atr_ratio*md.stat.atr)>bar_close[0] and (average_low-purchase_atr_ratio*md.stat.atr)<bar_close[0]:
                    self.IsPurchasable=True

                if self.IsPositionOn == True:
                    # there is a position on, therefore we want to check to see if
                    # we should realize a profit or stop a loss

                    #the stock has dropped too low, exit out of this position
                    if average_high>bar_close[0] or self.entry_price-sell_atr_ratio*md.stat.atr>bar_close[0]:

                        self.IsPositionOn = False
                        # send order; use a variable to accept the order_id that order.algo_buy returns
                        sell_order_id = order.algo_sell(self.symbol, algorithm=lime_midpoint_limit_sell, price=md[self.symbol].L1.bid*.95, intent="exit")
                        print('selling out of {0} at {1} due to stock dropping below average high at {1}'.format(self.symbol, service.time_to_string(service.system_time), bar_close[0]))
                        self.IsPurchasable=False

                    #we've made our target profit, let's back out of the trade now
                    elif self.entry_price+sell_atr_ratio*md.stat.atr<bar_close[0]:

                        self.IsPositionOn = False
                        # send order; use a variable to accept the order_id that order.algo_buy returns
                        sell_order_id = order.algo_sell(self.symbol, algorithm=lime_midpoint_limit_sell, price=md[self.symbol].L1.bid*.95, intent="exit")
                        print('selling out of {0} at {1} due to stock reaching target profit at {2}'.format(self.symbol, service.time_to_string(service.system_time), bar_close[0]))
                        self.IsPurchasable=False

                if self.IsShort == True:
                    # there is a position on, therefore we want to check to see if
                    # we should realize a profit or stop a loss
                    
                    #if the price has climbed a lot, exit out of the position
                    if average_low<bar_close[0] or self.entry_price+sell_atr_ratio*md.stat.atr<bar_close[0]:

                        self.IsShort = False
                        # send order; use a variable to accept the order_id that order.algo_buy returns
                        order_id = order.algo_buy(self.symbol, algorithm=lime_midpoint_limit_sell, price=md[self.symbol].L1.ask*1.05, intent="exit")
                        print('exiting short of {0} at {1} due to rising above average low at {2}'.format(self.symbol, service.time_to_string(service.system_time), bar_close[0]))
                        self.IsPurchasable=False

                    #we have made our profit target, exit out of the trade
                    if self.entry_price-sell_atr_ratio*md.stat.atr>bar_close[0]:

                        self.IsShort = False
                        # send order; use a variable to accept the order_id that order.algo_buy returns
                        order_id = order.algo_buy(self.symbol, algorithm=lime_midpoint_limit_sell, price=md[self.symbol].L1.ask*1.05, intent="exit")
                        print('exiting short of {0} at {1} due to stock dropping below sell point at {2}'.format(self.symbol, service.time_to_string(service.system_time), bar_close[0]))
                        self.IsPurchasable=False

                # we want to have at least a certain amount of time left before entering positions
                if service.system_time > self.model_start:
                    #make sure we're not already in a position and the stock hasn't already been bought and resold recently.
                    if self.IsPositionOn == False and self.IsShort == False and self.IsPurchasable==True:

                        # go long if stock is well above its normal values
                        if (average_high+purchase_atr_ratio*md.stat.atr)<bar_close[0]:
                            print('Purchasing {0} after breakout at {1}, purchased at {2}'\
                                  .format(self.symbol, service.time_to_string(service.system_time), bar_close[0]))
                            order_id = order.algo_buy(self.symbol, algorithm=lime_midpoint_limit_buy, price=1.05*md[self.symbol].L1.ask, intent="init", order_quantity=1000)
                            self.IsPositionOn=True
                            self.entry_price = bar_close[0]

                        # short if the stock is well below its normal values
                        elif (average_low-purchase_atr_ratio*md.stat.atr)>bar_close[0]:
                            print('Shorting {0} after low breakout at {1}, sold at {2}'\
                                  .format(self.symbol, service.time_to_string(service.system_time), bar_close[0]))
                            sell_order_id = order.algo_sell(self.symbol, algorithm=lime_midpoint_limit_sell, intent="init", order_quantity=1000)
                            self.IsShort=True
                            self.entry_price = bar_close[0]
                            
        else:
            
            # close out of our long positions at the end of the day 
            if self.IsPositionOn == True:
                sell_order_id = order.algo_sell(self.symbol, "market", intent="exit")
                self.IsPositionOn = False
                
            # close out of our short positions at the end of the day
            if self.IsShort == True:
                order_id = order.algo_buy(self.symbol, "market", intent="exit")
                self.IsShort = False

    def on_start(self, md, order, service, account):
        
        self.model_start = service.system_time + service.time_interval(minutes=start_delay, seconds=1)
        
© 2017 GitHub, Inc.
