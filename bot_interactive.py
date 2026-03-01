import os
import sys
import logging
from typing import Dict, Any, List, Optional

from curl_cffi import requests as cffi_requests
from curl_cffi.requests import AsyncSession
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configurations
DOMAIN = "https://shopclone47.com"
TARGET_IDS = {487, 506}
MAX_RUN_TIME = 2 * 3600 + 50 * 60  # 2 hours 50 minutes in seconds

# Environment Variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SHOP_USER = os.environ.get("SHOP_USER")
SHOP_PASS = os.environ.get("SHOP_PASS")


async def fetch_target_products() -> Optional[List[Dict[str, Any]]]:
    """
    Fetch data from ShopClone API, bypass Cloudflare with curl_cffi,
    and extract only target items.
    """
    if not SHOP_USER or not SHOP_PASS:
        logger.error("Thiếu SHOP_USER hoặc SHOP_PASS trong biến môi trường.")
        return None

    api_url = f"{DOMAIN}/api/ListResource.php?username={SHOP_USER}&password={SHOP_PASS}"

    try:
        async with AsyncSession(impersonate="chrome120", timeout=15.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                logger.error(f"API trả về không thành công: {data}")
                return None

            categories = data.get("categories", [])
            target_items: List[Dict[str, Any]] = []

            # Duyệt qua từng danh mục và tài khoản để bóc tách ID mục tiêu
            for cat in categories:
                accounts = cat.get("accounts", [])
                for acc in accounts:
                    item_id = int(acc.get("id", 0))
                    if item_id in TARGET_IDS:
                        target_items.append({
                            "id": item_id,
                            "name": acc.get("name", "Unknown"),
                            "price": acc.get("price", 0),
                            "amount": int(acc.get("amount", 0))
                        })
            
            return target_items

    except cffi_requests.errors.RequestsError as e:
        logger.error(f"Lỗi mạng/kết nối (curl_cffi): {repr(e)}")
        return None
    except ValueError as e:
        logger.error(f"Lỗi phân tích cú pháp JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Lỗi không xác định khi gọi API: {e}", exc_info=True)
        return None


async def send_telegram_alert(context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    """Helper function to safely send messages with error handling."""
    if not TELEGRAM_CHAT_ID:
        return
    try:
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
        logger.info("Đã gửi thông báo Telegram thành công.")
    except Exception as e:
        logger.error(f"Lỗi gửi tin nhắn Telegram: {e}")


async def check_api_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Background job to check API periodically and apply Anti-Spam state."""
    logger.info("Đang thực thi chu kỳ kiểm tra API...")
    products = await fetch_target_products()

    if products is None:
        logger.warning("Không lấy được dữ liệu sản phẩm. Bỏ qua chu kỳ này.")
        return

    # Khởi tạo bộ nhớ tạm để lưu trạng thái
    if "item_states" not in context.bot_data:
        context.bot_data["item_states"] = {}
        
    item_states: Dict[int, int] = context.bot_data["item_states"]

    in_stock_alerts: List[str] = []
    out_of_stock_alerts: List[str] = []

    for item in products:
        item_id = item["id"]
        current_qty = item["amount"]
        name = item["name"]
        price = item["price"]

        prev_qty = item_states.get(item_id, 0)
        logger.info(f"-> ID {item_id}: Hiện tại = {current_qty} | Lần trước = {prev_qty}")

        # Logic State Transition (Anti-Spam)
        if current_qty > 0 and prev_qty == 0:
            in_stock_alerts.append(
                f"✅ *{name}*\n- ID: `{item_id}`\n- Giá: {price} VND\n- Số lượng: *{current_qty}*"
            )
        elif current_qty == 0 and prev_qty > 0:
            out_of_stock_alerts.append(
                f"❌ *{name}*\n- ID: `{item_id}`\n- Trạng thái: *Đã hết hàng*"
            )

        item_states[item_id] = current_qty

    # Gửi tin nhắn gom nhóm
    if in_stock_alerts:
        msg = "🔥 *HÀNG ĐÃ VỀ (SHOPCLONE47)!* 🔥\n\n" + "\n\n".join(in_stock_alerts)
        await send_telegram_alert(context, msg)

    if out_of_stock_alerts:
        msg = "⚠️ *THÔNG BÁO HẾT HÀNG (SHOPCLONE47)* ⚠️\n\n" + "\n\n".join(out_of_stock_alerts)
        await send_telegram_alert(context, msg)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.message.reply_text(
            "👋 Bot ShopClone47 đang chạy (Anti-Spam Mode).\n"
            "Chỉ thông báo khi hàng TỪ KHÔNG -> CÓ và TỪ CÓ -> KHÔNG."
        )
    except Exception as e:
        logger.error(f"Lỗi trong start_command: {e}")


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.message.reply_text("⏳ Đang gọi API lấy số liệu trực tiếp...")
        products = await fetch_target_products()
        
        if not products:
            await update.message.reply_text("❌ Lỗi kết nối API. Vui lòng xem log server.")
            return

        status_msgs = [f"- {item['name']}: *{item['amount']} cái*" for item in products]
        reply_text = "📊 *Trạng thái hiện tại:*\n" + "\n".join(status_msgs)
        await update.message.reply_text(reply_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Lỗi trong check_command: {e}")


async def shutdown_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Đã đạt giới hạn thời gian chạy. Tiến hành Graceful Shutdown...")
    if context.application:
        context.application.stop_running()


def main() -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.critical("Thiếu TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID.")
        sys.exit(1)
        
    if not SHOP_USER or not SHOP_PASS:
        logger.critical("Thiếu SHOP_USER hoặc SHOP_PASS. Hãy kiểm tra biến môi trường.")
        sys.exit(1)

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("check", check_command))

    job_queue = application.job_queue
    if not job_queue:
        logger.critical("Không tìm thấy JobQueue. Cần chạy: pip install 'python-telegram-bot[job-queue]'")
        sys.exit(1)

    job_queue.run_repeating(check_api_job, interval=60, first=10)
    job_queue.run_once(shutdown_job, when=MAX_RUN_TIME)

    logger.info("Khởi động Bot ShopClone47 (Anti-Spam Mode) với curl_cffi...")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot được tắt thủ công.")
    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng trong quá trình polling: {e}")
    finally:
        logger.info("Tiến trình đã kết thúc an toàn.")

if __name__ == "__main__":
    main()