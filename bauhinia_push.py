# -*- coding: utf-8 -*-
import time
import logging
import sys
import redis
import json
import config
import traceback
import binascii

from ios_push import IOSPush
from xg_push import XGPush
from mipush import MiPush
from huawei import HuaWeiPush
from gcm import GCMPush
from jgpush import JGPush

rds = redis.StrictRedis(host=config.REDIS_HOST, port=config.REDIS_PORT, password=config.REDIS_PASSWORD, db=config.REDIS_DB)

class User(object):
    def __init__(self):
        self.apns_device_token = None
        self.uid = None
        self.appid = None
        self.name = ""

    @staticmethod
    def get_user(rds, appid, uid):
        u = User()
        key = "users_%s_%s"%(appid, uid)
        u.name, u.apns_device_token, apns_ts, u.ng_device_token, ng_ts, u.xg_device_token, xg_ts, u.mi_device_token, mi_ts, u.hw_device_token, hw_ts, u.gcm_device_token, gcm_ts, u.jp_device_token, jp_ts, unread = rds.hmget(key, "name", "apns_device_token", "apns_timestamp", "ng_device_token", "ng_timestamp", "xg_device_token", "xg_timestamp", "xm_device_token", "xm_timestamp", "hw_device_token", "hw_timestamp", "gcm_device_token", "gcm_timestamp", "jp_device_token", "jp_timestamp", "unread")
     
        u.appid = appid
        u.uid = uid
        u.unread = int(unread) if unread else 0
        u.apns_timestamp = int(apns_ts) if apns_ts else 0
        u.ng_timestamp = int(ng_ts) if ng_ts else 0
        u.xg_timestamp = int(xg_ts) if xg_ts else 0
        u.mi_timestamp = int(mi_ts) if mi_ts else 0
        u.hw_timestamp = int(hw_ts) if hw_ts else 0
        u.gcm_timestamp = int(gcm_ts) if gcm_ts else 0
        u.jp_timestamp = int(jp_ts) if jp_ts else 0
        return u

    @staticmethod
    def set_user_unread(rds, appid, uid, unread):
        key = "users_%s_%s"%(appid, uid)
        rds.hset(key, "unread", unread)
     
    @staticmethod
    def get_user_name(rds, appid, uid):
        key = "users_%s_%s"%(appid, uid)
        return rds.hget(key, "name")
     
    @staticmethod
    def get_user_notification_setting(rds, appid, uid, group_id):
        key = "users_%s_%s"%(appid, uid)
        quiet = rds.hget(key, "group_%d"%group_id)
        quiet = int(quiet) if quiet else 0
        return quiet

    @staticmethod
    def get_bundle_user(rds, appid, uid, bundle_id):
        u = User()
        key = "users_%s_%s_%s"%(appid, uid, bundle_id)
        u.name, u.apns_device_token, apns_ts, u.ng_device_token, ng_ts, u.xg_device_token, xg_ts, u.mi_device_token, mi_ts, u.hw_device_token, hw_ts, u.gcm_device_token, gcm_ts, u.jp_device_token, jp_ts, unread = rds.hmget(key, "name", "apns_device_token", "apns_timestamp", "ng_device_token", "ng_timestamp", "xg_device_token", "xg_timestamp", "xm_device_token", "xm_timestamp", "hw_device_token", "hw_timestamp", "gcm_device_token", "gcm_timestamp", "jp_device_token", "jp_timestamp", "unread")
     
        u.appid = appid
        u.uid = uid
        u.unread = int(unread) if unread else 0
        u.apns_timestamp = int(apns_ts) if apns_ts else 0
        u.ng_timestamp = int(ng_ts) if ng_ts else 0
        u.xg_timestamp = int(xg_ts) if xg_ts else 0
        u.mi_timestamp = int(mi_ts) if mi_ts else 0
        u.hw_timestamp = int(hw_ts) if hw_ts else 0
        u.gcm_timestamp = int(gcm_ts) if gcm_ts else 0
        u.jp_timestamp = int(jp_ts) if jp_ts else 0
        return u

    @staticmethod
    def set_bundle_user_unread(rds, appid, uid, bundle_id, unread):
        key = "users_%s_%s_%s"%(appid, uid, bundle_id)
        rds.hset(key, "unread", unread)


def push_content(sender_name, body):
    if not sender_name:
        try:
            content = json.loads(body)
            if content.has_key("text"):
                alert = content["text"]
            elif content.has_key("audio"):
                alert = u"你收到了一条消息"
            elif content.has_key("image"):
                alert = u"你收到了一张图片"
            else:
                alert = u"你收到了一条消息"
         
        except ValueError:
            alert = u"你收到了一条消息"

    else:
        try:
            sender_name = sender_name.decode("utf8")
            content = json.loads(body)
            if content.has_key("text"):
                alert = "%s:%s"%(sender_name, content["text"])
            elif content.has_key("audio"):
                alert = "%s%s"%(sender_name, u"发来一条语音消息")
            elif content.has_key("image"):
                alert = "%s%s"%(sender_name, u"发来一张图片")
            else:
                alert = "%s%s"%(sender_name, u"发来一条消息")
         
        except ValueError:
            alert = "%s%s"%(sender_name, u"发来一条消息")
    return alert
    
    
def ios_push(bundle_id, token, content, badge, extra):
    sound = "default"
    alert = content
    IOSPush.push(bundle_id, token, alert, sound, badge, extra)

def handle_im_message(msg):
    obj = json.loads(msg)
    if not obj.has_key("appid") or \
       not obj.has_key("sender") or \
       not obj.has_key("receiver") or \
       not obj.has_key("content"):
        logging.warning("invalid push msg:%s", msg)
        return

    logging.debug("push msg:%s", msg)

    appid = obj["appid"]
    sender = obj["sender"]
    receiver = obj["receiver"]

    sender_name = User.get_user_name(rds, appid, sender)

    content = ''
    no_push = False
    extra = {}
    try:
        c = json.loads(obj['content'])
        no_push = c.get('no_push', False)
        extra = c.get('push_extra', {})
        content = c.get('push_text', '')
    except ValueError:
        pass

    if not content:
        content = push_content(sender_name, obj["content"])

    if no_push:
        return

    extra["sender"] = sender

    certs = config.PUSH_CERTS
    for bundle_id in certs:
        logging.debug("bundle id:%s", bundle_id)
        cert = certs[bundle_id]
        appname = cert['name']

        u = User.get_bundle_user(rds, appid, receiver, bundle_id)
        if u is None:
            logging.info("uid:%d nonexist", receiver)
            continue
         
        #找出最近绑定的token
        ts = max(u.apns_timestamp, u.jp_timestamp)
         
        if u.apns_device_token and u.apns_timestamp == ts:
            ios_push(bundle_id, u.apns_device_token, content, u.unread + 1, extra)
            User.set_bundle_user_unread(rds, appid, receiver, bundle_id, u.unread+1)
        elif u.jp_device_token and u.jp_timestamp == ts:
            JGPush.push(bundle_id, appname, [u.jp_device_token], content, extra)
        else:
            logging.info("uid:%d has't device token", receiver)

def handle_group_message(msg):
    obj = json.loads(msg)
    if not obj.has_key("appid") or \
       not obj.has_key("sender") or \
       not obj.has_key("receivers") or \
       not obj.has_key("content") or \
       not obj.has_key("group_id"):
        logging.warning("invalid push msg:%s", msg)
        return

    logging.debug("group push msg:%s", msg)

    appid = obj["appid"]
    sender = obj["sender"]
    receivers = obj["receivers"]
    group_id = obj["group_id"]

    sender_name = User.get_user_name(rds, appid, sender)

    content = ''
    no_push = False
    try:
        c = json.loads(obj['content'])
        no_push = c.get('no_push', False)
        content = c.get('push_text')
    except ValueError:
        pass

    if not content:
        content = push_content(sender_name, obj["content"])

    if no_push:
        return

    extra = {}
    extra["sender"] = sender
    
    if group_id:
        extra["group_id"] = group_id
 

    certs = config.PUSH_CERTS
    for bundle_id in certs:
        logging.debug("bundle id:%s", bundle_id)
        cert = certs[bundle_id]
        appname = cert['name']

        apns_users = []
        jp_users = []

        for receiver in receivers:
            u = User.get_bundle_user(rds, appid, receiver, bundle_id)
            if u is None:
                logging.info("uid:%d nonexist", receiver)
                continue
             
            #找出最近绑定的token
            ts = max(u.apns_timestamp, u.jp_timestamp)
             
            if u.apns_device_token and u.apns_timestamp == ts:
                apns_users.append(u)
            elif u.jp_device_token and u.jp_timestamp == ts:
                jp_users.append(u)
            else:
                logging.info("uid:%d has't device token", receiver)

        for u in apns_users:
            ios_push(bundle_id, u.apns_device_token, content, u.unread + 1, extra)
            User.set_bundle_user_unread(rds, appid, receiver, bundle_id, u.unread+1)

        tokens = []
        for u in jp_users:
            tokens.append(u.jp_device_token)
        if tokens:
            JGPush.push(bundle_id, appname, tokens, content)


def receive_offline_message():
    while True:
        item = rds.blpop(("push_queue","group_push_queue"))
        if not item:
            continue
        q, msg = item
        if q == "push_queue":
            handle_im_message(msg)
        elif q == "group_push_queue":
            handle_group_message(msg)
        else:
            logging.warning("unknown queue:%s", q)


def main():
    logging.debug("startup")
    while True:
        try:
            receive_offline_message()
        except Exception, e:
            print_exception_traceback()
            time.sleep(1)
            continue

def print_exception_traceback():
    exc_type, exc_value, exc_traceback = sys.exc_info()
    logging.warn("exception traceback:%s", traceback.format_exc())

def init_logger(logger):
    root = logger
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)d -  %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

if __name__ == "__main__":
    init_logger(logging.getLogger(''))
    main()
