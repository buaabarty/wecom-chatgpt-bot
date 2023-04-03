import requests

access_token = "Hf-Z5zTUySuvsC9rRITl8wJxqccnbJCriDsVfC-ToEq7QX7Xut7Ud9ACUE3ZRQJ9N5OXpovEeiBLB8Mfr-ZbrD7kCDp_h1R-Bgq3xWp5MzPPi38yU0YQ0XSpNNXrKwhcH2fFa5CY3H8lP6VBphnq0jpqIs2mfQcsmhoZuo_9ERnyBgKTnwl77jRgto7dT56RduKcfEX-RXFGLflaJaIrEA"

url = f'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}'
data = {
    "touser": "YangBoYang",
    "msgtype": "text",
    "agentid": 1000002,  # 应用的AgentID
    "text": {
        "content": "您的消息内容"
    },
    "safe": 0,
    "enable_id_trans": 0,
    "enable_duplicate_check": 0,
}
    
response = requests.post(url, json=data)
print(response.content)