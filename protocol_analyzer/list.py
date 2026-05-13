from openai import OpenAI

# for backward compatibility, you can still use `https://api.deepseek.com/v1` as `base_url`.
client = OpenAI(api_key="sk-652e4764da9d463788ece1d325e5019d", base_url="https://api.deepseek.com")
print(client.models.list())