from celery import shared_task
import requests
from redis import Redis
from revChatGPT.V3 import Chatbot
from django.conf import settings
from .utils import ExpiringDict
from googleapiclient.discovery import build
from trafilatura import fetch_url, extract


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

def send_with_content(chatbot, contents, prompt):
    if len(contents) > 0:
        chatbot.add_to_conversation('请先阅读以下几段网络上搜索到的材料，然后回答问题：\n' + contents[0][:1024], 'user')
    if len(contents) > 1:
        for content in contents[1:]:
            chatbot.add_to_conversation(content[:1024], 'user')
    response = ""
    for query in chatbot.ask_stream('请根据以上信息，并结合你自己目前掌握的知识库，回答一个问题：\n' + prompt):
        response += query
    return response

def extract_main_content(url):
    try:
        downloaded = fetch_url(url)
        result = extract(downloaded)
        return result
    except Exception as e:
        print(e)
        return None

def calculate(chatbot, query):
    service = build("customsearch", "v1", developerKey=settings.GOOGLE_API_KEY)
    result = (
        service.cse()
        .list(q = query, cx = settings.CUSTOM_SEARCH_ENGINE_ID, num = settings.SEARCH_OPTIONS_COUNT)
        .execute()
    )
    search_results = result.get("items", [])
    search_results_links = [item["link"].strip() for item in search_results]
    contents = []
    for url in search_results_links:
        ret = extract_main_content(url)
        if ret is not None:
            contents.append(ret)
    if len(contents) > 0:
        return send_with_content(chatbot, contents, query)
    else:
        return ''

@shared_task
def send_message_to_wechat(message, user):
    if any(substring in message for substring in settings.SEARCH_TOKEN):
        for substring in settings.SEARCH_TOKEN:
            message = message.replace(substring, "")
        chatbots.set(user, Chatbot(temperature=0.1, api_key=settings.OPENAI_API_KEY, engine=settings.OPENAI_GPT_ENGINE, timeout=120, system_prompt=settings.OPENAI_SEARCH_PROMPT))
        chatbot = chatbots.get(user)
        try:
            chatres = calculate(chatbot, message)
        except Exception as e:
            print(e)
            chatres = settings.CHAT_GOOGLE_ERROR_MESSAGE
    elif message == settings.CHAT_RESET_MESSAGE: # restart a new conversation after recieved specific message
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
