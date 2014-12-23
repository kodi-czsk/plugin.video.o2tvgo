#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrapper pro iVysílání České televize
"""

import httplib
import urllib
import json

__author__ = "Štěpán Ort"
__license__ = "MIT"
__version__ = "1.0.0"
__email__ = "stepanort@gmail.com"


_COMMON_HEADERS = { "X-Nangu-App-Version" : "Android#1.1.1",
                    "X-Nangu-Device-Name" : "Nexus 7",
                    "User-Agent" : "Dalvik/1.6.0 (Linux; U; Android 4.4.4; Nexus 7 Build/KTU84P)",
                    "Connection" : "Keep-Alive" }

def _toString(text):
    if type(text).__name__=='unicode':
        output = text.encode('utf-8')
    else:
        output = str(text)
    return output

# Kanál
class LiveChannel:
    
    def __init__(self, o2tv, channel_key, name, logo_url, weight):
        self._o2tv = o2tv
        self.channel_key = channel_key
        self.name = name
        self.logo_url = logo_url
        self.weight = weight

    def url(self):
        if not self._o2tv.access_token:
            self._o2tv.refresh_access_token()
        access_token = self._o2tv.access_token
        playlist = None
        while access_token:
            device_id = "a47efefe07c2173c"
            params = {"serviceType":"LIVE_TV",
              "subscriptionCode":"100195978",
              "channelKey": self.channel_key,
              "deviceType":"TABLET",
              "streamingProtocol":"HLS"}
            headers = _COMMON_HEADERS;
            headers["Cookie"] = "access_token=" + access_token + ";deviceId=" + device_id
            conn = httplib.HTTPConnection("app.o2tv.cz")
            body = urllib.urlencode(params)
            url = "/sws/server/streaming/uris.json" + "?" + body
            conn.request(method="GET", url=url, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            jsonData = json.loads(data)
            access_token = None
            if 'statusMessage' in jsonData:
                status = jsonData['statusMessage']
                if status == 'bad-credentials':
                    access_token = self._o2tv.refresh_access_token()
                else:
                    raise Exception(status)
            else:
                playlist = jsonData["uris"][0]["uri"]
        return playlist

class AuthenticationError(BaseException):
    pass

class O2TVGO:
    
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self._live_channels = {}
        self.access_token = None
    
    def refresh_access_token(self):
        if not self.username or not self.password:
            raise AuthenticationError()
        conn = httplib.HTTPSConnection("oauth.nangu.tv")
        headers = {}

        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        
        params = {'grant_type' : 'password',
                  'client_id' : 'tef-web-portal-etnetera',
                  'client_secret' : '2b16ac9984cd60dd0154f779ef200679',
                  'username' : self.username,
                  'password' : self.password,
                  'platform_id' : '231a7d6678d00c65f6f3b2aaa699a0d0',
                  'language' : 'cs'}

        body = urllib.urlencode(params)
        conn.request("POST", "/oauth/token", body, headers)
        resp = conn.getresponse()
        data = resp.read()
        j = json.loads(data)
        if 'error' in j:
            error = j['error']
            if error == 'authentication-failed':
                raise AuthenticationError()
            else:
                raise Exception(error)
        self.access_token = j["access_token"]
        self.expires_in = j["expires_in"]
        return self.access_token
    
    def live_channels(self):
        if len(self._live_channels) == 0:
            conn = httplib.HTTPSConnection('www.o2tv.cz')
            conn.request(method="GET", url='/mobile/tv/channels-all.json', headers=_COMMON_HEADERS)
            resp = conn.getresponse()
            json_string = resp.read()
            j = json.loads(json_string);
            items = j['channelsAll']['items']
            for item in items:
                channel_key = _toString(item['channelKey'])
                name = _toString(item['name'])
                logo_url = "http://www.o2tv.cz" + item['logoUrl']
                weight = item['weight']
                live = item['live']
                if live:
                    self._live_channels[channel_key] = LiveChannel(self, channel_key, name, logo_url, weight)
        return self._live_channels
