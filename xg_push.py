# -*- coding: utf-8 -*-

import requests
import time
import json
import hashlib
import logging
import mysql
import config

XINGE_API = "http://openapi.xg.qq.com"
HTTP_METHOD = "POST"
XINGE_HOST = "openapi.xg.qq.com"



def GenSign(path, params, secretKey):
    ks = sorted(params.keys())
    paramStr = ''.join([('%s=%s' % (k, params[k])) for k in ks])
    signSource = u'%s%s%s%s%s' % (HTTP_METHOD, XINGE_HOST, path, paramStr, secretKey)
    return hashlib.md5(signSource).hexdigest()

class XGPush:
    @classmethod
    def get_xg_app(cls, appid):
        app = {}
        app["access_id"] = config.XG_ACCESS_ID
        app["secret_key"] = config.XG_SECRET_KEY
        app["appid"] = appid
        return app

    @classmethod
    def get_title(cls, appid):
        return "金脉"

    @classmethod
    def push(cls, appid, token, content, extra):
        path = "/v2/push/single_device"
        url = XINGE_API + path

        obj =  {}
        obj["title"] = cls.get_title(appid)
        obj["content"] = content
        obj["vibrate"] = 1
        if extra:
            obj["custom_content"] = extra

        app = XGPush.get_xg_app(appid)
        if app is None:
            logging.warning("can't read xinge access id")
            return False

        msg = json.dumps(obj, separators=(',',':'))

        params = {
            "access_id":app["access_id"],
            "timestamp":int(time.time()), 
            "expire_time":3600*24,
            "device_token":token,
            "message_type":1,
            "message":msg
        }
         
        params["sign"] = GenSign(path, params, app["secret_key"])
        headers = {"content-type":"application/x-www-form-urlencoded"}
         
        r = requests.post(url, headers=headers, data=params)
        return r.status_code == 200
