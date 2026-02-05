import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logger(name: str):
    logger = logging.getLogger(name)

    # 避免重複添加 Handler
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # 建立格式：[時間] [等級] [檔案名稱:行數] - 訊息
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')

        # --- 輸出到終端機 (Console) ---
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # --- 輸出到檔案 (File Handler) ---
        # 建立 logs 資料夾
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # TimedRotatingFileHandler 設定：
        # when="midnight": 每天午夜自動切換新檔案
        # interval=1: 間隔為 1 天
        # backupCount=0: 關鍵！設為 0 表示「永不刪除」舊檔案
        log_file = os.path.join(log_dir, "app.log")
        file_handler = TimedRotatingFileHandler(log_file,
                                                when="midnight",
                                                interval=1,
                                                backupCount=0,
                                                encoding="utf-8")
        # 設定檔案名稱格式，例如 app.log.2023-10-27
        file_handler.suffix = "%Y-%m-%d"
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
