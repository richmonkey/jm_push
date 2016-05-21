# -*- coding: utf-8 -*-
import time
import logging
import sys
import redis
from apnsclient import Message, APNs, Session
import json
import uuid
import subprocess
from OpenSSL import crypto
import os
import traceback
import threading

import config
from mysql import Mysql


sandbox = config.SANDBOX


class APNSConnectionManager:
    def __init__(self):
        self.apns_connections = {}
        #上次访问的时间戳,丢弃超过20m未用的链接
        self.connection_timestamps = {}
        self.lock = threading.Lock()

    def get_apns_connection(self, appid):
        self.lock.acquire()
        try:
            connections = self.apns_connections
            apns = connections[appid] if connections.has_key(appid) else None
            if apns:
                ts = self.connection_timestamps[appid]
                now = int(time.time())
                # > 10minute
                if (now - ts) > 20*60:
                    apns = None
                else:
                    self.connection_timestamps[appid] = now
        finally:
            self.lock.release()
        return apns

    def remove_apns_connection(self, appid):
        self.lock.acquire()
        try:
            connections = self.apns_connections
            if connections.has_key(appid):
                logging.debug("pop client:%s", appid)
                connections.pop(appid)
        finally:
            self.lock.release()

    def set_apns_connection(self, appid, connection):
        self.lock.acquire()
        try:
            self.apns_connections[appid] = connection
            self.connection_timestamps[appid] = int(time.time())
        finally:
            self.lock.release()

class IOSPush(object):
    apns_manager = APNSConnectionManager()

    @staticmethod
    def get_p12(appid):
        with open(config.P12, "rb") as f:
            p12 = f.read()
            return p12, config.P12_SECRET, 0

    @staticmethod
    def gen_pem(p12, secret):
        p12 = crypto.load_pkcs12(p12, str(secret))
        priv_key = crypto.dump_privatekey(crypto.FILETYPE_PEM, p12.get_privatekey())
        pub_key = crypto.dump_certificate(crypto.FILETYPE_PEM, p12.get_certificate())
        return priv_key + pub_key

    @classmethod
    def connect_apns(cls, appid):
        logging.debug("connecting apns")
        p12, secret, timestamp = cls.get_p12(appid)
        if not p12:
            return None

        if sandbox:
            pem_file = "/tmp/app_%s_sandbox_%s.pem" % (appid, timestamp)
            address = 'push_sandbox'
        else:
            pem_file = "/tmp/app_%s_%s.pem" % (appid, timestamp)
            address = 'push_production'

        if not os.path.isfile(pem_file):
            pem = cls.gen_pem(p12, secret)
            f = open(pem_file, "wb")
            f.write(pem)
            f.close()

        session = Session(read_tail_timeout=1)

        conn = session.get_connection(address, cert_file=pem_file)
        apns = APNs(conn)
        return apns

    @classmethod
    def get_connection(cls, appid):
        apns = cls.apns_manager.get_apns_connection(appid)
        if not apns:
            apns = cls.connect_apns(appid)
            if not apns:
                logging.warn("get p12 fail client id:%s", appid)
                return None
            cls.apns_manager.set_apns_connection(appid, apns)
        return apns

    @classmethod
    def push(cls, appid, token, alert, sound="default", badge=0, extra=None):
        message = Message([token], alert=alert, badge=badge, sound=sound, extra=extra)

        for i in range(3):
            if i > 0:
                logging.warn("resend notification")

            apns = cls.get_connection(appid)
             
            try:
                logging.debug("send apns:%s %s %s", message.tokens, alert, badge)
                result = apns.send(message)
             
                for token, (reason, explanation) in result.failed.items():
                    # stop using that token
                    logging.error("failed token:%s", token)
             
                for reason, explanation in result.errors:
                    # handle generic errors
                    logging.error("send notification fail: reason = %s, explanation = %s", reason, explanation)
             
                if result.needs_retry():
                    # extract failed tokens as new message
                    message = result.retry()
                    # re-schedule task with the new message after some delay
                    continue
                else:
                    break
            
            except Exception, e:
                logging.warn("send notification exception:%s", str(e))
                cls.apns_manager.remove_apns_connection(appid)

