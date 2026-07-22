import logging
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny

from .models import BlogPost
from .serializers import BlogPostListSerializer, BlogPostDetailSerializer
from .email import send_post_notification

logger = logging.getLogger(__name__)


# ── Public ────────────────────────────────────────────────────────────────────

class BlogPostListView(generics.ListAPIView):
    serializer_class = BlogPostListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return BlogPost.objects.filter(status='published').order_by('-published_at')


class BlogPostDetailView(generics.RetrieveAPIView):
    serializer_class = BlogPostDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return BlogPost.objects.filter(status='published')


# ── Staff / Admin ─────────────────────────────────────────────────────────────

class AdminBlogListView(generics.ListCreateAPIView):
    serializer_class = BlogPostDetailSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return BlogPost.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class AdminBlogDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BlogPostDetailSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'slug'
    queryset = BlogPost.objects.all()


class PublishPostView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, slug):
        try:
            post = BlogPost.objects.get(slug=slug)
        except BlogPost.DoesNotExist:
            return Response({'error': 'Post not found'}, status=404)

        post.status = 'published'
        if not post.published_at:
            post.published_at = timezone.now()
        post.save()

        send_email = request.data.get('send_email', True)
        if send_email and not post.email_sent:
            sent, count = send_post_notification(post)
            if sent:
                post.email_sent = True
                post.save(update_fields=['email_sent'])
            return Response({
                'status': 'published',
                'email_sent': sent,
                'recipients': count,
            })

        return Response({'status': 'published', 'email_sent': False, 'recipients': 0})
