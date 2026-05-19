import openai
import requests
import json
import time

# === НАСТРОЙКИ ===
VK_TOKEN = "vk1.a.V7Ge-D6_A_kHH6tBD4x1Ldxr3TY96oy6_dunCIwItQ1WNqJNgLSJvms9CdKZ9Rah9hZYfE90vapOrFT9GchkTmYegD9jqs8sigowjpcHGgxdOkYmh8AHzZW6U0xmxrtZGKASDEIDnQGbqX64cqykwKtBsfNYN2_Kx1fGRgnbOvt1Q-PWBL4K3jkQqvQdqs0YZv_WsrNnxyWc0Kdv0H_LOA"
USER_ID = 702040591
OPENAI_KEY = "sk-hkR_rAET2Xkgh7-lLoqRSg"
OPENAI_URL = "https://api.vsellm.ru/v1"
MODEL = "qwen/qwen3-vl-flash"
# =================

def get_group_names(token, user_id=None):
    names, offset = [], 0
    while True:
        params = {
            'access_token': token, 'v': '5.131', 'extended': 1,
            'count': 1000, 'offset': offset
        }
        if user_id: params['user_id'] = user_id
        data = requests.get('https://api.vk.com/method/groups.get', params=params).json()
        if 'error' in data:
            raise Exception(f"VK API error: {data['error'].get('error_msg')}")
        items = data['response']['items']
        if not items: break
        names.extend(g['name'] for g in items)
        if len(items) < 1000: break
        offset += 1000
        time.sleep(0.3)
    return names

def main():
    groups = get_group_names(VK_TOKEN, USER_ID)
    print(f"Groups: {len(groups)}")
    if not groups: return

    prompt = f"""Проанализируй список сообществ ВКонтакте и предложи 3-5 реальных профессий, наиболее соответствующих интересам пользователя. Используй стандартные названия профессий на русском языке. Верни ТОЛЬКО JSON-объект вида: {{"professions": ["профессия1", "профессия2"]}}.
Input: {repr(groups)}
Output ONLY JSON: {{"professions": ["prof1", "prof2"]}} (3-5 items, specific)."""

    client = openai.OpenAI(api_key=OPENAI_KEY, base_url=OPENAI_URL)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        print(resp.choices[0].message.content)
    except Exception as e:
        print(f"AI error: {e}")

if __name__ == "__main__":
    main()