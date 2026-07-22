import logging
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def send_post_notification(post):
    """Email all active users about a new blog post. Returns (success, recipient_count)."""
    api_key = settings.RESEND_API_KEY
    if not api_key:
        logger.warning('RESEND_API_KEY not configured — blog notification not sent')
        return False, 0

    frontend_url = settings.FRONTEND_URL.rstrip('/')
    post_url = f'{frontend_url}/blog/{post.slug}'

    recipients = list(User.objects.filter(is_active=True).values_list('email', flat=True))
    if not recipients:
        return False, 0

    html = _build_html(post, post_url)
    text = _build_text(post, post_url)

    try:
        import resend
        resend.api_key = api_key
        # Send one email per recipient to keep addresses private
        for email in recipients:
            resend.Emails.send({
                'from': f'Amanat | امانت <{settings.RESEND_FROM_EMAIL}>',
                'to': [email],
                'subject': f'New on Amanat: {post.title}',
                'html': html,
                'text': text,
            })
        return True, len(recipients)
    except Exception as exc:
        logger.error('Blog notification email failed: %s', exc)
        return False, 0


def _build_html(post, post_url):
    image_block = ''
    if post.featured_image_url:
        image_block = (
            f'<img src="{post.featured_image_url}" alt="" '
            'style="width:100%;max-width:560px;border-radius:10px;'
            'display:block;margin:0 auto 28px;">'
        )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#030712;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:48px 24px;">

    <div style="margin-bottom:36px;">
      <span style="color:#34d399;font-weight:700;font-size:22px;letter-spacing:-0.5px;">امانت</span>
      <span style="color:#6b7280;font-size:13px;margin-left:8px;vertical-align:middle;">Amanat</span>
    </div>

    <div style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:2px;margin-bottom:14px;">
      New Article
    </div>

    <h1 style="color:#f9fafb;font-size:26px;font-weight:700;margin:0 0 18px;line-height:1.35;letter-spacing:-0.3px;">
      {post.title}
    </h1>

    {image_block}

    <p style="color:#9ca3af;font-size:16px;line-height:1.75;margin:0 0 36px;">
      {post.excerpt}
    </p>

    <a href="{post_url}"
       style="display:inline-block;background:#059669;color:#ffffff;font-weight:600;
              font-size:15px;padding:14px 30px;border-radius:10px;text-decoration:none;
              letter-spacing:-0.1px;">
      Read the full article &rarr;
    </a>

    <div style="border-top:1px solid #1f2937;margin:48px 0 0;padding-top:24px;">
      <p style="color:#374151;font-size:12px;line-height:1.7;margin:0;">
        You&rsquo;re receiving this because you have an account on
        <a href="{settings.FRONTEND_URL}" style="color:#34d399;text-decoration:none;">Amanat</a>
        &mdash; Pakistan&rsquo;s Shariah-compliant PSX portfolio tracker.<br>
        To unsubscribe, reply to this email with the word <strong style="color:#4b5563;">unsubscribe</strong>.
      </p>
    </div>

  </div>
</body>
</html>"""


def _build_text(post, post_url):
    return f"""{post.title}
{'=' * min(len(post.title), 60)}

{post.excerpt}

Read the full article: {post_url}

---
You're receiving this because you have an account on Amanat.
To unsubscribe, reply with "unsubscribe".
Amanat | امانت — Shariah-Compliant PSX Portfolio Tracker
"""
