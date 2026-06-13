import os
from dotenv import load_dotenv
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Try to find .env in current or parent dir
if os.path.exists("../.env"):
    load_dotenv("../.env")
else:
    load_dotenv()

REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv("LLM_MODEL_ID", "us.deepseek.r1-v1:0")
BEARER_TOKEN = os.getenv("AWS_BEARER_TOKEN_BEDROCK")

print("Region:", REGION)
print("Model ID:", MODEL_ID)
print("Bearer Token (first 10 chars):", BEARER_TOKEN[:10] if BEARER_TOKEN else None)
print("AWS_BEARER_TOKEN_BEDROCK in os.environ:", "AWS_BEARER_TOKEN_BEDROCK" in os.environ)

# Ensure it's in os.environ
if BEARER_TOKEN:
    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = BEARER_TOKEN

try:
    client = boto3.client(
        "bedrock-runtime",
        region_name=REGION,
        config=Config(retries={"max_attempts": 5, "mode": "adaptive"}),
    )
    print("Client created successfully.")
    
    response = client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": "Reply with exactly: setup ok"}]}],
        inferenceConfig={"maxTokens": 1024, "temperature": 0.7},
    )
    print("RESPONSE:", response["output"]["message"]["content"][0]["text"])
except Exception as e:
    print("ERROR:", e)
