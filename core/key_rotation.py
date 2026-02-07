"""
JWT Key Rotation System (Stage 3 Security)

Implements dual-key strategy for JWT token rotation:
- Primary Key: Used to sign NEW tokens
- Deprecated Key: Still validates OLD tokens (until expiry)
- Expired Key: Removed from active validation

This allows seamless key rotation without invalidating existing tokens.
"""
import os
import json
import time
import hashlib
import secrets
import shutil
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path
from api.utils import logger

try:
    from jose import jwt
except ImportError:
    import jwt


class KeyRotationManager:
    """
    Manages JWT key rotation with dual-key strategy.

    The key rotation process:
    1. New tokens are signed with the primary key
    2. Old tokens validated with deprecated key until they expire
    3. Keys are automatically rotated every 30 days
    4. Manual rotation available via admin API

    Storage: config/keys/jwt_keys.json (chmod 600)
    """

    def __init__(self, config_dir: str = "config/keys"):
        """
        Initialize the key rotation manager.

        Args:
            config_dir: Directory to store key configuration
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.keys_file = self.config_dir / "jwt_keys.json"
        self.keys = self._load_keys()

        # Perform cleanup of expired keys on init
        self._cleanup_expired_keys()

    def _load_keys(self) -> Dict:
        """
        Load all key configurations from file.

        Returns:
            Dictionary containing keys configuration
        """
        if self.keys_file.exists():
            try:
                with open(self.keys_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load keys file, creating new: {e}")
                # Fall through to create new keys

        # Initialize: generate primary key for first-time setup
        logger.warning("🔑 No JWT keys found, generating new primary key")
        primary_key = self._generate_key()
        keys = {
            "primary": primary_key["id"],
            "keys": [primary_key],
            "last_rotation": datetime.utcnow().isoformat()
        }
        self._save_keys_direct(keys)
        return keys

    def _generate_key(self) -> Dict:
        """
        Generate a new cryptographic key.

        Returns:
            Dictionary with key metadata
        """
        # Generate unique key ID (first 16 chars of SHA256)
        key_id = hashlib.sha256(secrets.token_bytes(16)).hexdigest()[:16]

        # Generate 256-bit key value (URL-safe base64)
        key_value = secrets.token_urlsafe(32)

        now = datetime.utcnow()

        return {
            "id": key_id,
            "value": key_value,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=90)).isoformat(),
            "status": "active"
        }

    def get_current_key(self) -> str:
        """
        Get the current primary key value for signing new tokens.

        Returns:
            The primary key value

        Raises:
            RuntimeError: If no active primary key found
        """
        for key in self.keys["keys"]:
            if key["id"] == self.keys["primary"] and key["status"] == "active":
                return key["value"]
        raise RuntimeError("No active primary key found")

    def get_primary_key_id(self) -> str:
        """
        Get the current primary key ID.

        Returns:
            The primary key ID
        """
        return self.keys["primary"]

    def get_all_active_keys(self) -> Dict[str, str]:
        """
        Get all active keys for token validation.

        Includes both active and deprecated keys to allow
        existing tokens to remain valid during rotation.

        Returns:
            Dictionary mapping key IDs to key values
        """
        return {
            key["id"]: key["value"]
            for key in self.keys["keys"]
            if key["status"] in ["active", "deprecated"]
        }

    def rotate_key(self) -> Dict:
        """
        Execute key rotation.

        Process:
        1. Generate new key
        2. Promote to primary
        3. Deprecate old primary key
        4. Save with backup

        Returns:
            Dictionary with rotation metadata
        """
        old_primary_id = self.keys["primary"]

        # Generate new key
        new_key = self._generate_key()
        self.keys["keys"].append(new_key)

        # Update primary
        self.keys["primary"] = new_key["id"]

        # Deprecate old key
        for key in self.keys["keys"]:
            if key["id"] == old_primary_id:
                key["status"] = "deprecated"
                key["deprecated_at"] = datetime.utcnow().isoformat()

        self.keys["last_rotation"] = datetime.utcnow().isoformat()

        # Save with backup
        self._save_keys()

        result = {
            "old_key_id": old_primary_id,
            "new_key_id": new_key["id"],
            "rotated_at": self.keys["last_rotation"]
        }

        logger.info(f"🔑 Key rotation completed: {old_primary_id[:8]}... -> {new_key['id'][:8]}...")

        return result

    def verify_token_with_any_key(self, token: str, algorithms: List[str] = None) -> Optional[Dict]:
        """
        Verify token using any active key.

        Tries all active and deprecated keys until one successfully
        decodes the token. This allows tokens signed with old keys
        to remain valid.

        Args:
            token: JWT token string
            algorithms: List of allowed algorithms (default: ["HS256"])

        Returns:
            Decoded token payload with _key_id added, or None if invalid
        """
        if algorithms is None:
            algorithms = ["HS256"]

        all_keys = self.get_all_active_keys()

        for key_id, key_value in all_keys.items():
            try:
                payload = jwt.decode(
                    token,
                    key_value,
                    algorithms=algorithms,
                    options={"verify_exp": True}
                )
                # Add key_id to payload for tracking
                payload["_key_id"] = key_id
                return payload
            except Exception:
                # Try next key
                continue

        return None

    def _save_keys(self):
        """
        Save keys with automatic backup.

        Creates a timestamped backup before overwriting.
        Sets file permissions to 600 (owner read/write only).
        """
        if self.keys_file.exists():
            backup_file = self.config_dir / f"jwt_keys.backup.{int(time.time())}"
            try:
                shutil.copy(self.keys_file, backup_file)
                logger.debug(f"Created key backup: {backup_file.name}")
            except IOError as e:
                logger.error(f"Failed to create key backup: {e}")

        self._save_keys_direct(self.keys)

    def _save_keys_direct(self, keys_data: Dict):
        """
        Direct save of keys data (used during initialization).

        Args:
            keys_data: Keys dictionary to save
        """
        with open(self.keys_file, "w") as f:
            json.dump(keys_data, f, indent=2)

        # Set file permissions to owner read/write only
        self.keys_file.chmod(0o600)

    def _cleanup_expired_keys(self):
        """
        Remove expired keys from the configuration.

        Keys older than 90 days and in 'expired' status are removed
        to prevent unlimited file growth.
        """
        now = datetime.utcnow()
        keys_to_keep = []
        removed_count = 0

        for key in self.keys["keys"]:
            try:
                expires_at = datetime.fromisoformat(key["expires_at"])
                # Keep if not expired, or if still active/deprecated
                if expires_at > now or key["status"] in ["active", "deprecated"]:
                    keys_to_keep.append(key)
                else:
                    removed_count += 1
            except (KeyError, ValueError):
                # Keep keys with invalid dates
                keys_to_keep.append(key)

        if removed_count > 0:
            self.keys["keys"] = keys_to_keep
            self._save_keys_direct(self.keys)
            logger.info(f"🧹 Cleaned up {removed_count} expired JWT keys")

    def get_keys_status(self) -> Dict:
        """
        Get status of all keys (for admin monitoring).

        Returns:
            Dictionary with key status information (values masked)
        """
        keys_info = []
        for key in self.keys["keys"]:
            key_copy = key.copy()
            # Mask the actual key value for security
            if "value" in key_copy:
                key_copy["value"] = f"{key_copy['value'][:8]}...{key_copy['value'][-4:]}"
            keys_info.append(key_copy)

        return {
            "primary_key_id": self.keys["primary"],
            "last_rotation": self.keys["last_rotation"],
            "total_keys": len(self.keys["keys"]),
            "active_keys": len([k for k in self.keys["keys"] if k["status"] == "active"]),
            "deprecated_keys": len([k for k in self.keys["keys"] if k["status"] == "deprecated"]),
            "keys": keys_info
        }

    def should_rotate(self, rotation_interval_days: int = 30) -> bool:
        """
        Check if key rotation is due.

        Args:
            rotation_interval_days: Days between rotations (default: 30)

        Returns:
            True if rotation is due
        """
        try:
            last_rotation = datetime.fromisoformat(self.keys["last_rotation"])
            next_rotation = last_rotation + timedelta(days=rotation_interval_days)
            return datetime.utcnow() >= next_rotation
        except (KeyError, ValueError):
            # If we can't parse the date, rotation is due
            return True


# Global singleton instance
_global_manager: Optional[KeyRotationManager] = None


def get_key_manager() -> KeyRotationManager:
    """
    Get the global key rotation manager instance.

    Returns:
        KeyRotationManager singleton
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = KeyRotationManager()
    return _global_manager


# ============================================================================
# Auto-Rotation Task
# ============================================================================

async def key_rotation_task():
    """
    Scheduled task to automatically rotate JWT keys.

    Runs key rotation if it's due (every 30 days by default).
    Checks every hour and performs rotation when needed.

    This should be started in api_server.py's lifespan function:
        asyncio.create_task(key_rotation_task())
    """
    import asyncio

    manager = get_key_manager()
    rotation_interval_days = int(os.getenv("KEY_ROTATION_INTERVAL_DAYS", "30"))

    logger.info(
        f"🔑 Key rotation task started (interval: {rotation_interval_days} days, "
        f"next check: {manager.keys['last_rotation']})"
    )

    while True:
        try:
            if manager.should_rotate(rotation_interval_days):
                logger.info("🔑 Key rotation is due, performing rotation...")
                result = manager.rotate_key()
                logger.info(
                    f"✅ Key rotation completed: "
                    f"{result['old_key_id'][:8]}... -> {result['new_key_id'][:8]}..."
                )

                # Log audit event
                try:
                    from core.audit import audit_log
                    audit_log(
                        action="key_rotation_automatic",
                        metadata=result
                    )
                except ImportError:
                    pass

        except Exception as e:
            logger.error(f"❌ Key rotation failed: {e}")

        # Check again in 1 hour
        await asyncio.sleep(3600)
