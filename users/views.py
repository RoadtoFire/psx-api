import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


class CaseInsensitiveTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        attrs[self.username_field] = attrs[self.username_field].lower()
        return super().validate(attrs)


class EmailLoginView(TokenObtainPairView):
    serializer_class = CaseInsensitiveTokenSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class GoogleAuthView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        credential = request.data.get('credential')
        if not credential:
            return Response({'error': 'credential is required'}, status=status.HTTP_400_BAD_REQUEST)

        client_id = settings.GOOGLE_CLIENT_ID
        if not client_id:
            return Response({'error': 'Google OAuth is not configured on this server'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests
            payload = google_id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                client_id,
                clock_skew_in_seconds=10,
            )
        except Exception as e:
            logger.warning("Google token verification failed: %s", e)
            return Response({'error': 'Invalid Google credential'}, status=status.HTTP_400_BAD_REQUEST)

        email = payload.get('email', '').lower()
        if not email:
            return Response({'error': 'No email in Google token'}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(
            email=email,
            defaults=self._build_defaults(payload, email),
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })

    def _build_defaults(self, payload, email):
        base_username = email.split('@')[0][:140]
        username = base_username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{suffix}"
            suffix += 1
        return {'username': username}


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        # Always return 200 regardless — never confirm whether an email exists.
        detail = {'detail': 'If that email is registered, a reset link has been sent.'}

        if not email:
            return Response(detail)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(detail)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        self._send_reset_email(user.email, reset_url)
        return Response(detail)

    def _send_reset_email(self, to_email, reset_url):
        api_key = settings.RESEND_API_KEY
        from_email = settings.RESEND_FROM_EMAIL

        if not api_key:
            logger.warning("RESEND_API_KEY not configured — password reset email not sent to %s", to_email)
            return

        html_body = f"""
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px;">
          <h2 style="color: #059669; margin-bottom: 8px;">Reset your Amanat password</h2>
          <p style="color: #374151; margin-bottom: 24px;">
            We received a request to reset the password for your Amanat account.
            Click the button below to choose a new one. This link expires in 1 hour.
          </p>
          <a href="{reset_url}"
             style="display:inline-block; background:#059669; color:#fff; text-decoration:none;
                    padding:12px 28px; border-radius:8px; font-weight:600; font-size:15px;">
            Reset Password
          </a>
          <p style="color: #9ca3af; font-size: 13px; margin-top: 24px;">
            If you didn't request this, you can safely ignore this email.
          </p>
          <hr style="border:none; border-top:1px solid #e5e7eb; margin:24px 0;">
          <p style="color: #d1d5db; font-size: 12px;">
            Amanat | امانت &mdash; Shariah-Compliant PSX Portfolio Tracker
          </p>
        </div>
        """

        try:
            import resend
            resend.api_key = api_key
            resend.Emails.send({
                'from': f'Amanat <{from_email}>',
                'to': [to_email],
                'subject': 'Reset your Amanat password',
                'html': html_body,
            })
        except Exception as e:
            logger.error("Failed to send password reset email to %s: %s", to_email, e)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get('uid', '')
        token = request.data.get('token', '')
        new_password = request.data.get('new_password', '')

        if not all([uid, token, new_password]):
            return Response({'error': 'uid, token, and new_password are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_pk)
        except (TypeError, ValueError, User.DoesNotExist):
            return Response({'error': 'Invalid reset link'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'error': 'This reset link has expired or already been used. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response({'error': e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password updated successfully.'})
