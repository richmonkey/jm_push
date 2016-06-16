# -*- coding: utf-8 -*-

DEBUG=True

SANDBOX=True

REDIS_HOST="192.168.33.10"
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=""

APPNAME = "IMDemo"
APPID = 7
APPKEY = "sVDIlIiDUm7tWPYWhi6kfNbrqui3ez44"
APPSECRET = "0WiCxAU1jh76SbgaaFC7qIaBPm2zkyM1"

PUSH_CERTS = {
    'io.gobelieve.demo':{
        'name':"IMDemo",
        'ios':{
            'p12': "p12/apns_dev_cert.p12",
            'secret': ""
        },
        'jpush':{
            'app_key':'',
            'app_secret':'',
        }
    }
}

