"""Discord webhook configuration management."""
from app.extensions import db, mongo
from app.utils import validate_discord_webhook_url, test_discord_webhook
from datetime import datetime
from bson import ObjectId

class DiscordWebhookConfig:
    """Manager for Discord webhook configurations in MongoDB."""
    
    COLLECTION = "discord_webhooks"
    
    @staticmethod
    def get_collection():
        # Use mongo.db instead of db proxy
        return mongo.db[DiscordWebhookConfig.COLLECTION]
    
    @staticmethod
    def get_all():
        """Get all webhook configurations."""
        return list(DiscordWebhookConfig.get_collection().find().sort("created_at", -1))
    
    @staticmethod
    def get_by_id(webhook_id: str):
        """Get a specific webhook by ID."""
        try:
            return DiscordWebhookConfig.get_collection().find_one({"_id": ObjectId(webhook_id)})
        except Exception:  # FIXED: Changed from bare except
            return None
    
    @staticmethod
    def get_active_for_event(event_type: str):
        """Get all active webhooks for a specific event type."""
        return list(DiscordWebhookConfig.get_collection().find({
            "is_active": True,
            f"events.{event_type}": True
        }))
    
    @staticmethod
    def create(webhook_url: str, events: dict, created_by: ObjectId, name: str = None):
        """Create a new webhook configuration."""
        if not validate_discord_webhook_url(webhook_url):
            raise ValueError("Invalid Discord webhook URL")
        
        # Test the webhook
        test_result = test_discord_webhook(webhook_url)
        if not test_result["success"]:
            raise ValueError(f"Webhook test failed: {test_result['error']}")
        
        config = {
            "name": name or f"Webhook {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            "webhook_url": webhook_url,
            "events": events,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "created_by": created_by,
            "last_tested": datetime.utcnow(),
            "last_test_status": "success"
        }
        
        result = DiscordWebhookConfig.get_collection().insert_one(config)
        return DiscordWebhookConfig.get_collection().find_one({"_id": result.inserted_id})
    
    @staticmethod
    def update(webhook_id: str, updates: dict):
        """Update a webhook configuration."""
        allowed_updates = ["name", "events", "is_active", "webhook_url"]
        update_data = {k: v for k, v in updates.items() if k in allowed_updates}
        
        if "webhook_url" in update_data:
            if not validate_discord_webhook_url(update_data["webhook_url"]):
                raise ValueError("Invalid Discord webhook URL")
            test_result = test_discord_webhook(update_data["webhook_url"])
            update_data["last_tested"] = datetime.utcnow()
            update_data["last_test_status"] = "success" if test_result["success"] else "failed"
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = DiscordWebhookConfig.get_collection().update_one(
            {"_id": ObjectId(webhook_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    @staticmethod
    def delete(webhook_id: str):
        """Delete a webhook configuration."""
        result = DiscordWebhookConfig.get_collection().delete_one({"_id": ObjectId(webhook_id)})
        return result.deleted_count > 0
    
    @staticmethod
    def test(webhook_id: str):
        """Test an existing webhook configuration."""
        config = DiscordWebhookConfig.get_by_id(webhook_id)
        if not config:
            raise ValueError("Webhook not found")
        
        result = test_discord_webhook(config["webhook_url"])
        DiscordWebhookConfig.get_collection().update_one(
            {"_id": ObjectId(webhook_id)},
            {"$set": {"last_tested": datetime.utcnow(), "last_test_status": "success" if result["success"] else "failed"}}
        )
        return result