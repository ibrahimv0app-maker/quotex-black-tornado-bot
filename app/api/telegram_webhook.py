from fastapi import APIRouter, Request
import logging
import json

router = APIRouter()
logger = logging.getLogger("quotex_m1_bot.telegram_webhook")


@router.post("/telegram/webhook")
async def telegram_webhook(update: Request):
    """Receive Telegram webhook updates and log them so we can extract custom_emoji_id.

    Usage: set your Telegram bot webhook to https://<your-railway-domain>/telegram/webhook
    Then send a custom emoji in the channel; this handler will print the full update JSON
    to the application logs where Railway can show it.
    """
    try:
        data = await update.json()
    except Exception:
        body = await update.body()
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {"raw": str(body)}

    # Log full update at INFO level (visible in Railway logs); DEBUG if configured differently
    logger.info("Incoming Telegram update: %s", json.dumps(data, ensure_ascii=False))

    # For convenience, also extract and log any custom_emoji_id values found in entities
    try:
        # message or channel_post
        msg = data.get("message") or data.get("channel_post") or {}
        entities = msg.get("entities") or msg.get("caption_entities") or []
        emoji_ids = [e.get("custom_emoji_id") for e in entities if e.get("type") == "custom_emoji"]
        if emoji_ids:
            logger.info("Found custom_emoji_id(s): %s", ", ".join(str(x) for x in emoji_ids))
    except Exception:
        logger.exception("Error extracting custom emoji IDs from update")

    return {"ok": True}
