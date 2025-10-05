"""
SFTP Connection Test Script
Tests connection to BisectHosting SFTP server and locates log files.
"""

import os
import sys
from dotenv import load_dotenv
import paramiko

# Load environment variables
load_dotenv()

SFTP_HOST = os.getenv("SFTP_HOST", "")
SFTP_PORT = os.getenv("SFTP_PORT", "22")
SFTP_USERNAME = os.getenv("SFTP_USERNAME", "")
# Workaround for # character in password
SFTP_PASSWORD_RAW = os.getenv("SFTP_PASSWORD", "")
if SFTP_PASSWORD_RAW and '#' not in SFTP_PASSWORD_RAW and os.path.exists('.sftp_password'):
    with open('.sftp_password', 'r') as f:
        SFTP_PASSWORD = f.read().strip()
else:
    SFTP_PASSWORD = SFTP_PASSWORD_RAW
SFTP_LOG_PATH = os.getenv("SFTP_LOG_PATH", "")

def test_sftp_connection():
    """Test SFTP connection and explore directory structure."""
    
    print("=" * 70)
    print("SFTP Connection Test")
    print("=" * 70)
    
    if not SFTP_HOST or not SFTP_USERNAME or not SFTP_PASSWORD:
        print("\n[ERROR] SFTP credentials not configured in .env")
        print("Required: SFTP_HOST, SFTP_USERNAME, SFTP_PASSWORD")
        return False
    
    print(f"\n[INFO] Connecting to {SFTP_HOST}:{SFTP_PORT}")
    print(f"[INFO] Username: {SFTP_USERNAME}")
    
    try:
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect
        ssh.connect(
            hostname=SFTP_HOST,
            port=int(SFTP_PORT),
            username=SFTP_USERNAME,
            password=SFTP_PASSWORD,
            timeout=15
        )
        
        print("[OK] SSH connection successful!")
        
        # Open SFTP
        sftp = ssh.open_sftp()
        print("[OK] SFTP session opened!")
        
        # Get current directory
        current_dir = sftp.getcwd() or "/"
        print(f"\n[INFO] Current directory: {current_dir}")
        
        # List root directory
        print("\n[INFO] Root directory contents:")
        try:
            items = sftp.listdir('.')
            for item in sorted(items):
                try:
                    stat = sftp.stat(item)
                    item_type = "DIR" if paramiko.sftp_attr.S_ISDIR(stat.st_mode) else "FILE"
                    print(f"  [{item_type}] {item}")
                except Exception:
                    print(f"  [?] {item}")
        except Exception as e:
            print(f"[ERROR] Could not list directory: {e}")
        
        # Check for logs directory
        print("\n[INFO] Searching for logs directory...")
        log_dirs = ['/logs', 'logs', './logs', '/home/container/logs']
        
        for log_dir in log_dirs:
            try:
                files = sftp.listdir(log_dir)
                print(f"\n[OK] Found logs directory: {log_dir}")
                print("[INFO] Contents:")
                for f in sorted(files)[:10]:  # Show first 10 files
                    try:
                        stat = sftp.stat(f"{log_dir}/{f}")
                        size_mb = stat.st_size / (1024 * 1024)
                        print(f"  {f} ({size_mb:.2f} MB)")
                    except Exception:
                        print(f"  {f}")
                break
            except Exception:
                continue
        else:
            print("[WARNING] Could not find logs directory in common locations")
        
        # Test configured log path
        if SFTP_LOG_PATH:
            print(f"\n[INFO] Testing configured log path: {SFTP_LOG_PATH}")
            try:
                stat = sftp.stat(SFTP_LOG_PATH)
                size_mb = stat.st_size / (1024 * 1024)
                print(f"[OK] Log file found! Size: {size_mb:.2f} MB")
                
                # Read last few lines
                print("\n[INFO] Reading last 5 lines of log file:")
                with sftp.open(SFTP_LOG_PATH, 'r') as f:
                    f.seek(max(0, stat.st_size - 2000))  # Read last 2KB
                    lines = f.read().decode('utf-8', errors='ignore').split('\n')
                    for line in lines[-5:]:
                        if line.strip():
                            print(f"  {line}")
                
            except FileNotFoundError:
                print(f"[ERROR] Log file not found: {SFTP_LOG_PATH}")
                print("[INFO] Try one of these paths instead:")
                print("  /logs/latest.log")
                print("  logs/latest.log")
                print("  /home/container/logs/latest.log")
            except Exception as e:
                print(f"[ERROR] Error reading log file: {e}")
        
        # Cleanup
        sftp.close()
        ssh.close()
        
        print("\n[OK] SFTP connection test successful!")
        return True
        
    except paramiko.AuthenticationException:
        print("\n[ERROR] Authentication failed - check username/password")
        return False
    except paramiko.SSHException as e:
        print(f"\n[ERROR] SSH error: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        return False


if __name__ == "__main__":
    success = test_sftp_connection()
    sys.exit(0 if success else 1)
