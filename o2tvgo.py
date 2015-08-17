#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrapper pro iVysílání České televize
"""

import httplib
import urllib
import json
import requests

__author__ = "Štěpán Ort"
__license__ = "MIT"
__version__ = "1.1.4"
__email__ = "stepanort@gmail.com"


_COMMON_HEADERS = { "X-Nangu-App-Version" : "Android#1.2.9",
                    "X-Nangu-Device-Name" : "Nexus 7",
                    "User-Agent" : "Dalvik/2.1.0 (Linux; U; Android 5.1.1; Nexus 7 Build/LMY47V)",
                    "Accept-Encoding": "gzip",
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
        self.weight = weight
        self.logo_url = logo_url

    def url(self):
        if not self._o2tv.access_token:
            self._o2tv.refresh_access_token()
        access_token = self._o2tv.access_token
        if not self._o2tv.subscription_code:
            self._o2tv.refresh_configuration()
        subscription_code = self._o2tv.subscription_code
        playlist = None
        while access_token:
            params = {"serviceType":"LIVE_TV",
              "subscriptionCode":subscription_code,
              "channelKey": self.channel_key,
              "deviceType":"TABLET",
              "streamingProtocol":"HLS"}
            headers = _COMMON_HEADERS
            cookies = { "access_token": access_token, "deviceId": self._o2tv.device_id }
            req = requests.get('http://app.o2tv.cz/sws/server/streaming/uris.json', params=params, headers=headers, cookies=cookies)
            jsonData = req.json()
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

class TooManyDevicesError(BaseException):
    pass

class O2TVGO:

    def __init__(self, device_id, username, password):
        self.username = username
        self.password = password
        self._live_channels = {}
        self.access_token = None
        self.subscription_code = None
        self.offer = None
        self.device_id = device_id

    def refresh_access_token(self):
        if not self.username or not self.password:
            raise AuthenticationError()
        headers = _COMMON_HEADERS
        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        data = {  'grant_type' : 'password',
                  'client_id' : 'tef-web-portal-etnetera',
                  'client_secret' : '2b16ac9984cd60dd0154f779ef200679',
                  'username' : self.username,
                  'password' : self.password,
                  'platform_id' : '231a7d6678d00c65f6f3b2aaa699a0d0',
                  'language' : 'cs'}
        req = requests.post('https://oauth.nangu.tv/oauth/token', data=data, headers=headers, verify=False)
        j = req.json()
        if 'error' in j:
            error = j['error']
            if error == 'authentication-failed':
                raise AuthenticationError()
            else:
                raise Exception(error)
        self.access_token = j["access_token"]
        self.expires_in = j["expires_in"]
        return self.access_token

    def refresh_configuration(self):
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        headers = _COMMON_HEADERS
        cookies = { "access_token": access_token, "deviceId": self.device_id }
        req = requests.get('http://app.o2tv.cz/sws/subscription/settings/subscription-configuration.json', headers=headers, cookies=cookies)
        j = req.json()
        if 'errorMessage' in j:
            errorMessage = j['errorMessage']
            statusMessage = j['statusMessage']
            if statusMessage == 'unauthorized-device':
                raise TooManyDevicesError()
            else:
                raise Exception(error)
        self.subscription_code = _toString(j["subscription"])
        self.offer = j["billingParams"]["offers"]
        self.tariff = j["billingParams"]["tariff"]

    def live_channels(self):
        if not self.access_token:
            self.refresh_access_token()
        access_token = self.access_token
        if not self.offer:
            self.refresh_configuration()
        offer = self.offer
        if not self.tariff:
            self.refresh_configuration()
        tariff = self.tariff
        if len(self._live_channels) == 0:
            headers = _COMMON_HEADERS
            cookies = { "access_token": access_token, "deviceId": self.device_id }
            params = { "locality":"DEFAULT",
                "tariff": tariff,
                "isp": "1",
                "language": "ces",
                "deviceType": "MOBILE",
                "liveTvStreamingProtocol":"HLS",
                "offer": offer}
            req = requests.get('http://app.o2tv.cz/sws/server/tv/channels.json', params=params, headers=headers, cookies=cookies)
            j = req.json()
            purchased_channels = j['purchasedChannels']
            items = j['channels']
            for channel_id, item in items.iteritems():
                if channel_id in purchased_channels:
                    live = item['liveTvPlayable']
                    if live:
                        channel_key = _toString(item['channelKey'])
                        logo = _toString(item['logo'])
                        name = _toString(item['channelName'])
                        weight = item['weight']
                        self._live_channels[channel_key] = LiveChannel(self, channel_key, name, logo, weight)
            done = False
            offset = 0
            while not done:
                headers = _COMMON_HEADERS
                params = { "language": "ces",
                    "audience": "over_18",
                    "channelKey": self._live_channels.keys(),
                    "limit": 30,
                    "offset": offset}
                req = requests.get('http://www.o2tv.cz/mobile/tv/channels.json', params=params, headers=headers)
                j = req.json()
                items = j['channels']['items']
                for item in items:
                    item = item['channel']
                    channel_key = _toString(item['channelKey'])
                    if 'logoUrl' in item.keys():
                        logo_url = "http://www.o2tv.cz" + item['logoUrl']
                        self._live_channels[channel_key].logo_url = logo_url
                offset += 30
                total_count = j['channels']['totalCount']
                if offset >= total_count:
                    done = True
        return self._live_channels
