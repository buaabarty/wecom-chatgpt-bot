import base64
import string
import random
import hashlib
import time
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import xml.etree.cElementTree as ET
import socket
import six

WXBizMsgCrypt_OK = 0
WXBizMsgCrypt_ValidateSignature_Error = -40001
WXBizMsgCrypt_ParseXml_Error = -40002
WXBizMsgCrypt_ComputeSignature_Error = -40003
WXBizMsgCrypt_IllegalAesKey = -40004
WXBizMsgCrypt_ValidateCorpid_Error = -40005
WXBizMsgCrypt_EncryptAES_Error = -40006
WXBizMsgCrypt_DecryptAES_Error = -40007
WXBizMsgCrypt_IllegalBuffer = -40008
WXBizMsgCrypt_EncodeBase64_Error = -40009
WXBizMsgCrypt_DecodeBase64_Error = -40010
WXBizMsgCrypt_GenReturnXml_Error = -40011

class FormatException(Exception):
    pass

def throw_exception(message, exception_class=FormatException):
    raise exception_class(message)

def to_text(value, encoding='utf-8'):
    if not value:
        return ''
    if isinstance(value, six.text_type):
        return value
    if isinstance(value, six.binary_type):
        return value.decode(encoding)
    return six.text_type(value)

def to_binary(value, encoding='utf-8'):
    if not value:
        return b''
    if isinstance(value, six.binary_type):
        return value
    if isinstance(value, six.text_type):
        return value.encode(encoding)
    return to_text(value).encode(encoding)

def byte2int(c):
    if six.PY2:
        return ord(c)
    return c

class SHA1:
    def getSHA1(self, token, timestamp, nonce, encrypt):
        try:
            sortlist = [token, timestamp, nonce, to_text(encrypt)]
            sortlist.sort()
            sha = hashlib.sha1()
            sha.update("".join(sortlist).encode("ascii"))
            return WXBizMsgCrypt_OK, sha.hexdigest()
        except Exception as e:
            print(e)
            return WXBizMsgCrypt_ComputeSignature_Error, None


class XMLParse:
    AES_TEXT_RESPONSE_TEMPLATE = """<xml>
<Encrypt><![CDATA[%(msg_encrypt)s]]></Encrypt>
<MsgSignature><![CDATA[%(msg_signaturet)s]]></MsgSignature>
<TimeStamp>%(timestamp)s</TimeStamp>
<Nonce><![CDATA[%(nonce)s]]></Nonce>
</xml>"""

    def extract(self, xmltext):
        try:
            xml_tree = ET.fromstring(xmltext)
            encrypt = xml_tree.find("Encrypt")
            touser_name = xml_tree.find("ToUserName")
            return WXBizMsgCrypt_OK, encrypt.text, touser_name.text
        except Exception as e:
            print(e)
            return WXBizMsgCrypt_ParseXml_Error, None, None

    def generate(self, encrypt, signature, timestamp, nonce):
        resp_dict = {
            'msg_encrypt': encrypt,
            'msg_signaturet': signature,
            'timestamp': timestamp,
            'nonce': nonce,
        }
        resp_xml = self.AES_TEXT_RESPONSE_TEMPLATE % resp_dict
        return resp_xml


class PKCS7Encoder():
    block_size = 32

    def encode(self, text):
        text_length = len(text)
        amount_to_pad = self.block_size - (text_length % self.block_size)
        if amount_to_pad == 0:
            amount_to_pad = self.block_size
        pad = to_binary(chr(amount_to_pad))
        return text + pad * amount_to_pad

    def decode(self, decrypted):
        pad = byte2int(decrypted[-1])
        if pad < 1 or pad > 32:
            pad = 0
        return decrypted[:-pad]


class Prpcrypt(object):
    def __init__(self, key):
        self.key = key
        backend = default_backend()
        self.cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(key[:16]),
            backend=backend
        )

    def encrypt(self, text, corpid):
        text = to_binary(text)
        tmp_list = []
        tmp_list.append(to_binary(self.get_random_str()))
        length = struct.pack(b'I', socket.htonl(len(text)))
        tmp_list.append(length)
        tmp_list.append(text)
        tmp_list.append(to_binary(corpid))
        text = b''.join(tmp_list)
        pkcs7 = PKCS7Encoder()
        text = pkcs7.encode(text)
        try:
            encryptor = self.cipher.encryptor()
            ciphertext = to_binary(encryptor.update(text) + encryptor.finalize())
            return WXBizMsgCrypt_OK, base64.b64encode(ciphertext)
        except Exception as e:
            print(e)
            return WXBizMsgCrypt_EncryptAES_Error, None

    def decrypt(self, text, corpid):
        try:
            decryptor = self.cipher.decryptor()
            plain_text = decryptor.update(base64.b64decode(text)) + decryptor.finalize()
        except Exception as e:
            print(e)
            return WXBizMsgCrypt_DecryptAES_Error, None
        try:
            pad = plain_text[-1]
            content = plain_text[16:-pad]
            xml_len = socket.ntohl(struct.unpack("I", content[: 4])[0])
            xml_content = content[4: xml_len + 4]
            from_corpid = content[xml_len + 4:].decode("utf8")
        except Exception as e:
            print(e)
            return WXBizMsgCrypt_IllegalBuffer, None
        if from_corpid != corpid:
            return WXBizMsgCrypt_ValidateCorpid_Error, None
        return 0, xml_content

    def get_random_str(self):
        rule = string.ascii_letters + string.digits
        str = random.sample(rule, 16)
        return "".join(str)

class WXBizMsgCrypt(object):
    def __init__(self, sToken, sEncodingAESKey, sCorpId):
        try:
            self.key = base64.b64decode(sEncodingAESKey + "=")
            assert len(self.key) == 32
        except:
            throw_exception("[error]: EncodingAESKey unvalid !", FormatException)
        self.m_sToken = sToken
        self.m_sCorpid = sCorpId

    def VerifyURL(self, sMsgSignature, sTimeStamp, sNonce, sEchoStr):
        sha1 = SHA1()
        ret, signature = sha1.getSHA1(self.m_sToken, sTimeStamp, sNonce, sEchoStr)
        if ret != 0:
            return ret, None
        if not signature == sMsgSignature:
            return WXBizMsgCrypt_ValidateSignature_Error, None
        pc = Prpcrypt(self.key)
        ret, sReplyEchoStr = pc.decrypt(sEchoStr, self.m_sCorpid)
        return ret, sReplyEchoStr

    def EncryptMsg(self, sReplyMsg, sNonce, timestamp=None):
        pc = Prpcrypt(self.key)
        ret, encrypt = pc.encrypt(sReplyMsg, self.m_sCorpid)
        if ret != 0:
            return ret, None
        if timestamp is None:
            timestamp = str(int(time.time()))
        sha1 = SHA1()
        ret, signature = sha1.getSHA1(self.m_sToken, timestamp, sNonce, encrypt)
        if ret != 0:
            return ret, None
        xmlParse = XMLParse()
        return ret, xmlParse.generate(encrypt, signature, timestamp, sNonce)

    def DecryptMsg(self, sPostData, sMsgSignature, sTimeStamp, sNonce):
        xmlParse = XMLParse()
        ret, encrypt, touser_name = xmlParse.extract(sPostData)
        if ret != 0:
            return ret, None
        sha1 = SHA1()
        ret, signature = sha1.getSHA1(self.m_sToken, sTimeStamp, sNonce, encrypt)
        if ret != 0:
            return ret, None
        if not signature == sMsgSignature:
            return WXBizMsgCrypt_ValidateSignature_Error, None
        pc = Prpcrypt(self.key)
        ret, xml_content = pc.decrypt(encrypt, self.m_sCorpid)
        return ret, xml_content
