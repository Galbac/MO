# Security Notes

## Implemented
- Bearer auth with access and refresh tokens
- Refresh token rotation and invalidation
- Login brute-force lockout
- RBAC for admin/editor/operator/user zones
- Security headers middleware
- API rate limiting middleware
- Upload MIME, size and filename validation
- HTML sanitization for article content
- Audit logging for critical operations

## Operational checks
- Verify protected endpoints return `401` without token and `403` with insufficient role.
- Verify admin-only routes remain inaccessible to `user`, `editor`, `operator` where appropriate.
- Verify article HTML does not retain `<script>` blocks or inline `on*` handlers.

## Remaining production items
- Centralized secret rotation
- Full object storage malware scanning pipeline
- External IdP or enterprise session management if required
