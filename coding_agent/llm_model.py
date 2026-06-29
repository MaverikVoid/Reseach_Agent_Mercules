from langchain_huggingface import ChatHuggingFace,HuggingFaceEndpoint
from dotenv import load_dotenv
import os
load_dotenv()

huggingfacehub_api_token = os.getenv('HUGGINGFACEHUB_API_TOKEN')

llm = HuggingFaceEndpoint(
    repo_id="deepseek-ai/DeepSeek-V3.2",
    task="chat-completion",
    huggingfacehub_api_token=huggingfacehub_api_token,
    max_new_tokens=1200,
    temperature=0.1
)

model = ChatHuggingFace(llm=llm,huggingfacehub_api_token = huggingfacehub_api_token)

