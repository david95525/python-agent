import yfinance as yf
from langchain.tools import tool
from app.utils.logger import setup_logger
from duckduckgo_search import DDGS

logger = setup_logger("FinancialTools")


@tool
def get_market_news(query: str) -> str:
    """
    獲取與市場或特定股票相關的最新財經新聞與情緒。
    """
    logger.info(f"[Tool: Search] 正在搜尋新聞: {query}")
    try:
        search_query = query
        if ".TW" in query.upper():
            # 簡單映射：2330 -> 台積電, 2454 -> 聯發科 (或直接拿掉 .TW 搜)
            search_query = f"{query.split('.')[0]} 股票 新聞"
        with DDGS() as ddgs:
            # 搜尋財經相關新聞
            results = [r for r in ddgs.text(search_query, max_results=5)]

            if not results:
                return f"找不到關於 {query} 的相關新聞。"

            # 格式化輸出
            formatted_results = "\n".join([
                f"- {r['title']}: {r['body']} (連結: {r['href']})"
                for r in results
            ])
            return formatted_results
    except Exception as e:
        logger.error(f"新聞搜尋失敗: {e}")
        return f"無法獲取 {query} 的相關新聞。"


# 股價工具 (結構化數據)
@tool
def get_stock_price(symbol: str) -> str:
    """
    獲取指定股票代號（Symbol）的最新股價、漲跌幅與貨幣。
    範例：'AAPL' (美股), '2330.TW' (台股)。
    """
    logger.info(f"[Tool: Finance] 正在抓取股價: {symbol}")
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1d")
        if hist.empty:
            return f"找不到 {symbol} 的數據，請檢查代號是否正確。"

        current_price = hist['Close'].iloc[-1]
        prev_close = stock.info.get('previousClose', current_price)
        change = ((current_price - prev_close) / prev_close) * 100
        currency = stock.info.get('currency', 'USD')

        return f"{symbol} 當前價: {current_price:.2f} {currency} (當日漲跌: {change:+.2f}%)"
    except Exception as e:
        logger.error(f"股價獲取失敗: {e}")
        return f"無法獲取 {symbol} 的股價數據。"
