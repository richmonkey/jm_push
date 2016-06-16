# -*- coding: utf-8 -*-
import requests
import json
import logging
import time
import base64
import config

#文档地址:http://docs.jpush.io/server/rest_api_v3_push/
JG_URL = "https://api.jpush.cn/v3/push"

class JGPush:
    session = requests.session()
    mysql = None
        
    @classmethod
    def get_app(cls, bundle_id):
        now = int(time.time())
        cert = config.PUSH_CERTS.get(bundle_id, None)
        if cert is None:
            return None

        app = {}
        app["timestamp"] = now
        app['jg_app_key'] = cert['jpush']['app_key']
        app["jg_app_secret"] = cert['jpush']['app_secret']
        app["bundle_id"] = bundle_id
        return app

    @classmethod
    def send(cls, app_key, app_secret, device_tokens, title, content):
        obj = {
            "platform":"android",
            "notification": {
                "android": {
                    "alert": content,
                    "title": title,
                },
            },
            "audience" : {
                "registration_id" : device_tokens
            }
        }

        auth = base64.b64encode(app_key + ":" + app_secret)
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Basic ' + auth}

        data = json.dumps(obj)
        res = cls.session.post(JG_URL, data=data, headers=headers, timeout=60)
        if res.status_code != 200:
            logging.error("send jg message error:%s", res.status_code)
        else:
            logging.debug("send jg message success:%s", res.content)
                          
        print res.content
        

    @classmethod
    def push(cls, bundle_id, appname, tokens, content):
        app = cls.get_app(bundle_id)
        if app is None:
            logging.warning("can't read jg app secret")
            return False
            
        jg_app_key = app["jg_app_key"]
        jg_app_secret = app["jg_app_secret"]
        logging.debug("jg app secret:%s", jg_app_secret)
        logging.debug("send jg push:%s", content)
        for i in range(0, len(tokens), 1000):
            t = tokens[i:i+1000]
            cls.send(jg_app_key, jg_app_secret, t, appname, content)
        
    
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    APP_KEY = ""
    APP_SECRET = ""
    token = "18071adc030e776c98d"

    JGPush.send(APP_KEY, APP_SECRET, [token], "test", "测试极光推送")

