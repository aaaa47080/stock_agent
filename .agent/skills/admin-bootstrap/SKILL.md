---
name: admin-bootstrap
description: Automates the process of setting up the first admin user or adding new admins via the bootstrap endpoint. Includes a Python script for easy execution.
---

# Admin Bootstrap Skill

This skill provides a standardized way to promote a user to the Admin role using the `bootstrap-admin` endpoint.

## Usage

### Option 1: Using the Python Script (Recommended)

Run the included convenience script to interactively bootstrap an admin.

```bash
python .agent/skills/admin-bootstrap/bootstrap_admin.py
```

The script will:
1.  Prompt for the `user_id` you want to promote.
2.  (Optional) Prompt for an API token (if required/implemented in script, though the endpoint relies on `current_user` from the request, so the script might need to simulate a token or the user needs to use curl if they effectively need to *be* that user).

### Option 2: Browser Console (Easiest for First Admin)

1.  Open the App in your browser (Pi Browser or Chrome with valid SDK session).
2.  Open DevTools (F12) -> Console.
3.  Run:
    ```javascript
    // Replace with your actual User ID if needed, or just let backend handle current user
    const userId = AuthManager.currentUser.user_id; 
    await fetch(\`/api/admin/bootstrap-admin?user_id=\${userId}\`, {
        method: 'POST',
        headers: {
            'Authorization': \`Bearer \${AuthManager.accessToken}\`
        }
    }).then(r => r.json()).then(console.log);
    ```

### Option 3: CURL (If you have the token)

```bash
curl -X POST "http://localhost:8080/api/admin/bootstrap-admin?user_id=TARGET_USER_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Security & Configuration

### Environment Variables

| Variable | Development | Production | Notes |
| :--- | :--- | :--- | :--- |
| `ALLOW_ADMIN_BOOTSTRAP` | `true` | `true` -> `false` | **CRITICAL:** Set to `false` after first admin is created. |
| `TEST_MODE` | `true` | `false` | Must be `false` in production. |
| `ENVIRONMENT` | `development` | `production` | Enables production guards. |

### Rules

-   **Self-Promotion**: If no admins exist, you can only promote **yourself**. This prevents unauthorized users from promoting arbitrary accounts.
-   **Admin-Promotion**: If admins exist, only an **existing admin** can promote others.

## Production Security Checklist

After setting up the first admin:

1.  **Disable Bootstrap**: Set `ALLOW_ADMIN_BOOTSTRAP=false` in `.env` and restart the server.
2.  **Verify Access**: Ensure you can access the Admin Panel using the new admin account.
3.  **Audit Logs**: Check `config_audit_log` in the database to verify the bootstrap event was recorded.

## Troubleshooting

### "403 Forbidden"
-   **Cause**: `ALLOW_ADMIN_BOOTSTRAP` is `false`.
-   **Fix**: Set it to `true` in `.env` and restart.
-   **Cause**: Admins already exist, but you are not one.
-   **Fix**: Have an existing admin promote you.
-   **Cause**: No admins exist, but you tried to promote a different `user_id`.
-   **Fix**: Promote yourself first.

### "Admin tab not showing"
-   **Cause**: Frontend hasn't refreshed the user role.
-   **Fix**: Refresh the page. Verify `AuthManager.currentUser.role` is `'admin'` in the console.

