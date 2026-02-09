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
            # 優化搜尋關鍵字，增加「財經」或「股價」字眼能讓搜尋更精準
            search_query = f"{query.split('.')[0]} 股票 財經 新聞"

        ddgs = DDGS(timeout=10)

        # 轉換為 list 前先確保有拿到 generator
        results = list(ddgs.text(search_query, region="tw-tzh", max_results=5))

        if not results:
            return f"找不到關於 {query} 的相關新聞。"

        # 格式化輸出
        formatted_results = "\n".join([
            f"- {r.get('title', '無標題')}: {r.get('body', '無內容')} (連結: {r.get('href', '#')})"
            for r in results
        ])
        return formatted_results

    except Exception as e:
        logger.error(f"[Critical] 新聞搜尋崩潰: {str(e)}")
        return f"目前無法獲取 {query} 的即時新聞（搜尋引擎繁忙），請根據歷史數據進行分析。"


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
