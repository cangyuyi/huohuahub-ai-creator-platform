# -*- coding: utf-8 -*-
"""WeChat iLink Bot login script - fetches QR code and waits for scan"""
import asyncio
import sys
import os
import httpx
import qrcode
from PIL import Image

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

FIXED_BASE_URL = "https://ilinkai.weixin.qq.com/"
BOT_TYPE = "3"
QR_DIR = os.path.dirname(os.path.abspath(__file__))

async def main():
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        # Fetch QR code
        resp = await http.get(f"{FIXED_BASE_URL}ilink/bot/get_bot_qrcode?bot_type={BOT_TYPE}")
        data = resp.json()
        qrcode_key = data.get("qrcode", "")
        qrcode_url = data.get("qrcode_img_content", "")
        
        if not qrcode_key:
            print("Failed to get QR code")
            return
        
        print(f"QR URL: {qrcode_url}")
        
        # Generate and save QR code image
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(qrcode_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        qr_path = os.path.join(QR_DIR, "wechat_login_qr.png")
        img.save(qr_path)
        print(f"QR code saved to: {qr_path}")
        print("Please scan the QR code with WeChat to log in...")
        
        # Poll for scan status
        while True:
            try:
                resp = await http.get(
                    f"{FIXED_BASE_URL}ilink/bot/get_qrcode_status?qrcode={qrcode_key}",
                    timeout=35
                )
                status_data = resp.json()
            except Exception:
                await asyncio.sleep(1)
                continue
            
            status = status_data.get("status", "wait")
            
            if status == "scaned":
                print("Scanned! Please confirm in WeChat...")
            elif status == "confirmed":
                bot_token = status_data.get("bot_token", "")
                account_id = status_data.get("ilink_bot_id", "")
                base_url = status_data.get("baseurl", FIXED_BASE_URL)
                user_id = status_data.get("ilink_user_id", "")
                
                # Save token
                token_path = os.path.join(QR_DIR, "wechat_bot_token.txt")
                with open(token_path, "w", encoding="utf-8") as f:
                    f.write(f"token={bot_token}\n")
                    f.write(f"account_id={account_id}\n")
                    f.write(f"base_url={base_url}\n")
                    f.write(f"user_id={user_id}\n")
                
                print(f"\nLogin successful!")
                print(f"Account ID: {account_id}")
                print(f"Token saved to: {token_path}")
                return
            elif status == "expired":
                print("QR code expired, please run again.")
                return
            
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
