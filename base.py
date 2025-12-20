import requests
import json

# 配置信息
HARDCODED_API_KEY = "sk-vEKGv4fwTxDFuZ17vecYPCsmPNX31cLWPtRd3LUImkY90IJe"
HARDCODED_BASE_URL = "https://xh-hk.a3e.top/v1"

def test_api_connection():
    print("--- 开始测试 API 连接 ---")
    print(f"Base URL: {HARDCODED_BASE_URL}")
    
    # 构造标准的 OpenAI 格式 Chat Completion 接口地址
    # 注意：通常 Base URL 结尾是 /v1，所以我们要拼接 /chat/completions
    # 如果报错 404，可能需要检查 URL 拼接是否重复（例如 /v1/v1）
    endpoint = f"{HARDCODED_BASE_URL}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {HARDCODED_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 测试 Payload
    # 注意：有些中转服务可能不支持 'gpt-3.5-turbo'，如果报错可以尝试改成该服务商支持的模型名称
    payload = {
        "model": "gpt-3.5-turbo", 
        "messages": [
            {"role": "user", "content": "如果你能收到这条消息，请回复 '连接成功'。"}
        ],
        "stream": False
    }

    try:
        print(f"正在请求: {endpoint} ...")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        
        # 打印状态码
        print(f"HTTP 状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ 测试成功！API 调用正常。")
            print("API 返回内容:")
            # 尝试提取回复内容
            if "choices" in data and len(data["choices"]) > 0:
                print(f">>> {data['choices'][0]['message']['content']}")
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("\n❌ 测试失败。")
            print("错误响应内容:")
            print(response.text)
            
    except Exception as e:
        print(f"\n❌ 发生请求错误: {e}")

if __name__ == "__main__":
    test_api_connection()