from celery import shared_task
import requests
from redis import Redis
from revChatGPT.V3 import Chatbot
from django.conf import settings
from .utils import ExpiringDict

cache = ExpiringDict(1800) # set the expiring time of access_token as 1800 seconds
redis_client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
chatbots = ExpiringDict(1800) # set the expiring time of conversation as 1800 seconds

def set_access_token(token, expires_in):
    redis_client.set('wecom_access_token_bot', token, ex=expires_in)

def get_access_token():
    return redis_client.get('wecom_access_token_bot')

def request_access_token(corp_id, corp_secret):
    url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp_id}&corpsecret={corp_secret}'
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        if 'access_token' in result:
            return result['access_token'], result['expires_in']
        else:
            print(f"Error: {result.get('errmsg')}")
    else:
        print(f"Request failed with status code {response.status_code}")

def fetch_access_token(corp_id, corp_secret):
    access_token = get_access_token()
    if access_token:
        return access_token.decode()
    else:
        token, expires_in = request_access_token(corp_id, corp_secret)
        if token:
            set_access_token(token, expires_in)
            return token
        else:
            print("Failed to get access token.")

@shared_task
def send_message_to_wechat(message, user):
    if message == settings.CHAT_RESET_MESSAGE: # restart a new conversation after recieved specific message
        if chatbots.get(user) is not None:
            chatbots.set(user, Chatbot(api_key=settings.OPENAI_API_KEY, timeout=60, engine=settings.OPENAI_GPT_ENGINE, system_prompt=settings.OPENAI_SYSTEM_PROMPT))
        chatres = settings.CHAT_RESET_MESSAGE_RESULT
    else:
        chatbot = chatbots.get(user)
        if chatbot is None:
            chatbots.set(user, Chatbot(api_key=settings.OPENAI_API_KEY, timeout=60, engine=settings.OPENAI_GPT_ENGINE, system_prompt=settings.OPENAI_SYSTEM_PROMPT))
            chatbot = chatbots.get(user)
        try:
            chatres = chatbot.ask(message)
        except Exception as e:
            print(f"exception: {str(e)}")
            chatres = settings.CHAT_ERROR_MESSAGE
    access_token = fetch_access_token(settings.WEWORK_CORP_ID, settings.WEWORK_CORP_SECRET)
    url = f'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}'
    data = {
        "touser": user,
        "msgtype": "text",
        "agentid": settings.WEWORK_AGENT_ID,  # 应用的AgentID
        "text": {
            "content": chatres
        },
        "safe": 0,
        "enable_id_trans": 0,
        "enable_duplicate_check": 0,
    }
    requests.post(url, json=data, timeout=20)
