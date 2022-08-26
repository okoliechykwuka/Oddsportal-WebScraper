function pagination(splash, args)
    my_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
    splash:set_user_agent(my_user_agent)
    splash:init_cookies(splash.args.cookies)
    splash.images_enabled = false
    assert(splash:go(args.url))
    assert(splash:wait(0.5))
    splash:set_viewport_full()
    treat=require('treat')
    result= {}
    assert(splash:go(args.url))
    assert(splash:wait(0.5))
    table.insert(result, 1, splash:url())
    local element = splash:evaljs('document.querySelector("#pagination > a:nth-last-child(3) span").innerText')
   
    for i=2,element,1 do
        assert(splash:runjs('document.querySelector("#pagination > a:nth-last-child(2)").click()'))
        assert(splash:wait(2))            
        result[i]=splash:url()
    end

    local entries = splash:history()
    local last_response = entries[#entries].response
    assert(splash:wait(0.5))

    return {
            treat.as_array(result),
            cookies = splash:get_cookies(),
            headers = last_response.headers,
            }
    end



function main(splash)
    my_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
    splash:set_user_agent(my_user_agent)
    splash:init_cookies(splash.args.cookies)
    assert(splash:go(splash.args.url))
    assert(splash:wait(0.5))
    local entries = splash:history()
    local last_response = entries[#entries].response
    assert(splash:wait(0.5))
    return {
        html = splash:html(),
        cookies = splash:get_cookies(),
        headers = last_response.headers,
    }
end


function use_login(splash)
    my_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
    splash:set_user_agent(my_user_agent)
    splash:init_cookies(splash.args.cookies)
    local url = splash.args.url
    assert(splash:go(url))
    assert(splash:wait(0.5))

    splash:set_viewport_full()
    local search_input = splash:select('input[name=login-username]')   
    search_input:send_text("chuky")
    local search_input = splash:select('input[name=login-password]')
    search_input:send_text("A151515a")
    assert(splash:wait(0.5))
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

