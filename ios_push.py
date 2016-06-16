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
import time
import config
from mysql import Mysql


sandbox = config.SANDBOX
startup_timestamp = int(time.time())

class APNSConnectionManager:
    def __init__(self):
        self.apns_connections = {}
        #上次访问的时间戳,丢弃超过20m未用的链接
        self.connection_timestamps = {}
        self.lock = threading.Lock()

    def get_apns_connection(self, bundle_id):
        self.lock.acquire()
        try:
            connections = self.apns_connections
            apns = connections[bundle_id] if connections.has_key(bundle_id) else None
            if apns:
                ts = self.connection_timestamps[bundle_id]
                now = int(time.time())
                # > 10minute
                if (now - ts) > 20*60:
                    apns = None
                else:
                    self.connection_timestamps[bundle_id] = now
        finally:
            self.lock.release()
        return apns

    def remove_apns_connection(self, bundle_id):
        self.lock.acquire()
        try:
            connections = self.apns_connections
            if connections.has_key(bundle_id):
                logging.debug("pop client:%s", bundle_id)
                connections.pop(bundle_id)
        finally:
            self.lock.release()

    def set_apns_connection(self, bundle_id, connection):
        self.lock.acquire()
        try:
            self.apns_connections[bundle_id] = connection
            self.connection_timestamps[bundle_id] = int(time.time())
        finally:
            self.lock.release()

class IOSPush(object):
    apns_manager = APNSConnectionManager()

    @staticmethod
    def get_p12(bundle_id):
        cert = config.PUSH_CERTS.get(bundle_id)
        if not cert:
            return None, None, 0

        p12_path = cert['ios']['p12']
        secret = cert['ios']['secret']
        with open(p12_path) as f:
            p12 = f.read()
            return p12, secret, startup_timestamp

    @staticmethod
    def gen_pem(p12, secret):
        p12 = crypto.load_pkcs12(p12, str(secret))
        priv_key = crypto.dump_privatekey(crypto.FILETYPE_PEM, p12.get_privatekey())
        pub_key = crypto.dump_certificate(crypto.FILETYPE_PEM, p12.get_certificate())
        return priv_key + pub_key

    @classmethod
    def connect_apns(cls, bundle_id):
        logging.debug("connecting apns")
        p12, secret, timestamp = cls.get_p12(bundle_id)
        if not p12:
            return None

        if sandbox:
            pem_file = "/tmp/app_%s_sandbox_%s.pem" % (bundle_id, timestamp)
            address = 'push_sandbox'
        else:
            pem_file = "/tmp/app_%s_%s.pem" % (bundle_id, timestamp)
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
    def get_connection(cls, bundle_id):
        apns = cls.apns_manager.get_apns_connection(bundle_id)
        if not apns:
            apns = cls.connect_apns(bundle_id)
            if not apns:
                logging.warn("get p12 fail client id:%s", bundle_id)
                return None
            cls.apns_manager.set_apns_connection(bundle_id, apns)
        return apns

    @classmethod
    def push(cls, bundle_id, token, alert, 
             sound="default", badge=0, extra=None):
        message = Message([token], alert=alert, badge=badge, sound=sound, extra=extra)

        for i in range(3):
            if i > 0:
                logging.warn("resend notification")

            apns = cls.get_connection(bundle_id)
             
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
                cls.apns_manager.remove_apns_connection(bundle_id)

