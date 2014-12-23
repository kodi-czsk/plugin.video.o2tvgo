import sys
import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib
import httplib
from urlparse import urlparse
import json
import traceback
from o2tvgo import O2TVGO
from o2tvgo import AuthenticationError

params = False
try:
    ###############################################################################
    REMOTE_DBG = False
    # append pydev remote debugger
    if REMOTE_DBG:
        try:
            sys.path.append(os.environ['HOME']+r'/.xbmc/system/python/Lib/pysrc')
            import pydevd
            pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True)
        except ImportError:
            sys.stderr.write("Error: Could not load pysrc!")
            sys.exit(1)
    ###############################################################################
    _addon_ = xbmcaddon.Addon('plugin.video.o2tvgo')
    
    # First run
    if not (_addon_.getSetting("settings_init_done") == 'true'):
        DEFAULT_SETTING_VALUES = { 'send_errors' : 'false' }
        for setting in DEFAULT_SETTING_VALUES.keys():
            val = _addon_.getSetting(setting)
            if not val:
                _addon_.setSetting(setting, DEFAULT_SETTING_VALUES[setting])
        _addon_.setSetting("settings_init_done", "true")
    
    ###############################################################################
    _profile_ = xbmc.translatePath(_addon_.getAddonInfo('profile'))
    _lang_   = _addon_.getLocalizedString
    _scriptname_ = _addon_.getAddonInfo('name')
    _first_error_ = (_addon_.getSetting('first_error') == "true")
    _send_errors_ = (_addon_.getSetting('send_errors') == "true")
    _username_ = _addon_.getSetting("username")
    _password_ = _addon_.getSetting("password")
    _format_ = 'video/' + _addon_.getSetting('format').lower()
    _icon_ = xbmc.translatePath( os.path.join(_addon_.getAddonInfo('path'), 'icon.png' ) )
    _handle_ = int(sys.argv[1])
    _baseurl_ = sys.argv[0]
    
    _o2tvgo_ = O2TVGO(_username_, _password_) 
    ###############################################################################
    def log(msg, level=xbmc.LOGDEBUG):
        if type(msg).__name__=='unicode':
            msg = msg.encode('utf-8')
        xbmc.log("[%s] %s"%(_scriptname_,msg.__str__()), level)
    
    def logDbg(msg):
        log(msg,level=xbmc.LOGDEBUG)
    
    def logErr(msg):
        log(msg,level=xbmc.LOGERROR)
    ###############################################################################
    
    def _fetchChannels():
        global _o2tvgo_
        channels = None
        ex = False
        while not channels:
            try:
                channels = _o2tvgo_.live_channels()
            except AuthenticationError:
                if ex:
                    return None
                ex = True
                d = xbmcgui.Dialog()
                d.notification(_scriptname_, _lang_(30003), xbmcgui.NOTIFICATION_ERROR)
                _reload_settings()
        return channels
    
    def _fetchChannel(channel_key):
        link = None
        ex = False
        while not link:
            _o2tvgo_.access_token = _addon_.getSetting('access_token')
            channels = _fetchChannels()
            if not channels:
                return
            channel = channels[channel_key]
            try:
                link = channel.url()
                _addon_.setSetting('access_token', _o2tvgo_.access_token)
            except AuthenticationError:
                if ex:
                    return None
                ex = True
                d = xbmcgui.Dialog()
                d.notification(_scriptname_, _lang_(30003), xbmcgui.NOTIFICATION_ERROR)
                _reload_settings()
        return link, channel
    
    def _reload_settings():
        _addon_.openSettings()
        global _first_error_
        _first_error_ = (_addon_.getSetting('first_error') == "true")
        global _send_errors_
        _send_errors_ = (_addon_.getSetting('send_errors') == "true")
        global _username_
        _username_ = _addon_.getSetting("username")
        global _password_
        _password_ = _addon_.getSetting("password")
        global _o2tvgo_
        _o2tvgo_ = O2TVGO(_username_, _password_)
    
    def channelListing():
        channels = _fetchChannels()
        if not channels:
            return
        channels_sorted = sorted(channels.values(), key=lambda channel: channel.weight)
        for channel in channels_sorted:
            addDirectoryItem(channel.name, _baseurl_+ "?play=" + urllib.quote_plus(channel.channel_key), image=channel.logo_url, isFolder=False)
        xbmcplugin.endOfDirectory(_handle_, updateListing=False)
   
    def playChannel(channel_key):
        r = _fetchChannel(channel_key)
        if not r:
            return
        link, channel = r
        pl=xbmc.PlayList(1)
        pl.clear()
        li = xbmcgui.ListItem(channel.name)
        li.setThumbnailImage(channel.logo_url)
        xbmc.PlayList(1).add(link, li)
        xbmc.Player().play(pl)
   
    def addDirectoryItem(label, url, plot=None, title=None, date=None, icon=_icon_, image=None, fanart=None, isFolder=True):
        li = xbmcgui.ListItem(label)
        if not title:
            title = label
        liVideo = {'title': title}
        if image:
            li.setThumbnailImage(image)
        li.setIconImage(icon)
        li.setInfo("video", liVideo)
        xbmcplugin.addDirectoryItem(handle=_handle_, url=url, listitem=li, isFolder=isFolder)
    
    def _toString(text):
        if type(text).__name__=='unicode':
            output = text.encode('utf-8')
        else:
            output = str(text)
        return output
    
    def _sendError(params, exc_type, exc_value, exc_traceback):
        try:
            conn = httplib.HTTPSConnection('script.google.com')
            req_data = urllib.urlencode({ 'addon' : _scriptname_, 'params' : _toString(params), 'type' : exc_type, 'value' : exc_value, 'traceback' : _toString(traceback.format_exception(exc_type, exc_value, exc_traceback))})
            headers = {"Content-type": "application/x-www-form-urlencoded"}
            conn.request(method='POST', url='/macros/s/AKfycbyZfKhi7A_6QurtOhcan9t1W0Tug-F63_CBUwtfkBkZbR2ysFvt/exec', body=req_data, headers=headers)
            resp = conn.getresponse()
            while resp.status >= 300 and resp.status < 400:
                location = resp.getheader('Location')
                o = urlparse(location, allow_fragments=True)
                host = o.netloc
                conn = httplib.HTTPSConnection(host)
                url = o.path + "?" + o.query
                conn.request(method='GET', url=url)
                resp = conn.getresponse()
            if resp.status >= 200 and resp.status < 300:
                resp_body = resp.read()
                json_body = json.loads(resp_body)
                status = json_body['status']
                if status == 'ok':
                    return True
        except:
            pass
        return False
    
    def get_params():
            param=[]
            paramstring=sys.argv[2]
            if len(paramstring)>=2:
                    params=sys.argv[2]
                    cleanedparams=params.replace('?','')
                    if (params[len(params)-1]=='/'):
                            params=params[0:len(params)-2]
                    pairsofparams=cleanedparams.split('&')
                    param={}
                    for i in range(len(pairsofparams)):
                            splitparams={}
                            splitparams=pairsofparams[i].split('=')
                            if (len(splitparams))==2:
                                    param[splitparams[0]]=splitparams[1]
            return param             

    def assign_params(params):
        for param in params:
            try:
                globals()[param]=urllib.unquote_plus(params[param])
            except:
                pass
    
    play=None
    params=get_params()
    assign_params(params)
    
    if play:
        playChannel(_toString(play))
    else:
        channelListing()
except Exception as ex:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    xbmcgui.Dialog().notification(_scriptname_, _toString(exc_value), xbmcgui.NOTIFICATION_ERROR)
    if not _first_error_:
        if xbmcgui.Dialog().yesno(_scriptname_, _lang_(30500), _lang_(30501)):
            _addon_.setSetting("send_errors", "true")
            _send_errors_ = (_addon_.getSetting('send_errors') == "true")
        _addon_.setSetting("first_error", "true")
        _first_error_ = (_addon_.getSetting('first_error') == "true")
    if _send_errors_:
        if _sendError(params, exc_type, exc_value, exc_traceback):
            xbmcgui.Dialog().notification(_scriptname_, _lang_(30502), xbmcgui.NOTIFICATION_INFO)
        else:
            xbmcgui.Dialog().notification(_scriptname_, _lang_(30503), xbmcgui.NOTIFICATION_ERROR)
            traceback.print_exception(exc_type, exc_value, exc_traceback)