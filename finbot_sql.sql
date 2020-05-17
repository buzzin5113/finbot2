CREATE TABLE STOCK(
    TICKER              TEXT PRIMARY KEY,
    FIGI                TEXT,
    ISIN                TEXT,
    NAME                TEXT,
    LOT                 INTEGER,
    CURRENCY            TEXT,
    IN_STOCK            INTEGER,                            -- 0 нет в портфеле, 1 есть в портфеле
    PRICE_BIDS          REAL,                               -- Спрос (мы продаем) из стакана
    PRICE_ASKS          REAL,                               -- Предложение (мы покупаем)
    PRICE_MAX           REAL,
    PRICE_SELL          REAL,                               -- Цена по который были проданы акции в прошлый раз
    PRICE_LAST          REAL,                               -- Последняя цена с биржи
    YEAR_MAX            REAL,                               -- Максимальная цена за год (get_quote())
    YEAR_MIN            REAL,                               -- Минимальная цена за год (get_quote())
    PE                  REAL,                               -- Отношение стоимоть/прибыль (get_quote())
    PE_FW               REAL,
    PRICE_FW            REAL,
    DIV_DATE            TEXT,                               -- Дата фиксации дивидентов (get_dividends())
    DIV                 REAL,                               -- Сумма дивидентов (get_dividends())
    DIV_PERCENT         REAL,      
    V1                  REAL,
    V2                  REAL,
    V3                  REAL,
    V4                  REAL,
    V5                  REAL,
    V_SUMM              REAL,
    FORBIDDEN           INTEGER
);