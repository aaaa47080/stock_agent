"""
私訊功能配置讀取
"""
from ..connection import get_connection


def _get_message_config(key: str, default: any = None):
    """從 system_config 表讀取配置值"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT value, value_type FROM system_config WHERE key = %s', (key,))
        row = c.fetchone()
        if not row:
            return default

        value, value_type = row
        if value == 'null' or value is None:
            return None

        if value_type == 'int':
            return int(value)
        elif value_type == 'float':
            return float(value)
        elif value_type == 'bool':
            return value.lower() in ('true', '1', 'yes')
        return value
    except Exception:
        return default
    finally:
        conn.close()
