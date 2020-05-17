"""
Финансовый бот.
Рабоча через API Tinkoff
"""

import xxx as secret

from iexfinance.stocks import Stock as iex_stock
from openapi_client import openapi

import telegram
import sqlite3
import time
import random
import datetime

class Bond:

    debug = True

    auth_tinkoff_token = ''
    auth_telegram_token = ''
    auth_iex_token = ''

    auth_tinkoff = ''

    balance_rub = 0
    balance_usd = 0
    balance_eur = 0

    currency_allow = []

    database = ''
    database_path = './finbot.db'

    def __init__(self):
        self.auth_tinkoff_token = secret.token
        self.auth_telegram_token = secret.tokentel
        self.auth_iex_token = secret.tokeniex

        self._auth_tinkoff()
        self._db_connect()

    def _auth_tinkoff(self):
        """
        Авторизуемся в API Tinkoff
        """
        self.auth_tinkoff = openapi.api_client(secret.token)


    def _db_connect(self):
        """
        Подключаем БД            
        """
        self.database = sqlite3.connect(self.database_path)

    
    def db_fetchall(self, sql):
        """
        Извлечение данных из БД. Возвращает все строки в виде списка.
        """
        cursor = self.database.cursor()
        cursor.execute(sql)
        data = cursor.fetchall()
        self.database.commit()
        return data

    
    def db_executesql(self, sql):
        """
        Выполение запроса котрый ничего не возвращает
        """
        cursor = self.database.cursor()
        cursor.execute(sql)
        self.database.commit()


    def balance_get(self):
        """
        Получим баланс
        """
        try:
            data = self.auth_tinkoff.portfolio.portfolio_currencies_get()
            for llist in data.payload.currencies:
                if llist.currency == 'RUB': self.balance_rub = llist.balance
                if llist.currency == 'USD': self.balance_usd = llist.balance
                if llist.currency == 'EUR': self.balance_eur = llist.balance
            
            if self.debug:
                print('Баланс RUB: {}'.format(self.balance_rub))
                print('Баланс USD: {}'.format(self.balance_usd))
                print('Баланс EUR: {}'.format(self.balance_eur))
        except Exception as e:
            self.telegram_send_text('Ошибка при запросе баланса')
            self.telegram_send_text(e)


    def telegram_send_text(self, msg):
        """
        Отправка сообщения в телеграмм
        """

        bot = telegram.Bot(self.auth_telegram_token)
        try:
            bot.sendMessage('198182712', text=msg,  parse_mode=telegram.ParseMode.HTML)
            time.sleep(1)
            return True
        except telegram.TelegramError as error_text:
            print('Ошибка отправки текстового сообщения в телеграм')
            print(error_text)
            return False


class Stock(Bond):

    stock_price_now = 80
    portfolio_stock = []
    portfolio_stock_instance = {}

    def __init__(self):
        self.currency_allow = ['USD']
        super(Stock, self).__init__()

    
    def stock_buy(self):
        """
        Покупка акций
        """
        print('Пробуем купить акции')

        while self.balance_usd > 30:
            if self.balance_usd > 55:
                self.stock_price_now = self.stock_price_now * 0.95
            else:
                self.stock_price_now = self.balance_usd - 7

            sql = """
                  SELECT 
                      FIGI, TICKER, PRICE_LAST * LOT
                  FROM 
                      STOCK
                    WHERE
                        CURRENCY = 'USD' and PRICE_LAST * LOT < {}
                        AND IN_STOCK = 0 and PRICE_LAST < PRICE_SELL * 0.988 
                        AND V_SUMM > 0.5
                    ORDER BY V_SUMM DESC
                    LIMIT 10
                """.format(self.stock_price_now)
            data = self.db_fetchall(sql)
            random.shuffle(data)

            # выбрали акцию
            self.portfolio_stock_instance['figi'] = data[0][0]
            self.portfolio_stock_instance['ticker'] = data[0][1]
            # Данные обновили
            self.stock_price_get()


            if self.debug:
                for llist in data:
                    print(llist)

            if not llist:
                print('Акций не нашлось')
                break

            #Проверим, что разница между покупкой и продажей не слишком большая
            if ((self.portfolio_stock_instance['bids']/self.portfolio_stock_instance['asks']) - 1) * self.portfolio_stock_instance['bids'] < 0.5:

                stock_count = int(self.stock_price_now / self.portfolio_stock_instance['asks'])

                msg = """
                🍭 Покупаю {} в количестве {} по {} 
                На сумму {}
                """.format(self.portfolio_stock_instance['ticker'],
                        stock_count,
                        self.portfolio_stock_instance['asks'],
                        self.portfolio_stock_instance['asks'] * stock_count
                                                                                
                )
                self.telegram_send_text(msg)

                try:
                    request = { "lots": stock_count, "operation": "Buy" }
                    self.auth_tinkoff.orders.orders_market_order_post(self.portfolio_stock_instance['figi'], request)


                    sql = """
                            UPDATE
                                STOCK
                            SET 
                                IN_STOCK = 1,
                                PRICE_SELL = 0,
                                PRICE_MAX = 0
                            WHERE
                                TICKER = '{}'
                        """.format(self.portfolio_stock_instance['ticker'])
                    self.db_executesql(sql)
                    
                    self.balance_get()
                                
                    time.sleep(2)
                except:
                    self.telegram_send_text('Ошибка при покупке акций')
            
            else:
                self.telegram_send_text('Слишком большая разница между покупкой и продажей')
    
    def stock_sell(self):
        """
        Расчет возможности продажи акций
        """
        # Обновим данные по акциям
        self.stock_portfolio()
        # Для каждой позиции в портфолио запустим проверку
        for self.portfolio_stock_instance in self.portfolio_stock:
            self.stock_sell_check()
        
    
    def stock_sell_check(self):
        """
        Проверяем конкретную акцию на возможность продажи
        """
        print('Проверяем возможность продажи {}'.format(self.portfolio_stock_instance['ticker']))
        # Декомпозиция данных ценной бумаги
        # Обновляем текущую цену покупки и продажи
        self.stock_price_get()

        # Узнаем максимальную цену
        self.stock_price_max_get()

        # Проверяем условие для продажи

        if1 = self.portfolio_stock_instance['bids'] > (self.portfolio_stock_instance['price_buy'] * 1.011) 
        if2 = self.portfolio_stock_instance['bids'] < self.portfolio_stock_instance['price_max']
        try:
            if3 = (self.portfolio_stock_instance['price_max'] - self.portfolio_stock_instance['price_buy']) / (self.portfolio_stock_instance['bids'] - self.portfolio_stock_instance['price_buy']) > 1.2
        except:
            if3 = False

        if self.debug: print(if1, if2, if3)

        if  if1 and if2 and if3:
            print('Продаем - {}'.format(self.portfolio_stock_instance['name']))
            self.stock_sell_order()
        else:
            print('Не продаем {}'.format(self.portfolio_stock_instance['name']))


    def stock_sell_order(self):
        """
        Создаем запрос на продажу акций
        """
        request = { "lots": self.portfolio_stock_instance['lots'], "operation": "Sell" }
        try:
            self.auth_tinkoff.orders.orders_market_order_post(self.portfolio_stock_instance['figi'], request)        
            # Если запрос успешно отправлен, регистрируем в БД, отправляем сообщение в инстаграм
            # Обновим цену продажи в БД
            sql = """
                    UPDATE
                        STOCK
                    SET
                        PRICE_SELL = {}
                    WHERE
                        FIGI = '{}'
                """.format(self.portfolio_stock_instance['bids'],
                            self.portfolio_stock_instance['figi']
                            )
            self.db_executesql(sql)

            # Обнулим максимум в БД
            sql = """
                UPDATE
                    STOCK
                SET 
                    PRICE_MAX = 0,
                    IN_STOCK = 0
                WHERE 
                    FIGI = '{}'
                """.format(self.portfolio_stock_instance['figi'])
            self.db_executesql(sql)
            # Отправка сообщения о продаже в телеграм
            msg = """
            ✔️ Продаем {} {} - {} штук по {}
            Ориентировочная прибыль {}$
            """.format(self.portfolio_stock_instance['ticker'],
                    self.portfolio_stock_instance['name'],
                    self.portfolio_stock_instance['lots'],
                    self.portfolio_stock_instance['bids'],
                    round(((self.portfolio_stock_instance['bids']/self.portfolio_stock_instance['price_buy']) - 1)  * self.portfolio_stock_instance['price_buy'], 3)
                    )
            self.telegram_send_text(msg)
        except:
            self.telegram_send_text('Сбой при продаже акций')


    def stock_price_max_get(self):
        """
        Узнаем значение максимальной цены для акции
        """
        # Запросим из БД и сохраним
        sql = """
              SELECT
                PRICE_MAX
              FROM
                STOCK
              WHERE TICKER = '{}'
              """.format(self.portfolio_stock_instance['ticker'])
        data = self.db_fetchall(sql)
        self.portfolio_stock_instance['price_max'] = data[0][0]

        if self.portfolio_stock_instance['bids'] > self.portfolio_stock_instance['price_max']:
            print('Новый максимум для {} - {} {}'.format(self.portfolio_stock_instance['ticker'], 
                                                         self.portfolio_stock_instance['bids'], 
                                                         self.portfolio_stock_instance['currency']))

            self.portfolio_stock_instance['price_max'] = self.portfolio_stock_instance['bids']

            # Обновим в БД
            sql = """
                  UPDATE 
                    STOCK 
                  SET
                    PRICE_MAX = {}
                  WHERE
                    TICKER = '{}';
                  """.format(self.portfolio_stock_instance['price_max'],
                             self.portfolio_stock_instance['ticker'])
            
            self.db_executesql(sql)

            msg = """
            ⚡Новый максимум для {} - {}
            Стоимость: {} {}
            Разница с изначальной стоимостью: {}%
            """.format(self.portfolio_stock_instance['ticker'], self.portfolio_stock_instance['name'],
                       self.portfolio_stock_instance['price_max'], self.portfolio_stock_instance['currency'],
                       round(((self.portfolio_stock_instance['price_max']/self.portfolio_stock_instance['price_buy']) - 1)  * 100, 3))
            self.telegram_send_text(msg)

    
    def stock_price_get(self):
        """
        Узнаем текущую цену из стакана
        """
        try:
            data = self.auth_tinkoff.market.market_orderbook_get(self.portfolio_stock_instance['figi'], 1)

            try:
                self.portfolio_stock_instance['asks'] = data.payload.asks[0].price
            except:
                self.portfolio_stock_instance['asks'] = 999999
            try:
                self.portfolio_stock_instance['bids'] = data.payload.bids[0].price
            except:
                self.portfolio_stock_instance['bids'] = 0.01
            self.portfolio_stock_instance['price_last'] = data.payload.last_price

            if self.debug: print('Buy: ' + str(self.portfolio_stock_instance['price_buy']) + ' Asks: ' + str(self.portfolio_stock_instance['asks']) + ' Bids' + str(self.portfolio_stock_instance['bids']))

            # Сохраним данные в БД, вдруг пригодятся
            sql = """
                    UPDATE
                        STOCK
                    SET
                        PRICE_ASKS = {},
                        PRICE_BIDS = {},
                        PRICE_LAST = {}
                    WHERE
                        FIGI = '{}'
                """.format(self.portfolio_stock_instance['asks'],
                            self.portfolio_stock_instance['bids'],
                            self.portfolio_stock_instance['price_last'],
                            self.portfolio_stock_instance['figi']
                            )
            self.db_executesql(sql)

            time.sleep(0.5)
        except Exception as e:
            self.telegram_send_text('Ошибка при запросе стакана')
            self.telegram_send_text(e)


    def stock_portfolio(self):
        """
        Акции в наличии
        """
        print('Обновляем портфолио')
        data = self.auth_tinkoff.portfolio.portfolio_get()
        
        if self.debug: print(data)

        self.portfolio_stock = []

        for llist in data.payload.positions:
            if llist.instrument_type == 'Stock' and llist.average_position_price.currency in self.currency_allow:
                self.portfolio_stock_instance = {}
                self.portfolio_stock_instance['figi'] = llist.figi
                self.portfolio_stock_instance['isin'] = llist.isin
                self.portfolio_stock_instance['name'] = llist.name
                self.portfolio_stock_instance['ticker'] = llist.ticker
                self.portfolio_stock_instance['lots'] = llist.lots
                self.portfolio_stock_instance['price_buy'] = llist.average_position_price.value
                self.portfolio_stock_instance['yield'] = llist.expected_yield.value / llist.lots
                self.portfolio_stock_instance['currency'] = llist.expected_yield.currency

                if self.debug:
                    print('portfolio_stock_instance')
                    print(self.portfolio_stock_instance)
            
                self.portfolio_stock.append(self.portfolio_stock_instance)

        if self.debug:
            print('portfolio_stock:')
            print(self.portfolio_stock)


    def stock_update_data(self):
        """
        Ищем новые акции и добавляем в БД
        """
        print('Обновляем список акций, ищем новые')
        sql = """
            SELECT
                TICKER
            FROM
                STOCK;
            """
        data_db = self.db_fetchall(sql)

        data_tinkoff = self.auth_tinkoff.market.market_stocks_get()
        for llist in data_tinkoff.payload.instruments:
            found = 0
            for db_row in data_db:
                if db_row[0] == llist.ticker:
                    found = 1
            if found < 1:
                # Новая бумага, добавляем в БД
                print('Новая ценная бумага {}'.format(llist.ticker))
                sql = """
                    INSERT INTO
                        STOCK (
                            TICKER, FIGI, ISIN, NAME, LOT, CURRENCY, 
                            PRICE_BIDS, PRICE_ASKS, PRICE_MAX, PRICE_SELL, PRICE_LAST, YEAR_MAX, YEAR_MIN, PE, PE_FW, PRICE_FW, 
                            DIV_DATE, DIV, DIV_PERCENT, V1, V2, V3, V4, V5, V_SUMM, FORBIDDEN    
                        )
                    VALUES (
                        "{}", "{}", "{}", "{}", {}, "{}", 
                        0, 0, 0, 999999, 0, 0, 0, 0, 0, 0
                        0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                    );
                    """.format(
                        llist.ticker,
                        llist.figi,
                        llist.isin,
                        llist.name,
                        llist.lot,
                        llist.currency 
                    )
                self.db_executesql(sql)
                msg = """
                🌍
                Новая ценная бумага.
                {} - {}
                """.format(llist.ticker, llist.name)
                self.telegram_send_text(msg)
            else:
                # Обновим данные по существующей в БД бумаге
                sql = """
                    UPDATE 
                        STOCK 
                    SET
                        TICKER = "{}",
                        ISIN = "{}",
                        NAME = "{}",
                        LOT = "{}",
                        CURRENCY = "{}"
                    WHERE 
                        FIGI = "{}"
                    ;
                    """.format(
                        llist.ticker,
                        llist.isin,
                        llist.name,
                        llist.lot,
                        llist.currency,
                        llist.figi
                    )
                self.db_executesql(sql)
            
            # Обновим цены акции
            self.portfolio_stock_instance['figi'] = llist.figi
            self.stock_price_get()
                

    def stock_update_rating(self):
        """
        Обновляем рейтинг акций.
        Всего 5 рейтингов + сумма
        """
        # Загрузка данных
        # self.stock_update_rating_load()
        
        # Расчет рейтинга
        sql = """
                SELECT
                    TICKER
                FROM 
                    STOCK;
              """
        data = self.db_fetchall(sql)
        for llist in data:
            self.portfolio_stock_instance['ticker'] = llist[0]
            print('Расчет рейтинга для "{}"'.format(self.portfolio_stock_instance['ticker']))

            self.stock_update_rating_v1()
            self.stock_update_rating_v2()
            self.stock_update_rating_v3()
            self.stock_update_rating_v4()
            self.stock_update_rating_v5()
            self.stock_update_rating_v_summ()


    def stock_update_rating_load(self):
        """
        Загрузка данных для рейтинга
        """
        sql = """
              SELECT 
                TICKER, FIGI
              FROM
                STOCK
              WHERE
                CURRENCY  = 'USD' AND FORBIDDEN = 0
              ORDER BY 1
              """
        data = self.db_fetchall(sql)

        for llist in data:
            print('Обновление данных для ' + str(llist[0]))

            self.portfolio_stock_instance['ticker'] = llist[0]
            self.portfolio_stock_instance['figi'] = llist[1]

            stock_data = iex_stock(llist[0], token=self.auth_iex_token)
            list_stock_data = stock_data.get_quote()
            
            if self.debug: print(list_stock_data)

            self.portfolio_stock_instance['year_max'] = list_stock_data['week52High']
            self.portfolio_stock_instance['year_min'] = list_stock_data['week52Low']
            self.portfolio_stock_instance['pe'] = list_stock_data['peRatio']

            if self.portfolio_stock_instance['year_max'] == None: self.portfolio_stock_instance['year_max'] = 0
            if self.portfolio_stock_instance['year_min'] == None: self.portfolio_stock_instance['year_min'] = 0
            if self.portfolio_stock_instance['pe'] == None: self.portfolio_stock_instance['pe'] = 0

            self.portfolio_stock_instance['figi'] = llist[1]
            self.stock_price_get()
            if self.portfolio_stock_instance['asks'] == None: self.portfolio_stock_instance['asks']  = 0.01

            stock_data = iex_stock(llist[0], token=self.auth_iex_token)
            list_stock_data = stock_data.get_dividends(	range='3m')
            
            try:
                self.portfolio_stock_instance['div_date'] = list_stock_data[0]['exDate']
            except:
                self.portfolio_stock_instance['div_date'] = '9999-01-01'
            try:    
                self.portfolio_stock_instance['div'] = float(list_stock_data[0]['amount'])
            except:
                self.portfolio_stock_instance['div'] = 0.0
            try:
                self.portfolio_stock_instance['div_percent'] = round((self.portfolio_stock_instance['div']/(self.portfolio_stock_instance['last_price'] / 100))* 4, 2)
            except:
                self.portfolio_stock_instance['div_percent'] = 0.0
            if self.portfolio_stock_instance['div_date'] == None: self.portfolio_stock_instance['div_date'] = '9999-01-01'
            if self.portfolio_stock_instance['div'] == None: self.portfolio_stock_instance['div'] = 0.0

            # Дополнительно обновим asks, bids, price_last
            self.stock_price_get

            if self.debug: print(self.portfolio_stock_instance)

            sql = """
                    UPDATE
                        STOCK
                    SET
                        YEAR_MAX = {},
                        YEAR_MIN = {},
                        PE = {},
                        PRICE_ASKS = {},
                        DIV_DATE = '{}',
                        DIV = {},
                        DIV_PERCENT = {}
                    WHERE
                        TICKER = '{}'
                    ;
                  """.format(self.portfolio_stock_instance['year_max'],
                             self.portfolio_stock_instance['year_min'],
                             self.portfolio_stock_instance['pe'],
                             self.portfolio_stock_instance['asks'],
                             self.portfolio_stock_instance['div_date'],
                             self.portfolio_stock_instance['div'],
                             self.portfolio_stock_instance['div_percent'],
                             self.portfolio_stock_instance['ticker']
                            )
            self.db_executesql(sql)


    def stock_update_rating_v1(self):
        """
        Расчет V1
        """
        #vK1 = ((vTarget - vPrice) / (vPrice / 100)) * 0.02
        #if vK1 > 2:
        #    vK1 = 2
        #if vK1 < 0:
        #    vK1 = 0
        self.portfolio_stock_instance['v1'] = 0

        sql = """
                UPDATE
                    STOCK
                SET
                    V1 = {}
                WHERE
                    TICKER = '{}'
              """.format(self.portfolio_stock_instance['v1'],
                         self.portfolio_stock_instance['ticker']
                        )
        self.db_executesql(sql)

        print('\t\tV1   : {}'.format(self.portfolio_stock_instance['v1']))


    def stock_update_rating_v2(self):
        """
        Расчет V2
        """
        sql = """
                SELECT 
                    DIV_PERCENT
                FROM
                    STOCK 
                WHERE TICKER = '{}'
              """.format(self.portfolio_stock_instance['ticker'])
        data = self.db_fetchall(sql)

        self.portfolio_stock_instance['div_percent'] = data[0][0]
        
        self.portfolio_stock_instance['v2'] = (self.portfolio_stock_instance['div_percent'] - 2) * (0.5 / 8)
        if self.portfolio_stock_instance['v2'] > 0.8:
            self.portfolio_stock_instance['v2'] = 0.8
        if self.portfolio_stock_instance['v2'] < 0:
            self.portfolio_stock_instance['v2'] = 0

        self.portfolio_stock_instance['v2'] = round(self.portfolio_stock_instance['v2'], 3)

        sql = """
                UPDATE
                    STOCK
                SET
                    V2 = {}
                WHERE
                    TICKER = '{}'
              """.format(self.portfolio_stock_instance['v2'],
                         self.portfolio_stock_instance['ticker']
                        )
        self.db_executesql(sql)

        print('\t\tV2   : {}'.format(self.portfolio_stock_instance['v2']))


    def stock_update_rating_v3(self):
        """
        Расчет V3
        """
        sql = """
                SELECT
                    PE
                FROM
                    STOCK
                WHERE
                    TICKER = '{}';
              """.format(self.portfolio_stock_instance['ticker'])
        data = self.db_fetchall(sql)

        self.portfolio_stock_instance['pe'] = data[0][0]

        self.portfolio_stock_instance['v3'] = 1 - ((self.portfolio_stock_instance['pe'] - 5) * (1 / 15))
        if self.portfolio_stock_instance['v3'] > 1: 
            self.portfolio_stock_instance['v3'] = 1
        if self.portfolio_stock_instance['v3'] < 0:
            self.portfolio_stock_instance['v3'] = 0
        
        self.portfolio_stock_instance['v3'] = round(self.portfolio_stock_instance['v3'], 3)

        sql = """
                UPDATE
                    STOCK
                SET V3 = {}
                WHERE
                    TICKER = '{}';
              """.format(self.portfolio_stock_instance['v2'],
                         self.portfolio_stock_instance['ticker']
                        )
        self.db_executesql(sql)

        print('\t\tV3   : {}'.format(self.portfolio_stock_instance['v3']))


    def stock_update_rating_v4(self):
        """
        Расчет V4
        """
        # vK4 = 0.5 - ((vFPE - 5) * (1 / 30))
        # if vK4 > 0.5:
        #     vK4 = 0.5
        # if vK4 < 0:
        #     vK4 = 0        
        self.portfolio_stock_instance['v4'] = 0

        sql = """
                UPDATE
                    STOCK
                SET
                    V4 = {}
                WHERE
                    TICKER = '{}'
              """.format(self.portfolio_stock_instance['v4'],
                         self.portfolio_stock_instance['ticker']
                        )
        self.db_executesql(sql)

        print('\t\tV4   : {}'.format(self.portfolio_stock_instance['v4']))


    def stock_update_rating_v5(self):
        """
        Расчет V5
        """

        sql = """
                SELECT
                    YEAR_MAX, YEAR_MIN
                FROM
                    STOCK
                WHERE TICKER = '{}'
              """.format(self.portfolio_stock_instance['ticker'])
        data = self.db_fetchall(sql)
        
        self.portfolio_stock_instance['year_max'] = data[0][0]
        self.portfolio_stock_instance['year_min'] = data[0][1]

        sql = """
                SELECT 
                    PRICE_LAST
                FROM
                    STOCK
                WHERE 
                    TICKER = '{}';
              """.format(self.portfolio_stock_instance['ticker'])
        data = self.db_fetchall(sql)
        self.portfolio_stock_instance['price_last'] = data[0][0]
        
        v1 = self.portfolio_stock_instance['price_last'] - (self.portfolio_stock_instance['year_min'] + (self.portfolio_stock_instance['year_max'] - self.portfolio_stock_instance['year_min']) * 0.5)
        if v1 < 0:
            v1 = v1 * -1
        v2 = (self.portfolio_stock_instance['year_max'] - self.portfolio_stock_instance['year_min']) * 0.5 * 0.01
        try:
            self.portfolio_stock_instance['v5'] = 1 - ((v1 / v2) * 0.01)
        except:
            self.portfolio_stock_instance['v5'] = 0

        self.portfolio_stock_instance['v5'] = round(self.portfolio_stock_instance['v5'], 3)

        sql = """
                UPDATE 
                    STOCK
                SET 
                    V5 = {} 
                WHERE
                    TICKER = '{}';
              """.format(self.portfolio_stock_instance['v5'],
                         self.portfolio_stock_instance['ticker']
                        )
        self.db_executesql(sql)

        print('\t\tV5   : {}'.format(self.portfolio_stock_instance['v5']))


    def stock_update_rating_v_summ(self):
        """
        Сумма всех рейтингов
        """
        self.portfolio_stock_instance['v_summ'] = self.portfolio_stock_instance['v1'] + \
                                                  self.portfolio_stock_instance['v2'] + \
                                                  self.portfolio_stock_instance['v3'] + \
                                                  self.portfolio_stock_instance['v4'] + \
                                                  self.portfolio_stock_instance['v5']

        self.portfolio_stock_instance['v_summ'] = round(self.portfolio_stock_instance['v_summ'], 3)   
        
        sql = """
                UPDATE
                    STOCK
                SET
                    V_SUMM = {}
                WHERE
                    TICKER = '{}'
              """.format(self.portfolio_stock_instance['v_summ'],
                         self.portfolio_stock_instance['ticker']
                        )
        self.db_executesql(sql)

        print('\t\tV_SUMM: {}'.format(self.portfolio_stock_instance['v_summ']))


def main():
    print('Starting...')
    bond = Stock()

    # Основной цикл
    #bond.stock_update_data() 
    while True:
        # Выполняем только в рабочее время биржи 16:30 - 23:00 МСК (TODO)
        start_time = 16*60 + 31         # Время начала 16:31
        end_time = 22*60 + 59           # Время окончания 22:59
        current_time =  datetime.datetime.now().hour*60 +datetime.datetime.now().minute
        
        if start_time <= current_time and end_time >= current_time:
            bond.balance_get()
            bond.stock_sell()
            if bond.balance_usd > 30:
                # bond.stock_update_data()        # Обновим список акций (новые и обновим параметры существующих)
                # bond.stock_update_rating()      # Обновление рейтинга
                bond.stock_buy()
            else:
                print('Не на что покупать')
        else:
            print('Время не наступило')

        # Пауза между проверками цены 30 секунд
        time.sleep(30)


if __name__ == ('__main__'):
    main()