# StyleLeveling deployment

The included `render.yaml` creates the Django web service and PostgreSQL database.

After Render creates the service:

1. Add the final frontend domain to `CORS_ALLOWED_ORIGINS`.
2. Add the final API domain to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
3. Run `python styleleveling/manage.py createsuperuser` in the Render shell.
4. In Django Admin, enable **Guest visible** only for stores visitors may browse.

## Membership API

- `POST /api/members/signup/` with `email` and `password`
- `POST /api/members/login/` with `username` (the member email) and `password`
- Send `Authorization: Token <token>` for member requests

## Deal API

- `GET /api/listings/` — guests receive at most 100 matching listings from guest-visible stores; members receive the complete matching feed
- `GET /api/listings/<id>/` — listing detail with `image_urls` and `outbound_url`
- `GET/POST /api/saved-deals/` — list or save a member's deals
- `DELETE /api/saved-deals/<id>/` — remove a saved deal

The `outbound_url` automatically uses `affiliate_url` when present and otherwise uses the original retailer `product_page_url`.
