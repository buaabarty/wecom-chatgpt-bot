from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from wechatpy.enterprise.crypto import WeChatCrypto
import hashlib
from wechatpy.enterprise import parse_message
from wechatpy.exceptions import InvalidSignatureException
import xml.etree.ElementTree as ET
from .WXBizMsg import WXBizMsgCrypt
from .tasks import send_message_to_wechat

def check_signature(token, signature, timestamp, nonce):
    sorted_params = sorted([token, timestamp, nonce])
    sha1 = hashlib.sha1()
    sha1.update(''.join(sorted_params).encode('utf-8'))
    return sha1.hexdigest() == signature

def get_from_username(xml_string):
    root = ET.fromstring(xml_string)
    from_username = root.find('FromUserName').text
    return from_username

@csrf_exempt
def wechat(request):
    signature = request.GET.get('msg_signature')
    timestamp = request.GET.get('timestamp')
    nonce = request.GET.get('nonce')
    echostr = request.GET.get('echostr')
    wxcpt = WXBizMsgCrypt(settings.WEWORK_TOKEN, settings.WEWORK_AES_KEY, settings.WEWORK_CORP_ID)
    try:
        check_signature(settings.WEWORK_TOKEN, signature, timestamp, nonce)
    except InvalidSignatureException:
        return HttpResponse(status = 403)
    if request.method == 'GET':
        _, sEchoStr = wxcpt.VerifyURL(signature, timestamp, nonce, echostr)
        return HttpResponse(sEchoStr, content_type="text/plain")
    elif request.method == 'POST':
        crypto = WeChatCrypto(settings.WEWORK_TOKEN, settings.WEWORK_AES_KEY, settings.WEWORK_CORP_ID)
        decrypted_xml = crypto.decrypt_message(request.body, signature, timestamp, nonce)
        msg = parse_message(decrypted_xml)
        send_message_to_wechat.delay(msg.content, get_from_username(decrypted_xml))
        return HttpResponse("", content_type="text/plain")
