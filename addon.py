# Module: addon.py
# Author: Fabio F. / 2021 ARSAT
# License: GNU General Public License, Version 3, http://www.gnu.org/licenses/

import xbmcgui
import xbmcplugin
import xbmcaddon
import json
import os
import requests
import base64
import hashlib
from urllib.parse import urlencode, parse_qsl, quote_plus as quote


PLUGIN_NAME = 'plugin.video.contar'
API_URL     = 'https://api.cont.ar/api/v2'

addon_url = sys.argv[0]
addon_handle = int(sys.argv[1])
addon = xbmcaddon.Addon(PLUGIN_NAME)
addon_name = addon.getAddonInfo('name')
addon_icon = addon.getAddonInfo('icon')
addon_version = addon.getAddonInfo('version')
art_path = os.path.join(addon.getAddonInfo('path'), 'resources', 'media')


def translation(id):
    return addon.getLocalizedString(id).encode('utf-8')


def init_session():
    email = xbmcgui.Dialog().input(translation(30001), addon.getSetting('email'), xbmcgui.INPUT_ALPHANUM)
    if email == '': return False
    addon.setSetting('email', email)
    password = xbmcgui.Dialog().input(translation(30002), '', xbmcgui.INPUT_ALPHANUM, xbmcgui.ALPHANUM_HIDE_INPUT)
    if password == '': return False

    url = f"{API_URL}/authenticate"
    r = requests.post(url, json={'email': email, 'password': password})
    data = r.json()
    if r.ok:
        addon.setSetting('token', data['token'])
        return True
    else:
        addon.setSetting('token', '')
        xbmcgui.Dialog().ok(translation(30003), data['error'])
        return False
        

def authenticate():
    profile = None
    if addon.getSetting('token') != '':
        profile = json_request('user')
    if profile == None:
        if not init_session():
            sys.exit(0)
        profile = json_request('user')
        if profile == None:
            xbmcgui.Dialog().ok(translation(30003), 'Falló login (no debería suceder)')
            sys.exit(0)


def add_directory_item(name, query, image=None, isFolder=True, art=None, info=None, endpoint=None):
    url = f'{addon_url}?action={query}'
    if endpoint: url += f"&endpoint={endpoint}"
    list_item = xbmcgui.ListItem(label=name)
    if image:
        thumb = os.path.join(art_path, image)
        list_item.setArt({'icon': thumb, 'thumb': thumb})
    if art: list_item.setArt(art)
    if info: list_item.setInfo('video', info)
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=isFolder)


def root_menu():
    authenticate()
    xbmc.log(f"CONTAR - root_menu()", level=xbmc.LOGDEBUG)
    add_directory_item(translation(30004), 'live', 'live.png')
    add_directory_item(translation(30005), 'list_channels', 'channels.png')
    add_directory_item(translation(30012), 'list_prods', 'my-list.png', endpoint="mylist")
    add_directory_item(translation(30013), 'search', 'search.png')
    add_directory_item(translation(30014), 'close_session', 'close-session.png', False)
    xbmcplugin.endOfDirectory(addon_handle)


def live(params):
    resp = json_request("live")
    for item in resp['data']:
        if item["type"] != "STREAM": continue
        list_item = xbmcgui.ListItem(label=item['title'])
        list_item.setArt(
            {'thumb': item['avatar'],
             'poster': item['mobile_image'],
             'icon': item['mobile_image'],
             'banner': item['mobile_image'],
             'fanart': item['cover']})
        list_item.setInfo('video', {'title': item['title']})
        list_item.setProperty('IsPlayable', 'true')
        url = f"{addon_url}?action=play&source={item['hls']}"
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=False)    
    xbmcplugin.endOfDirectory(addon_handle)


def list_channels(params):
    resp = json_request("channel/list")
    for item in resp['data']:
        list_item = xbmcgui.ListItem(label=item['name'])
        list_item.setArt(
            {'thumb': item['avatar'],
             'poster': item['logoImage'],
             'icon': item['logoImage'],
             'banner': item['tabletImage'],
             'fanart': item['tabletImage']})
        url = f"{addon_url}?action=list_prods&endpoint=channel/series/{item['id']}"
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(addon_handle)
    
    
def get_hls(streams):
    for stream in streams:
        if stream['type'] == 'HLS':
            return stream['url']
    return None


def list_prods(params):
    resp = json_request(params["endpoint"])
    for item in resp['data']:
        list_item = xbmcgui.ListItem(label=item['name'])
        list_item.setArt(
            {'thumb': item['seasonImage'],
             'poster': item['seasonImage'],
             'icon': item['seasonImage'],
             'banner': item['wallImage'],
             'fanart': item['smartImage']})
        info = {
            'title': item['name'],
            'year': item['year'],
            'plot': item['story']
            }
        q = item["totalSeasons"] * item["totalEpisodes"]
        if q > 1:
            url = f"{addon_url}?action=list_epis&endpoint=serie/{item['uuid']}"
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=True)    
        else:
            r2 = json_request(f"serie/{item['uuid']}")
            if hls := get_hls(r2['data']['vuuid']['data']['streams']):
                list_item.setInfo('video', info)
                list_item.setProperty('IsPlayable', 'true')
                url = f"{addon_url}?action=play&source={hls}"
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=False)    
    xbmcplugin.endOfDirectory(addon_handle)


def list_epis(params):
    resp = json_request(params["endpoint"])
    for season in resp['data']['seasons']['data']:
        for item in season['videos']['data']:
            list_item = xbmcgui.ListItem(label=item['name'])
            list_item.setArt(
                {'thumb': item['posterImage'],
                 'poster': item['posterImage'],
                 'icon': item['posterImage'],
                 'fanart': season['seasonImage']})
            info = {
                'title': item['name'],
                'plot': item['synopsis']
                }
            if hls := get_hls(item['streams']):
                list_item.setInfo('video', info)
                list_item.setProperty('IsPlayable', 'true')
                url = f"{addon_url}?action=play&source={hls}"
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=list_item, isFolder=False)    
    xbmcplugin.endOfDirectory(addon_handle)


def close_session(params):
    addon.setSetting('token', '')
    xbmc.executebuiltin('ActivateWindow(Videos,addons://sources/video/)')


def search(params):
    query = xbmcgui.Dialog().input(translation(30027))
    if query == '': return
    params['endpoint'] = f'search/videos?query={quote(query)}'
    list_prods(params)


def play(params):
    play_item = xbmcgui.ListItem(path=params['source'])
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem=play_item)


def decode_json(response):
    try:
        data = response.json()
        if response.ok:
            return data, ''
        errmsg = data['error'] or 'Error (json)'
    except:
        errmsg = response.content or 'Error (html)'
    return None, errmsg


def show_error(title, status, message):
    try:
        xbmc.log(f"ERROR [{PLUGIN_NAME}]: {title} - code ({status}) - {message.encode('utf8', 'ignore')}", level=xbmc.LOGDEBUG)
        xbmcgui.Dialog().ok(f"{title} ({status})", message)
    except:
        pass


def json_request(path):
    xbmc.log(f"CONTAR - json_request() path:{path}", level=xbmc.LOGDEBUG)
    token = addon.getSetting('token')
    url = f"{API_URL}/{path}"
    headers = {'Authorization': 'Bearer ' + token}
    xbmc.log(f"CONTAR - json_request() URL:{url}", level=xbmc.LOGDEBUG)
    r = requests.get(url, headers=headers)
    retries = 5

    while r.status_code == 422 and retries > 0:
        r = requests.get(url, headers=headers)
        retries -= 1
        
    if r.status_code == 422:
        # special case used during login to test a token
        if path == 'user': return None
        # in the very unlikely situation token expires, user must restart
        xbmcgui.Dialog().ok(translation(30029), translation(30030))
        close_session([])
        sys.exit(0)

    # raise for status
    elif r.status_code >= 400:
        show_error(translation(30037), r.status_code, r.content)
        close_session([])
        sys.exit(0)

    if not r.content: return None
    data, errmsg = decode_json(r)
    if not data:
        show_error(translation(30037), r.status_code, errmsg)
        sys.exit(0)
    return data


if __name__ == '__main__':
    params = dict(parse_qsl(sys.argv[2][1:]))
    if params:
        globals()[params['action']](params)
    else:
        root_menu()
