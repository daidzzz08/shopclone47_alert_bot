import sys
import logging
from curl_cffi import requests as cffi_requests
from curl_cffi.requests import AsyncSession
import asyncio

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configurations
DOMAIN = "https://shopclone47.com"
USERNAME = "daidzzz08"  # <--- Thay tài khoản của bạn vào đây
PASSWORD = "11112005@Azx"  # <--- Thay mật khẩu của bạn vào đây

API_URL = f"{DOMAIN}/api/ListResource.php?username={USERNAME}&password={PASSWORD}"


async def fetch_all_products() -> None:
    """Gọi API và in toàn bộ danh mục/sản phẩm ra terminal để khảo sát ID."""
    logger.info(f"Đang kết nối đến {DOMAIN} để lấy danh sách sản phẩm...")
    
    try:
        # Sử dụng impersonate để tránh bị block bởi Anti-Bot
        async with AsyncSession(impersonate="chrome120", timeout=15.0) as client:
            response = await client.get(API_URL)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                logger.error(f"API trả về lỗi hoặc không thành công: {data}")
                return

            categories = data.get("categories", [])
            if not categories:
                logger.warning("Không tìm thấy danh mục nào trong Response.")
                return

            # Hiển thị dữ liệu dạng cây (Tree) ra Terminal
            print("\n" + "="*50)
            print("📦 DANH SÁCH SẢN PHẨM TRÊN SHOPCLONE47")
            print("="*50)

            total_items = 0
            for cat in categories:
                cat_name = cat.get("name", "Unknown Category")
                accounts = cat.get("accounts", [])
                
                print(f"\n📁 [Danh mục] {cat_name}")
                
                if not accounts:
                    print("   └── (Trống)")
                    continue
                    
                for acc in accounts:
                    item_id = acc.get("id")
                    item_name = acc.get("name")
                    price = acc.get("price")
                    amount = acc.get("amount")
                    
                    print(f"   ├── ID: {item_id:<4} | Kho: {amount:<4} | Giá: {price}đ | Tên: {item_name}")
                    total_items += 1
            
            print("\n" + "="*50)
            print(f"✅ Đã tải xong {total_items} sản phẩm thuộc {len(categories)} danh mục.")

    except cffi_requests.errors.RequestsError as e:
        logger.error(f"Lỗi mạng/kết nối (curl_cffi): {repr(e)}")
    except ValueError as e:
        logger.error(f"Lỗi JSON (Có thể sai tài khoản/mật khẩu hoặc bị chặn): {e}\nNội dung raw: {response.text[:200]}")
    except Exception as e:
        logger.error(f"Lỗi không xác định: {e}", exc_info=True)


if __name__ == "__main__":
    if USERNAME == "YOUR_USERNAME" or PASSWORD == "YOUR_PASSWORD":
        logger.error("Vui lòng thay đổi USERNAME và PASSWORD trong file code trước khi chạy.")
        sys.exit(1)
        
    # Chạy hàm async
    asyncio.run(fetch_all_products())