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

rds = redis.StrictRedis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB)

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
    
    
def ios_push(appid, token, content, badge, extra):
    sound = "default"
    alert = content
    IOSPush.push(appid, token, alert, sound, badge, extra)


def handle_im_message(msg):
    obj = json.loads(msg)
    if not obj.has_key("appid") or not obj.has_key("sender") or \
       (not obj.has_key("receiver") and not obj.has_key("receivers")):
        logging.warning("invalid push msg:%s", msg)
        return

    logging.debug("push msg:%s", msg)

    appid = obj["appid"]
    sender = obj["sender"]

    receivers = []
    if obj.has_key("receiver"):
        receivers = [obj["receiver"]]
    elif obj.has_key("receivers"):
        receivers = obj["receivers"]
        
    group_id = obj["group_id"] if obj.has_key("group_id") else 0

    sender_name = User.get_user_name(rds, appid, sender)
    content = push_content(sender_name, obj["content"])

    extra = {}
    extra["sender"] = sender
    
    if group_id:
        extra["group_id"] = group_id

    appname = config.APPNAME

    apns_users = []
    jp_users = []
    xg_users = []
    hw_users = []
    gcm_users = []
    mi_users = []

    for receiver in receivers:
        u = User.get_user(rds, appid, receiver)
        if u is None:
            logging.info("uid:%d nonexist", receiver)
            continue
         
        if group_id:
            quiet = User.get_user_notification_setting(rds, appid, receiver, group_id)
            if quiet:
                logging.info("uid:%d group id:%d is in quiet mode", receiver, group_id)
                continue

        #找出最近绑定的token
        ts = max(u.apns_timestamp, u.xg_timestamp, u.ng_timestamp, 
                 u.mi_timestamp, u.hw_timestamp, u.gcm_timestamp, u.jp_timestamp)

        if u.apns_device_token and u.apns_timestamp == ts:
            apns_users.append(u)
        elif u.xg_device_token and u.xg_timestamp == ts:
            xg_users.append(u)
        elif u.mi_device_token and u.mi_timestamp == ts:
            mi_users.append(u)
        elif u.hw_device_token and u.hw_timestamp == ts:
            hw_users.append(u)
        elif u.gcm_device_token and u.gcm_timestamp == ts:
            gcm_users.append(u)
        elif u.jp_device_token and u.jp_timestamp == ts:
            jp_users.append(u)
        else:
            logging.info("uid:%d has't device token", receiver)
            continue

    for u in xg_users:
        XGPush.push(appid, token, content, extra)

    for u in hw_users:
        HuaWeiPush.push(appid, appname, u.hw_device_token, content)

    for u in gcm_users:
        GCMPush.push(appid, appname, u.gcm_device_token, content)

    for u in mi_users:
        MiPush.push(appid, appname, u.mi_device_token, content)
    
    for u in apns_users:
        ios_push(appid, u.apns_device_token, content, u.unread + 1, extra)
        User.set_user_unread(rds, appid, receiver, u.unread+1)

    tokens = []
    for u in jp_users:
        tokens.append(u.jp_device_token)
    if tokens:
        JGPush.push(appid, appname, tokens, content)


def handle_voip_message(msg):
    obj = json.loads(msg)
    appid = obj["appid"]
    sender = obj["sender"]
    receiver = obj["receiver"]

    sender_name = User.get_user_name(rds, appid, sender)
    u = User.get_user(rds, appid, receiver)
    if u is None:
        logging.info("uid:%d nonexist", receiver)
        return

    #找出最近绑定的token
    ts = max(u.apns_timestamp, u.xg_timestamp, u.ng_timestamp, 
             u.mi_timestamp, u.hw_timestamp, u.gcm_timestamp, u.jp_timestamp)

    if sender_name:
        sender_name = sender_name.decode("utf8")
        content = "%s:%s"%(sender_name, u"请求与你通话")
    else:
        content = u"你的朋友请求与你通话"

    appname = config.APPNAME
    if u.apns_device_token and u.apns_timestamp == ts:
        sound = "apns.caf"
        badge = u.unread
        IOSPush.push(appid, u.apns_device_token, content, badge, sound, {})
    elif u.gcm_device_token and u.gcm_timestamp == ts:
        GCMPush.push(appid, appname, u.gcm_device_token, content)
    elif u.jp_device_token and u.jp_timestamp == ts:
        JGPush.push(appid, appname, [u.jp_device_token], content)
    else:
        logging.info("uid:%d has't device token", receiver)


def system_message_content(body):
    try:
        obj = json.loads(body)
        if obj['operation'] == "Request":
            src_uid = int(obj['sourceUserId'])
            sender_name = obj.get('sourceUserName', '')
            if sender_name:
                sender_name = sender_name.decode("utf8")
                content = "%s:%s"%(sender_name, u"请求加你为好友")
            else:
                content = "你收到一条好友请求"
            return content
        elif obj['operation'] == 'OfficialAccountNotice':
            return obj['tips']

    except ValueError:
        return None


def handle_system_message(msg):
    obj = json.loads(msg)
    appid = obj["appid"]
    receiver = obj["receiver"]
    body = obj["content"]

    appname = config.APPNAME

    u = User.get_user(rds, appid, receiver)
    if u is None:
        logging.info("uid:%d nonexist", receiver)
        return

    content = system_message_content(body)
    if not content:
        logging.info("can't push system message:%s", msg)
        return

    
    #找出最近绑定的token
    ts = max(u.apns_timestamp, u.xg_timestamp, u.ng_timestamp, 
             u.mi_timestamp, u.hw_timestamp, u.gcm_timestamp, u.jp_timestamp)

    if u.apns_device_token and u.apns_timestamp == ts:
        sound = "apns.caf"
        IOSPush.push(appid, u.apns_device_token, content, u.unread, sound, {})
        User.set_user_unread(rds, appid, receiver, u.unread+1)
    elif u.gcm_device_token and u.gcm_timestamp == ts:
        GCMPush.push(appid, appname, u.gcm_device_token, content)
    elif u.jp_device_token and u.jp_timestamp == ts:
        JGPush.push(appid, appname, [u.jp_device_token], content)
    else:
        logging.info("uid:%d has't device token", receiver)


def receive_offline_message():
    while True:
        item = rds.blpop(("push_queue", "voip_push_queue", "system_push_queue"))
        if not item:
            continue
        q, msg = item
        if q == "push_queue":
            handle_im_message(msg)
        elif q == "voip_push_queue":
            handle_voip_message(msg)
        elif q == "system_push_queue":
            handle_system_message(msg)
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
