import aiohttp
from loguru import logger # 假设你使用的是 loguru，如果是标准 logging 请替换

async def request_ai(provider_config: dict, target_text: str, additional_prompt: str = "") -> str:
    """
    负责将消息文本和用户的 prompt 组装，并请求大模型 API。
    成功则返回生成的字符串，失败则抛出异常。
    """
    api_key = provider_config.get("api_key")
    api_endpoint = provider_config.get("api_endpoint")
    no_sensitive = provider_config.get("no_sensitive", False)
    model = provider_config.get("model", "gpt-3.5-turbo") # 建议配置文件加个 model 字段兜底

    if not api_key or not api_endpoint:
        raise ValueError("AI Provider 配置缺失 api_key 或 api_endpoint")

    # 1. 组装 System Prompt
    system_prompt = "你是一个得力的群聊助手。请根据用户的要求处理提供的消息内容。你的回复需要简练而完整的描述发生的事情，整理出发展的顺序。"
    if no_sensitive:
        system_prompt += "请注意严格过滤掉任何可能引发争议的政治、暴力等敏感词汇。"

    # 2. 组装 User Content
    if not additional_prompt.strip():
        additional_prompt = "请帮我总结/处理以下代码块中的消息内容："
        
    user_content = f"{additional_prompt}\n\n```\n{target_text}\n```"

    # 3. 构造 OpenAI 兼容格式的 Payload
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    }

    # 4. 发起异步请求
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_endpoint, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(60), proxy=provider_config['proxy']['url'] if provider_config['proxy']['enabled'] else None) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    if not reply_content:
                        raise ValueError("AI 返回了 HTTP 200，但解析出的文本内容为空。")
                    return reply_content
                else:
                    error_info = await resp.text()
                    logger.error(f"AI API HTTP Error {resp.status}: {error_info}")
                    raise ConnectionError(f"API 请求失败 (状态码: {resp.status})")
                    
    except TimeoutError:
        raise TimeoutError("API 请求超时，大模型节点可能负载过高。")
    except Exception as e:
        logger.error(f"failed to request ai: {e}")
        raise e # 继续向上抛出，交由 bot 模块回复给用户