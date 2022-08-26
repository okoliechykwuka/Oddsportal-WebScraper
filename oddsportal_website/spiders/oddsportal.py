#Web Scraping 
from typing import Optional
import scrapy
from scrapy_splash import SplashRequest, SplashJsonResponse, SplashTextResponse
from scrapy.http import Request, HtmlResponse
from scrapy.selector import Selector
from urllib.parse import urljoin
#Error Handling
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError
from twisted.internet.error import TimeoutError, TCPTimedOutError
#Reading Lua
from pkgutil import get_data
#data Manipulation
import pandas as pd


class OddsportalSpider(scrapy.Spider):
    name = 'oddsportal'
    allowed_domains = ['oddsportal.com']

    def __init__(self, *args, **kwargs): 
        self.login_page = 'https://www.oddsportal.com/login/'
        

        self.login_lua = """
                    function main(splash)
                        my_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
                        splash:set_user_agent(my_user_agent)
                        splash:init_cookies(splash.args.cookies)
                        local url = splash.args.url
                        assert(splash:go(url))
                        assert(splash:wait(2))

                        splash:set_viewport_full()
                        local search_input = splash:select('input[name=login-username]')   
                        search_input:send_text("chuky")
                        local search_input = splash:select('input[name=login-password]')
                        search_input:send_text("A151515a")
                        assert(splash:wait(2))
                        local submit_button = splash:select('div:nth-child(3) > button[name=login-submit]')
                        submit_button:mouse_click()
                        local entries = splash:history()
                        local last_response = entries[#entries].response

                        assert(splash:wait(0.5))

                        return {
                            html = splash:html(),
                            cookies = splash:get_cookies(),
                            headers = last_response.headers,
                        }
                    end
        
                 """

        self.lua_request = """
                  function main(splash)
                    my_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
                    splash:set_user_agent(my_user_agent)
                    splash:init_cookies(splash.args.cookies)
                    splash.images_enabled = false
                    assert(splash:go(splash.args.url))
                    assert(splash:wait(1))
                    local entries = splash:history()
                    local last_response = entries[#entries].response
                    assert(splash:wait(0.5))
                    return {
                        html = splash:html(),
                        cookies = splash:get_cookies(),
                        headers = last_response.headers,
                    }
                end
        
                  """

        super(OddsportalSpider, self).__init__(*args, **kwargs)

    # spider's entry point
    def start_requests(self):
        """called before crawling starts. function uses lua script to login into the website while maintaing user sessions
        
        Parameters
        ----------
        input: self
        output: returns the response with the splashJsonResponse of the redirect url after login.
        """
        yield SplashRequest(
        url=self.login_page,
        callback=self.after_login,
        endpoint='execute', 
        args={
                'lua_source': self.login_lua,
                'wait': 0.5,
                'timeout':90,
                'images':0
            },
            
            cache_args=['lua_source'], dont_filter=True
         )

    # results page response
    def after_login(self, response):
        """called after a successful login. 
          function uses lua script, to send a request to the /results/ url
          while maintaing user sessions.
        Parameters
        ----------
        
        response: SplashJsonResponse
        output: returns a response of the /results/ page content of oddsportal webiste while maintaining user session.
        """
        
        cookies = response.data['cookies']
        headers = response.data['headers']
        url = 'https://www.oddsportal.com/results/'
        yield  SplashRequest(url=url, endpoint='execute',
                                  callback=self.parse, 
                                  cookies=cookies, headers=headers,
                                   args={'lua_source': self.lua_request, 'timeout':90,'images':0},
                                   cache_args=['lua_source'], errback=self.errback_httpbin,
        
                                  )  

    def parse(self,response):
        """ 
        Request to get all results links page content from oddsportal.
        Parameters
        ----------
        
        response: SplashJsonResponse
        output: returns a response of the /country/leagues page content of oddsportal webiste while maintaining user session.
        """
        cookies = response.data['cookies']
        headers = response.data['headers']
        links = response.xpath("//div[@id= 'archive-tables']//tbody/tr[@xsid=1]/td/a/@href").extract()
        for link in links:
            url = response.urljoin(link)
            yield  SplashRequest(url=url, endpoint='execute',
                                  callback=self.parse_link, 
                                  cookies=cookies, headers=headers,
                                   args={'lua_source': self.lua_request,'timeout':90,'images':0},
                                   cache_args=['lua_source'], errback=self.errback_httpbin,
        
                                  ) 

    def parse_link(self,response):
        """ 
        Request to get years links .
        Parameters
        ----------
        
        response: SplashJsonResponse
        output: returns a response of the /country/leagues page content  for all years  while maintaining user session.
        """
        cookies = response.data['cookies']
        headers = response.data['headers']

        links = response.xpath("//div[@class = 'main-menu2 main-menu-gray']//strong/a/@href").extract()

        for link in links:
                url = response.urljoin(link)
                yield  SplashRequest(url=url, endpoint='execute',
                                    callback=self.check_paginated_pages, 
                                    cookies=cookies, headers=headers,
                                    args={'lua_source': self.lua_request,'timeout':90,'images':0},
                                    cache_args=['lua_source'], errback=self.errback_httpbin,
                                    ) 
                                    

    def check_paginated_pages(self,response):
        """ 
        Request to get pagination  links and page contents.
        Function sends request to the current page and also to all the paginated pages.
        Parameters
        ----------
        response: SplashJsonResponse
        output: returns a response for  all paginated page content across the different years  while maintaining user session.
        """

        try:

            cookies = response.data['cookies']
            headers = response.data['headers']
            game_links =  response.xpath("//div[@id = 'tournamentTable']//td[@class = 'name table-participant']/a/@href").extract()
            for link in game_links:
                games = response.urljoin(link)
                yield  SplashRequest(url=games,
                                    callback=self.follow_teams, 
                                    cookies=cookies, headers=headers,
                                    endpoint='execute',
                                    args={'lua_source': self.lua_request,'timeout':90,'images':0},
                                    cache_args=['lua_source'], errback=self.errback_httpbin,
                                        
                                    ) 

            next_page = response.xpath("//*[@id='pagination']/a[last()-1]//@href").get()
            if next_page:
                abs_url = response.urljoin(next_page)
                yield SplashRequest(
                    url = abs_url,
                    callback=self.check_paginated_pages,
                    cookies=cookies, headers=headers,
                    endpoint='execute',
                    args={'lua_source': self.lua_request,'timeout':90,'images':0},
                    cache_args=['lua_source'], errback=self.errback_httpbin,
                )
            else:
                self.logger.info("Webpage has no pagination")
        except ValueError as v:
            self.logger.info('Invalid Url Provided')

    def winner_agg(self, item: dict, home: int | str, away: int | str, key: bool=True):

        if key:
            if home > away:
                item['1X2'] = 1
            elif home < away:
                item['1X2'] = 2
            else:
                item['1X2'] = 'X'
        else:
            if home > away:
                item['Winner'] = 1
            elif home < away:
                item['Winner'] = 2
            else:
                item['Winner'] = 'X'

    def bet_odds(self, index_pos:int, item: dict, response, betting_exchange:list, keys:list):
            if index_pos == 0:
                self.pos_zero_betexchange(item, response, keys)
            elif index_pos == 1:
                self.pos_one_betexchange(item, response, keys)
            elif index_pos == 2:
                self.pos_two_betexchange(item, response, keys)
            else:
                self.logger.info("Index Value Out of range  %s", betting_exchange)
    

    def pos_zero_betexchange(self,item, response, keys:list):
        

        Back = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[2]/span/text()')
        Lay = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[1]/span/text()')   
      
        if  Back:
            #Odds
            back_1 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[3]/div/text()[1]').get()

            back_x = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[4]/div/text()[1]').get()

            back_2 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[5]/div/text()[1]').get()

            #Liq
            back_1_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[3]/div/text()[2]').get()

            back_x_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[4]/div/text()[2]').get()

            back_2_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[5]/div/text()[2]').get()


            item[keys[0]] = back_1.strip()
            item[keys[2]] = back_x.strip()
            item[keys[4]] = back_2.strip()
            item[keys[1]] =  back_1_liq.split(')')[0].split('(')[1].strip()
            item[keys[3]] = back_x_liq.split(')')[0].split('(')[1].strip()
            item[keys[5]] = back_2_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[0]] = ''
            item[keys[2]] = ''
            item[keys[4]] = ''
            item[keys[1]] =  ''
            item[keys[3]] = ''
            item[keys[5]] = ''

        if Lay:
            #Odds
            lay_1 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[2]/div/text()').get()
            lay_x = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[3]/div/text()').get()
            lay_2 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[4]/div/text()').get()
            #Liq
            lay_1_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[2]/div/text()[2]').get()
            lay_x_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[3]/div/text()[2]').get()
            lay_2_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[4]/div/text()[2]').get()

            item[keys[6]] = lay_1.strip()
            item[keys[8]] = lay_x.strip()
            item[keys[10]] = lay_2.strip()
            item[keys[7]] =  lay_1_liq.split(')')[0].split('(')[1].strip()
            item[keys[9]] = lay_x_liq.split(')')[0].split('(')[1].strip()
            item[keys[11]] = lay_2_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[6]] = ''
            item[keys[8]] = ''
            item[keys[10]] = ''
            item[keys[7]] =  ''
            item[keys[9]] = ''
            item[keys[11]] = ''

    def pos_one_betexchange(self,item, response, keys:list):

        Back = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[2]/span/text()')
        Lay = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[1]/span/text()')        
      
        if  Back:
            #Odds
            back_1 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[3]/div/text()').get()
            back_x = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[4]/div/text()').get()
            back_2 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[5]//text()').get()
            #Liq
            back_1_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[3]/div/text()[2]').get()
            back_x_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[4]/div/text()[2]').get()
            back_2_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[5]/div/text()[2]').get()

            item[keys[0]] = back_1.strip()
            item[keys[2]] = back_x.strip()
            item[keys[4]] = back_2.strip()
            item[keys[1]] =  back_1_liq.split(')')[0].split('(')[1].strip()
            item[keys[3]] = back_x_liq.split(')')[0].split('(')[1].strip()
            item[keys[5]] = back_2_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[0]] = ''
            item[keys[2]] = ''
            item[keys[4]] = ''
            item[keys[1]] =  ''
            item[keys[3]] = ''
            item[keys[5]] = ''
        if Lay:
            #Odds
            lay_1 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[2]/div/text()').get()
            lay_x = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[3]/div/text()').get()
            lay_2 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[4]/div/text()').get()
            #Liq
            lay_1_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[2]/div/text()[2]').get()
            lay_x_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[3]/div/text()[2]').get()
            lay_2_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[4]/div/text()[2]').get()


            item[keys[6]] = lay_1.strip()
            item[keys[8]] = lay_x.strip()
            item[keys[10]] = lay_2.strip()
            item[keys[7]] =  lay_1_liq.split(')')[0].split('(')[1].strip()
            item[keys[9]] = lay_x_liq.split(')')[0].split('(')[1].strip()
            item[keys[11]] = lay_2_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[6]] = ''
            item[keys[8]] = ''
            item[keys[10]] = ''
            item[keys[7]] =  ''
            item[keys[9]] = ''
            item[keys[11]] = ''

    def pos_two_betexchange(self,item, response, keys:list):
        
        Back = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[5]/td[2]/span/text()')
        Lay = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[6]/td[1]/span/text()')        
      
        if  Back:
            #Odds
            back_1 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[5]/td[3]/div/text()').get()
            back_x = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[5]/td[4]/div/text()').get()
            back_2 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[5]/td[5]/div/text()').get()
            #Liq
            back_1_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[5]/td[3]/div/text()[2]').get()
            back_x_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[5]/td[4]/div/text()[2]').get()
            back_2_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[5]/td[5]/div/text()[2]').get()

            item[keys[0]] = back_1.strip()
            item[keys[2]] = back_x.strip()
            item[keys[4]] = back_2.strip()
            item[keys[1]] =  back_1_liq.split(')')[0].split('(')[1].strip()
            item[keys[3]] = back_x_liq.split(')')[0].split('(')[1].strip()
            item[keys[5]] = back_2_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[0]] = ''
            item[keys[2]] = ''
            item[keys[4]] = ''
            item[keys[1]] =  ''
            item[keys[3]] = ''
            item[keys[5]] = ''
        if Lay:
            #Odds
            lay_1 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[6]/td[2]/div/text()').get()
            lay_x = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[6]/td[3]/div/text()').get()
            lay_2 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[6]/td[4]/div/text()').get()
            #Liq
            lay_1_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[6]/td[2]/div/text()[2]').get()
            lay_x_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[6]/td[3]/div/text()[2]').get()
            lay_2_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[6]/td[4]/div/text()[2]').get()


            item[keys[6]] = lay_1.strip()
            item[keys[8]] = lay_x.strip()
            item[keys[10]] = lay_2.strip()
            item[keys[7]] =  lay_1_liq.split(')')[0].split('(')[1].strip()
            item[keys[9]] = lay_x_liq.split(')')[0].split('(')[1].strip()
            item[keys[11]] = lay_2_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[6]] = ''
            item[keys[8]] = ''
            item[keys[10]] = ''
            item[keys[7]] =  ''
            item[keys[9]] = ''
            item[keys[11]] = ''

    ##############  Over Goals ##################
    def pos_zero_betexchange(self,item, response, keys:list):

        Back = response.xpath('//*[@id="odds-data-table"]/div[2]/table/tbody/tr[1]/td[2]/span/text()')
        Lay = response.xpath('//*[@id="odds-data-table"]/div[2]/table/tbody/tr[2]/td[1]/span/text()')   
      
        if  Back:
            #Odds
            back_1 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[3]/div/text()[1]').get()

            back_x = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[4]/div/text()[1]').get()

            back_2 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[5]/div/text()[1]').get()

            #Liq
            back_1_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[3]/div/text()[2]').get()

            back_x_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[4]/div/text()[2]').get()

            back_2_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[5]/div/text()[2]').get()


            item[keys[0]] = back_1.strip()
            item[keys[2]] = back_x.strip()
            item[keys[4]] = back_2.strip()
            item[keys[1]] =  back_1_liq.split(')')[0].split('(')[1].strip()
            item[keys[3]] = back_x_liq.split(')')[0].split('(')[1].strip()
            item[keys[5]] = back_2_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[0]] = ''
            item[keys[2]] = ''
            item[keys[4]] = ''
            item[keys[1]] =  ''
            item[keys[3]] = ''
            item[keys[5]] = ''

        if Lay:
            #Odds
            lay_1 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[2]/div/text()').get()
            lay_x = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[3]/div/text()').get()
            lay_2 = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[4]/div/text()').get()
            #Liq
            lay_1_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[2]/div/text()[2]').get()
            lay_x_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[3]/div/text()[2]').get()
            lay_2_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[4]/div/text()[2]').get()

            item[keys[6]] = lay_1.strip()
            item[keys[8]] = lay_x.strip()
            item[keys[10]] = lay_2.strip()
            item[keys[7]] =  lay_1_liq.split(')')[0].split('(')[1].strip()
            item[keys[9]] = lay_x_liq.split(')')[0].split('(')[1].strip()
            item[keys[11]] = lay_2_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[6]] = ''
            item[keys[8]] = ''
            item[keys[10]] = ''
            item[keys[7]] =  ''
            item[keys[9]] = ''
            item[keys[11]] = ''
    
    def pos_zero_bts(self,item, response, keys:list):
        #getting both team to score odds

        Back = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[2]/span/text()')
        print(Back,'Backkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk')
        Lay = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[1]/span/text()') 
      
        if  Back:
            #Odds
            back_yes = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[3]/div/text()[1]').get()
            print('This is back 1--------------------------', back_yes)
            back_no = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[4]/div/text()[1]').get()
            print('This is back X--------------------------', back_no)
 
            #Liq
            back_yes_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[3]/div/text()[2]').get()
            print('This is liq 1 --------------------------', back_yes_liq)
            back_no_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[4]/div/text()[2]').get()
            print('This is back x --------------------------', back_no_liq)
            item[keys[0]] = back_yes.strip()
            item[keys[2]] = back_no.strip()
            item[keys[1]] =  back_yes_liq.split(')')[0].split('(')[1].strip()
            item[keys[3]] = back_no_liq.split(')')[0].split('(')[1].strip()
      
        else:
            item[keys[0]] = ''
            item[keys[2]] = ''
            item[keys[1]] =  ''
            item[keys[3]] = ''

        if Lay:
            #Odds
            lay_yes = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[2]/div/text()').get()
            lay_no = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[3]/div/text()').get()

            #Liq
            lay_yes_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[2]/div/text()[2]').get()
            lay_no_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[3]/div/text()[2]').get()

            item[keys[4]] = lay_yes.strip()
            item[keys[6]] = lay_no.strip()

            item[keys[5]] =  lay_yes_liq.split(')')[0].split('(')[1].strip()
            item[keys[7]] = lay_no_liq.split(')')[0].split('(')[1].strip()
        else:
            item[keys[4]] = ''
            item[keys[6]] = ''
            item[keys[5]] = ''
            item[keys[7]] =  ''

    def pos_one_bts(self,item, response, keys:list):

        Back = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[2]/span/text()')

        Lay = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[1]/span/text()') 



        if  Back:
            #Odds
            back_yes = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[3]/div/text()').get()
            back_no = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[4]/div/text()').get()
            #Liq
            back_yes_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[3]/div/text()[2]').get()
            back_no_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[4]/div/text()[2]').get()

            item[keys[0]] = back_yes.strip()
            item[keys[2]] = back_no.strip()
            item[keys[1]] =  back_yes_liq.split(')')[0].split('(')[1].strip()
            item[keys[3]] = back_no_liq.split(')')[0].split('(')[1].strip()
        
        else:
            item[keys[0]] = ''
            item[keys[2]] = ''
            item[keys[1]] =  ''
            item[keys[3]] = ''

        if Lay:
            #Odds
            lay_yes = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[2]/div/text()').get()
            lay_no = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[3]/div/text()').get()
            #Liq
            lay_yes_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[2]/div/text()[2]').get()
            lay_no_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[3]/div/text()[2]').get()


            item[keys[4]] = lay_yes.strip()
            item[keys[6]] = lay_no.strip()
            item[keys[5]] =  lay_yes_liq.split(')')[0].split('(')[1].strip()
            item[keys[7]] = lay_no_liq.split(')')[0].split('(')[1].strip()

        else:
            item[keys[4]] = ''
            item[keys[6]] = ''
            item[keys[5]] = ''
            item[keys[7]] =  ''

    def pos_two_bts(self,item, response, keys:list):

        Back = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[1]/td[2]/span/text()')
        Lay = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[2]/td[1]/span/text()') 
      
        if  Back:
            #Odds
            back_yes = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[3]/div/text()').get()
            back_no = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[4]/div/text()').get()
            #Liq
            back_yes_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[3]/div/text()[2]').get()
            back_no_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[3]/td[4]/div/text()[2]').get()

            item[keys[0]] = back_yes.strip()
            item[keys[2]] = back_no.strip()
            item[keys[1]] =  back_yes_liq.split(')')[0].split('(')[1].strip()
            item[keys[3]] = back_no_liq.split(')')[0].split('(')[1].strip()
        
        else:
            item[keys[0]] = ''
            item[keys[2]] = ''
            item[keys[1]] =  ''
            item[keys[3]] = ''

        if Lay:
            #Odds
            lay_yes = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[2]/div/text()').get()
            lay_no = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[3]/div/text()').get()
            #Liq
            lay_yes_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[2]/div/text()[2]').get()
            lay_no_liq = response.xpath('//*[@id="odds-data-table"]/div[3]/table/tbody/tr[4]/td[3]/div/text()[2]').get()


            item[keys[4]] = lay_yes.strip()
            item[keys[6]] = lay_no.strip()
            item[keys[5]] =  lay_yes_liq.split(')')[0].split('(')[1].strip()
            item[keys[7]] = lay_no_liq.split(')')[0].split('(')[1].strip()

        else:
            item[keys[4]] = ''
            item[keys[6]] = ''
            item[keys[5]] = ''
            item[keys[7]] =  ''


    def bts_odds(self, index_pos:int, item: dict, response, betting_exchange:list, keys:list):
            if index_pos == 0:
                self.pos_zero_bts(item, response, keys)
            elif index_pos == 1:
                self.pos_one_bts(item, response, keys)
            elif index_pos == 2:
                self.pos_two_bts(item, response, keys)
            else:
                self.logger.info("Index Value Out of range  %s", betting_exchange)

    def follow_teams(self,response):

        item = {}
        cookies = response.data['cookies']
        headers = response.data['headers']
        self.logger.info("Downloading data from Oddsportal ------------------------  %s", response.url)        
        item['Sports'] = response.xpath('//*[@id="breadcrumb"]/a[2]/text()').get()
        item['Country'] = response.xpath('//*[@id="breadcrumb"]/a[3]/text()').get()
        item['Event'] = response.xpath('//*[@id="breadcrumb"]/a[4]/text()').get()
        date = response.xpath('//*[@id="col-content"]/p[1]/text()').get()
        date = date.split(',')[1].strip()
        clean_date = pd.to_datetime(date).strftime('%d/%m/%Y')
        item['Date'] = clean_date
        month = date.split(' ')
        clean_month = month[0] +'.'+ month[1]
        item['Month'] = clean_month
        dmap = {'Jan': 'Q1', 'Feb':'Q1', 'Mar': 'Q1', 'Apr':'Q2', 'May':'Q2', 'Jun':'Q2', 'Jul':'Q3', 'Aug':'Q3', 'Sep':'Q3', 'Oct':'Q4', 'Nov':'Q4', 'Dec': 'Q4' }
        d = [v for k, v in dmap.items() if k == month[1]]
        item['Quarter'] = d[0]
        item['Year'] = month[-1]
        teams = response.xpath('//*[@id="col-content"]/h1/text()').get()
        teams = teams.split(' - ')
        team_1 = teams[0].strip()
        team_2 = teams[1].strip()
        item['Team 1'] = team_1
        # item['Team 2'] = team_2
        score = response.xpath('//div[@id="event-status"]//p/text()').get()
        alternative_score = response.xpath('//*[@id="event-status"]/p/strong/text()').get()
        self.logger.info("Scores ------------------------  %s", score)

        try:

            if score is not None:
                scrore_1 = alternative_score.split(' ')[0].split(':')[0].strip()
                scrore_2 = alternative_score.split(' ')[0].split(':')[1].strip()
                home_first_half_goals = score.split(',')[0].split('(')[1].split(':')[0].strip()
                away_first_half_goals = score.split(',')[0].split('(')[1].split(':')[1].strip()
                home_second_half_goals = score.split(',')[1].split(')')[0].split(':')[0].strip()
                away_second_half_goals = score.split(',')[1].split(')')[0].split(':')[1].strip()

                self.winner_agg(item, scrore_1, scrore_2)

                item['Final result'] = alternative_score
                item['1HH Goals'] = home_first_half_goals
                item['1HA Goals'] = away_first_half_goals
                item['1H Total Goals'] = int(home_first_half_goals) + int(away_first_half_goals)
                item['2HH Goals'] = home_second_half_goals
                item['2HA Goals'] = away_second_half_goals
                item['2H Total Goals'] = int(home_second_half_goals) + int(away_second_half_goals)
                item['FT Total Goals'] = item['1H Total Goals'] + item['2H Total Goals']
                 
        
                if len(score) >= 17:
                    item['ET'] = 1
                    home_goal_et = score.split(',')[2].split(':')[0].strip()
                    away_goal_et = score.split(',')[2].split(':')[1].strip()
                    item['ET H Goals'] = int(home_goal_et)
                    item['ET A Goals'] = int(away_goal_et)
                    item['ET Total Goals'] = item['ET H Goals'] + item['ET A Goals']
                    item['Pen'] = 1
                    item['H Pen'] = score.split(',')[3].split(':')[0].strip()
                    item['A Pen'] = score.split(',')[3].split(':')[1].split(')')[0].strip()
                    item['Total Pens'] = int(item['H Pen'] ) + int(item['A Pen'])
                    home_agg_goal = int(item['1HH Goals']) +  int(item['2HH Goals']) + item['ET H Goals'] + int(item['H Pen'])
                    away_agg_goal = int(item['1HA Goals']) +  int(item['2HA Goals']) + item['ET A Goals'] + int(item['A Pen'])
                    self.winner_agg(item, home_agg_goal, away_agg_goal, key=False)

                elif len(score) >= 13 and len(score) < 17:
                    item['ET'] = 1
                    item['ET H Goals'] = ''
                    item['ET A Goals'] = ''
                    item['ET Total Goals'] = ''
                    item['Pen'] = 1
                    item['H Pen'] = score.split(',')[2].split(':')[0].strip()
                    item['A Pen'] = score.split(',')[2].split(':')[1].split(')')[0].strip()
                    item['Total Pens'] = int(item['H Pen'] ) + int(item['A Pen'])
                    home_agg_goal = int(item['1HH Goals']) +  int(item['2HH Goals']) + int(item['H Pen'])
                    away_agg_goal = int(item['1HA Goals']) +  int(item['2HA Goals']) + int(item['A Pen'])
                    self.winner_agg(item, home_agg_goal, away_agg_goal, key=False)
                else:
                    item['ET'] = 0
                    item['ET H Goals'] = ''
                    item['ET A Goals'] = ''
                    item['ET Total Goals'] = ''
                    item['Pen'] = 0
                    item['H Pen'] = ''
                    item['A Pen'] = ''
                    item['Total Pens'] = ''
                    home_agg_goal = int(item['1HH Goals']) +  int(item['2HH Goals'])
                    away_agg_goal = int(item['1HA Goals']) +  int(item['2HA Goals'])
                    self.winner_agg(item, home_agg_goal, away_agg_goal, key=False)


            elif alternative_score is not None:

                scrore_1 = alternative_score.split(' ')[0].split(':')[0].strip()
                scrore_2 = alternative_score.split(' ')[0].split(':')[1].strip()
                
                self.winner_agg(item, scrore_1, scrore_2)

                item['Final result'] = alternative_score
                item['1HH Goals'] = ''
                item['1HA Goals'] = ''
                item['1H Total Goals'] = ''
                item['2HH Goals'] = ''
                item['2HA Goals'] = ''
                item['2H Total Goals'] = ''
                item['FT Total Goals'] = int(scrore_1) + int(scrore_2)
                item['ET'] = ''
                item['ET H Goals'] = ''
                item['ET A Goals'] = ''
                item['ET Total Goals'] = ''
                item['Pen'] = 0
                item['H Pen'] = ''
                item['A Pen'] = ''
                item['Total Pens'] = ''
                self.winner_agg(item, scrore_1, scrore_2, key=False)
                
            else:
                item['1'] = ''
                item['2'] = ''
                item['X'] = ''
                item['Final result'] = ''
                item['1HH Goals'] = ''
                item['1HA Goals'] = ''
                item['1H Total Goals'] = ''
                item['2HH Goals'] = ''
                item['2HA Goals'] = ''
                item['2H Total Goals'] = ''
                item['FT Total Goals']  = ''
                item['ET'] = ''
                item['ET H Goals'] = ''
                item['ET A Goals'] = ''
                item['ET Total Goals'] = ''
                item['Pen'] = 0
                item['H Pen'] = ''
                item['A Pen'] = ''
                item['Total Pens'] = ''
                item['Winner'] = ''

            #Getting Odds for BetExchange 1X2 scores
            betting_exchange = response.xpath("//*[@class= 'table-container exchangeContainer']//a[@class='name']/text()").getall()
            keys_Betfair_exchange = ['BE Back 1 - Odds','BE Back 1 - Liq','BE Back X - Odds','BE Back X - Liq','BE Back 2 - Odds','BE Back 2 - Liq','BE Lay 1 - Odds','BE Lay 1 - Liq',
                                          'BE Lay X - Odds','BE Lay X - Liq','BE Lay 2 - Odds','BE Lay 2 - Liq' ]

            keys_matchbook = ['MB Back 1 - Odds','MB Back 1 - Liq','MB Back X - Odds','MB Back X - Liq','MB Back 2 - Odds','MB Back 2 - Liq','MB Lay 1 - Odds','MB Lay 1 - Liq',
                                          'MB Lay X - Odds','MB Lay X - Liq','MB Lay 2 - Odds','MB Lay 2 - Liq' ]
            
            keys_smarkets = ['SM Back 1 - Odds','SM Back 1 - Liq','SM Back X - Odds','SM Back X - Liq','SM Back 2 - Odds','SM Back 2 - Liq','SM Lay 1 - Odds','SM Lay 1 - Liq',
                                          'SM Lay X - Odds','SM Lay X - Liq','SM Lay 2 - Odds','SM Lay 2 - Liq' ]


            
            if 'Betfair Exchange' in betting_exchange:
                #check index position of betfair exchange
                index_pos = betting_exchange.index('Betfair Exchange')
                self.bet_odds(index_pos, item, response, betting_exchange, keys_Betfair_exchange)
            # else:
            #     for value in keys_Betfair_exchange:
            #         item[value] = ''

            if 'Matchbook' in betting_exchange:
                index_pos = betting_exchange.index('Matchbook')
                self.bet_odds(index_pos, item, response, betting_exchange, keys_matchbook)
            # else:
            #     for value in keys_matchbook:
            #         item[value] = ''

            if 'Smarkets' in betting_exchange:
                #check index position of betfair exchange
                index_pos = betting_exchange.index('Smarkets')
                self.bet_odds(index_pos, item, response, betting_exchange, keys_smarkets)
            # else:
                # for value in keys_smarkets:
                #     item[value] = ''


        except (IndexError,AttributeError, ValueError) as e:
            self.logger.warning('AttributeError on %s', response.url)
        
        first_half_win_url = response.urljoin('#1X2;3')
        print(first_half_win_url,'----------------------------- First Half Win Odds ------------------------------------')
        yield  SplashRequest(url=first_half_win_url, endpoint = 'execute',
                            callback=self.first_half_win_odds, 
                            cookies=cookies, headers=headers,
                            args={'lua_source': self.lua_request,'timeout':90,'images':0},
                            cache_args=['lua_source'], errback=self.errback_httpbin,
                            cb_kwargs={'item': item},
                            ) 



    def first_half_win_odds(self, response, item):
        #Getting Odds for BetExchange 1X2 scores
        cookies = response.data['cookies']
        headers = response.data['headers']

        bts = response.xpath('//div[@class= "table-container exchangeContainer"]//th[@class="center odds-odds"]').getall()

        if len(bts) == 3:
            #Getting Odds for BetExchange 1X2 scores
            betting_exchange = response.xpath("//*[@class= 'table-container exchangeContainer']//a[@class='name']/text()").getall()

            keys_Betfair = ['BE Back First Half 1 - Odds','BE Back First Half 1 - Liq','BE Back First Half X - Odds','BE Back First Half X - Liq','BE Back First Half 2 - Odds','BE Back First Half 2 - Liq',
                            'BE Lay First Half 1 - Odds','BE Lay First Half 1 - Liq', 'BE Lay First Half X - Odds','BE Lay First Half X - Liq','BE Lay First Half 2 - Odds','BE Lay First Half 2 - Liq' ]

            keys_matchbook = ['MB Back First Half 1 - Odds','MB Back First Half 1 - Liq','MB Back First Half X - Odds','MB Back First Half X - Liq','MB Back First Half 2 - Odds','MB Back First Half 2 - Liq',
                             'MB Lay First Half 1 - Odds','MB Lay First Half 1 - Liq', 'MB Lay First Half X - Odds','MB Lay First Half X - Liq','MB Lay First Half 2 - Odds','MB Lay First Half 2 - Liq' ]
            
            keys_smarkets = ['SM Back First Half 1 - Odds','SM Back First Half 1 - Liq','SM Back First Half X - Odds','SM Back First Half X - Liq','SM Back First Half 2 - Odds','SM Back First Half 2 - Liq',
                            'SM Lay First Half 1 - Odds','SM Lay First Half 1 - Liq', 'SM Lay First Half X - Odds','SM Lay First Half X - Liq','SM Lay First Half 2 - Odds','SM Lay First Half 2 - Liq' ]

            try: 
            
                if 'Betfair Exchange' in betting_exchange:
                    #check index position of betfair exchange
                    index_pos = betting_exchange.index('Betfair Exchange')
                    self.bet_odds(index_pos, item, response, betting_exchange, keys_Betfair)
                # else:
                #     for value in keys_Betfair_exchange:
                #         item[value] = ''

                if 'Matchbook' in betting_exchange:
                    index_pos = betting_exchange.index('Matchbook')
                    self.bet_odds(index_pos, item, response, betting_exchange, keys_matchbook)
                # else:
                #     for value in keys_matchbook:
                #         item[value] = ''

                if 'Smarkets' in betting_exchange:
                    #check index position of betfair exchange
                    index_pos = betting_exchange.index('Smarkets')
                    self.bet_odds(index_pos, item, response, betting_exchange, keys_smarkets)
                # else:
                    # for value in keys_smarkets:
                    #     item[value] = ''
                    
            except (IndexError,AttributeError, ValueError) as e:
                self.logger.warning('AttributeError on %s', response.url)
        else:
            self.logger.info('Match have No First Half Win Odds')
        
        url = response.url.split('#')[0]
        first_bts_url = urljoin(url, '#over-under;2')

        print(first_bts_url, '----------------------------- Over Goals ------------------------------------')

        yield  SplashRequest(url=first_bts_url, endpoint='execute',
                            callback=self.bts_full_time, 
                            cookies=cookies, headers=headers,
                            args={'lua_source': self.lua_request,'timeout':90,'images':0},
                            cache_args=['lua_source'], errback=self.errback_httpbin,
                            cb_kwargs={'item': item},
                            )


    def over_goals(self, response, item):
        #Getting Odds for BetExchange 1X2 scores
        cookies = response.data['cookies']
        headers = response.data['headers']

        bts = response.xpath('//div[@class= "table-container exchangeContainer"]//th[@class="center odds-odds"]').getall()

        if len(bts) == 2:
            betting_exchange = response.xpath("//*[@class= 'table-container exchangeContainer']//a[@class='name']/text()").getall()
            
            keys_Betfair = ['BE Back BTTS Yes - Odds', 'BE Back BTTS Yes - Liq', 'BE Back BTTS No - Odds',  'BE Back BTTS No - Liq', 'BE Lay BTTS Yes - Odds', 
                           'BE Lay BTTS Yes - Liq', 'BE Lay BTTS No - Odds', 'BE Lay BTTS No - Liq']

            keys_matchbook = ['MB Back BTTS Yes - Odds', 'MB Back BTTS Yes - Liq', 'MB Back BTTS No - Odds',  'MB Back BTTS No - Liq', 'MB Lay BTTS Yes - Odds', 
                             'MB Lay BTTS Yes - Liq', 'MB Lay BTTS No - Odds', 'MB Lay BTTS No - Liq']

            keys_smarkets = ['SM Back BTTS Yes - Odds', 'SM Back BTTS Yes - Liq', 'SM Back BTTS No - Odds',  'SM Back BTTS No - Liq', 'SM Lay BTTS Yes - Odds', 
                            'SM Lay BTTS Yes - Liq', 'SM Lay BTTS No - Odds', 'SM Lay BTTS No - Liq']
            try: 
            
                if 'Betfair Exchange' in betting_exchange:
                    #check index position of betfair exchange
                    index_pos = betting_exchange.index('Betfair Exchange')
                    self.bet_odds(index_pos, item, response, betting_exchange, keys_Betfair)
                # else:
                #     for value in keys_Betfair_exchange:
                #         item[value] = ''

                if 'Matchbook' in betting_exchange:
                    index_pos = betting_exchange.index('Matchbook')
                    self.bet_odds(index_pos, item, response, betting_exchange, keys_matchbook)
                # else:
                #     for value in keys_matchbook:
                #         item[value] = ''

                if 'Smarkets' in betting_exchange:
                    #check index position of betfair exchange
                    index_pos = betting_exchange.index('Smarkets')
                    self.bet_odds(index_pos, item, response, betting_exchange, keys_smarkets)
                # else:
                    # for value in keys_smarkets:
                    #     item[value] = ''
                    
            except (IndexError,AttributeError, ValueError) as e:
                self.logger.warning('AttributeError on %s', response.url)
        else:
            self.logger.info('Match have No First Half Win Odds')
        
        url = response.url.split('#')[0]
        first_bts_url = urljoin(url, '#bts;2')

        print(first_bts_url, '----------------------------- Both Team To Score------------------------------------')

        yield  SplashRequest(url=first_bts_url, endpoint='execute',
                            callback=self.bts_full_time, 
                            cookies=cookies, headers=headers,
                            args={'lua_source': self.lua_request,'timeout':90,'images':0},
                            cache_args=['lua_source'], errback=self.errback_httpbin,
                            cb_kwargs={'item': item},
                            )


    # def bts_full_time(self, response, item):
    #     #Getting Odds for BetExchange 1X2 scores
    #     cookies = response.data['cookies']
    #     headers = response.data['headers']

    #     bts = response.xpath('//div[@class= "table-container exchangeContainer"]//th[@class="center odds-odds"]').getall()

    #     if len(bts) == 2:
    #         betting_exchange = response.xpath("//*[@class= 'table-container exchangeContainer']//a[@class='name']/text()").getall()
            
    #         keys_Betfair = ['BE Back BTTS Yes - Odds', 'BE Back BTTS Yes - Liq', 'BE Back BTTS No - Odds',  'BE Back BTTS No - Liq', 'BE Lay BTTS Yes - Odds', 
    #                        'BE Lay BTTS Yes - Liq', 'BE Lay BTTS No - Odds', 'BE Lay BTTS No - Liq']

    #         keys_matchbook = ['MB Back BTTS Yes - Odds', 'MB Back BTTS Yes - Liq', 'MB Back BTTS No - Odds',  'MB Back BTTS No - Liq', 'MB Lay BTTS Yes - Odds', 
    #                          'MB Lay BTTS Yes - Liq', 'MB Lay BTTS No - Odds', 'MB Lay BTTS No - Liq']

    #         keys_smarkets = ['SM Back BTTS Yes - Odds', 'SM Back BTTS Yes - Liq', 'SM Back BTTS No - Odds',  'SM Back BTTS No - Liq', 'SM Lay BTTS Yes - Odds', 
    #                         'SM Lay BTTS Yes - Liq', 'SM Lay BTTS No - Odds', 'SM Lay BTTS No - Liq']

    #         try:
            
    #             if 'Betfair Exchange' in betting_exchange:
    #                 #check index position of betfair exchange
    #                 index_pos = betting_exchange.index('Betfair Exchange')
    #                 self.bts_odds(index_pos, item, response, betting_exchange, keys_Betfair)
    #             # else:
    #             #     for value in keys_Betfair_exchange:
    #             #         item[value] = ''

    #             if 'Matchbook' in betting_exchange:
    #                 index_pos = betting_exchange.index('Matchbook')
    #                 self.bts_odds(index_pos, item, response, betting_exchange, keys_matchbook)
    #             # else:
    #             #     for value in keys_matchbook:
    #             #         item[value] = ''

    #             if 'Smarkets' in betting_exchange:
    #                 #check index position of betfair exchange
    #                 index_pos = betting_exchange.index('Smarkets')
    #                 self.bts_odds(index_pos, item, response, betting_exchange, keys_smarkets)
    #             # else:
    #                 # for value in keys_smarkets:
    #                 #     item[value] = ''
    #         except (IndexError,AttributeError, ValueError) as e:
    #             self.logger.warning('AttributeError on %s', response.url)
    #     else:
    #         self.logger.info('Match have No Both-Team-to-Score')
        
    #     url = response.url.split('#')[0]
    #     first_bts_url = urljoin(url, '#bts;3')

    #     print(first_bts_url, '-----------------------------1st Half Both Team To Score------------------------------------')

    #     yield  SplashRequest(url=first_bts_url, endpoint='execute',
    #                         callback=self.first_bts_full_time, 
    #                         cookies=cookies, headers=headers,
    #                         args={'lua_source': self.lua_request,'timeout':90,'images':0},
    #                         cache_args=['lua_source'], errback=self.errback_httpbin,
    #                         cb_kwargs={'item': item},
    #                         ) 


    # def first_bts_full_time(self, response, item):
    #     cookies = response.data['cookies']
    #     headers = response.data['headers']
    #     #Getting Odds for BetExchange 1X2 scores
    
    #     bts = response.xpath('//div[@class= "table-container exchangeContainer"]//th[@class="center odds-odds"]').getall()

    #     if len(bts) == 2:
    #         betting_exchange = response.xpath("//*[@class= 'table-container exchangeContainer']//a[@class='name']/text()").getall()
    #         keys_Betfair = ['BE Back FIRST HALF BTTS Yes - Odds', 'BE Back FIRST HALF BTTS Yes - Liq', 'BE Back FIRST HALF BTTS No - Odds',  'BE FIRST HALF Back BTTS No - Liq', 'BE Lay FIRST HALF BTTS Yes - Odds', 
    #                        'BE Lay FIRST HALF BTTS Yes - Liq', 'BE Lay FIRST HALF BTTS No - Odds', 'BE Lay FIRST HALF BTTS No - Liq']

    #         keys_matchbook = ['MB Back FIRST HALF BTTS Yes - Odds', 'MB Back FIRST HALF BTTS Yes - Liq', 'MB Back FIRST HALF BTTS No - Odds',  'MB Back FIRST HALF BTTS No - Liq', 'MB Lay FIRST HALF BTTS Yes - Odds', 
    #                          'MB Lay FIRST HALF BTTS Yes - Liq', 'MB Lay FIRST HALF BTTS No - Odds', 'MB Lay FIRST HALF BTTS No - Liq']

    #         keys_smarkets = ['SM Back FIRST HALF BTTS Yes - Odds', 'SM Back FIRST HALF BTTS Yes - Liq', 'SM Back FIRST HALF BTTS No - Odds',  'SM Back FIRST HALF BTTS No - Liq', 'SM Lay FIRST HALF BTTS Yes - Odds', 
    #                         'SM Lay FIRST HALF BTTS Yes - Liq', 'SM Lay FIRST HALF BTTS No - Odds', 'SM Lay FIRST HALF BTTS No - Liq']

    #         try:
            
    #             if 'Betfair Exchange' in betting_exchange:
    #                 #check index position of betfair exchange
    #                 index_pos = betting_exchange.index('Betfair Exchange')
    #                 self.bts_odds(index_pos, item, response, betting_exchange, keys_Betfair)
    #             # else:
    #             #     for value in keys_Betfair_exchange:
    #             #         item[value] = ''

    #             if 'Matchbook' in betting_exchange:
    #                 index_pos = betting_exchange.index('Matchbook')
    #                 self.bts_odds(index_pos, item, response, betting_exchange, keys_matchbook)
    #             # else:
    #             #     for value in keys_matchbook:
    #             #         item[value] = ''

    #             if 'Smarkets' in betting_exchange:
    #                 #check index position of betfair exchange
    #                 index_pos = betting_exchange.index('Smarkets')
    #                 self.bts_odds(index_pos, item, response, betting_exchange, keys_smarkets)
    #             # else:
    #                 # for value in keys_smarkets:
    #                 #     item[value] = ''
    #         except (IndexError,AttributeError, ValueError) as e:
    #             self.logger.warning('AttributeError on %s', response.url)
    #     else:
    #         self.logger.info('Match have No First HalfBoth-Team-to-Score')

    #     yield item


    def errback_httpbin(self, failure):

        """
        Error Handling Function for all request and response.
        Parameters
        ----------
        failure: logs a request or response errors on the console.        
        """
        # log all failures
        self.logger.error(repr(failure))

        # in case you want to do something special for some errors,
        # you may need the failure's type:

        if failure.check(HttpError):
            # these exceptions come from HttpError spider middleware
            # you can get the non-200 response
            response = failure.value.response
            self.logger.error('HttpError on %s', response.url)

        elif failure.check(DNSLookupError):
            # this is the original request
            request = failure.request
            self.logger.error('DNSLookupError on %s', request.url)

        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error('TimeoutError on %s', request.url)
        
        
        elif failure.check(IndexError):
            request = failure.request
            self.logger.error('IndexError on %s', request.url)

    def __repr__(self):
        return "Oddsportal(oddsportal odds web scraper  for all sports')"
    
    def __str__(self):
        return self.__repr__()





