"This class consists valid values for parameters"
class ParamChecker:
    def __init__(self):
        
        # Valid parameters
        self.valid_intervals = ["1m", "5m" , "15m" , "30m" , "1h" , "4h" , "8h" , "12h" , "1d" , "3d" , "1w"]
        self.valid_borsalar = ["binance","binance_futures","cbase"]
        self.grafik_listesi = ["liqmap","futmap","futmap1","futmap2","futmap3","futmap4","futmap5","futmap6", "volplot","cbase"]
        self.valid_futmaps = ["1","2","3","4","5","6"] # We have 6 futmaps. They are separated by these numbers
        
        self.cbase_coin_list = ["BTCUSDT","ETHUSDT"] # valid pairs for coinbase data        
        self.valid_cbase_coins = ["btc","eth","BTC","ETH"] # Valid coins forc oinbase data
        
        # Max values for parameters       
        self.max_candle_adet = 300 # the limit to the amt. of price candles we can provide
        self.max_historical = 1000 # the limit of the oldest historical data that we can proveid
        self.heatmap_seviye = 100 # the limit that is necessary for liqmap calculation
        
    def check_pair(self,parite,coin_list_spot,graph,borsa="binance"):    
        hata = False
        parite = parite.upper()
        parite = parite.replace("USDT","")
        graph = graph.lower()
                  
        if parite != "ETHBTC" and parite+"USDT" not in coin_list_spot: hata = True
            
        elif graph == "cbase": 
            if parite not in self.valid_cbase_coins: hata = True 
        return hata,parite

    def check_borsa(self, graph,borsa):
        hata = False
        if borsa not in self.valid_borsalar:
            hata = True
        else:
            if graph in ["liqmap","oimap","futmap","futplot","lsplot"] and borsa != "binance_futures": # These only works with binance_futures
                hata = True
            elif graph == "cbase" and borsa != "cbase":
                hata = True
                
        return hata