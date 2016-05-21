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
    def get_app(cls, appid):
        now = int(time.time())
        app = {}
        app["timestamp"] = now
        app["jg_app_key"] = config.JG_APP_KEY
        app["jg_app_secret"] = config.JG_APP_SECRET
        app["appid"] = appid

        return app

    @classmethod
    def send(cls, app_key, app_secret, device_token, title, content):
        obj = {
            "platform":"android",
            "notification": {
                "android": {
                    "alert": content,
                    "title": title,
                },
            },
            "audience" : {
                "registration_id" : [ device_token ]
            }
        }

        auth = base64.b64encode(app_key + ":" + app_secret)
        print auth
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Basic ' + auth}

        data = json.dumps(obj)
        res = cls.session.post(JG_URL, data=data, headers=headers, timeout=60)
        if res.status_code != 200:
            logging.error("send jg message error")
        else:
            obj = json.loads(res.content)
            if obj.has_key("code") and obj["code"] == 0:
                logging.debug("send jg message success")
            else:
                logging.error("send jg message error:%s", res.content)                
        print res.content
        

    @classmethod
    def push(cls, appid, appname, token, content):
        app = cls.get_app(appid)
        if app is None:
            logging.warning("can't read jg app secret")
            return False
            
        jg_app_key = app["jg_app_key"]
        jg_app_secret = app["jg_app_secret"]
        logging.debug("jg app secret:%s", jg_app_secret)
        cls.send(jg_app_key, jg_app_secret, token, appname, content)
  
        
    
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    APP_KEY = ""
    APP_SECRET = ""
    token = "18071adc030e776c98d"

    JGPush.send(APP_KEY, APP_SECRET, token, "test", "测试极光推送")

