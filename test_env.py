"""Quick test to verify .env is being read correctly"""
import os
from dotenv import load_dotenv

load_dotenv()

print("SFTP Configuration:")
print(f"SFTP_HOST: {os.getenv('SFTP_HOST', 'NOT SET')}")
print(f"SFTP_PORT: {os.getenv('SFTP_PORT', 'NOT SET')}")
print(f"SFTP_USERNAME: {os.getenv('SFTP_USERNAME', 'NOT SET')}")
print(f"SFTP_PASSWORD: {os.getenv('SFTP_PASSWORD', 'NOT SET')}")
print(f"SFTP_LOG_PATH: {os.getenv('SFTP_LOG_PATH', 'NOT SET')}")
