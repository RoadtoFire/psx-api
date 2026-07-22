from django.urls import path
from .views import (
    BlogPostListView,
    BlogPostDetailView,
    AdminBlogListView,
    AdminBlogDetailView,
    PublishPostView,
)

urlpatterns = [
    # Public
    path('blog/', BlogPostListView.as_view(), name='blog-list'),
    path('blog/<slug:slug>/', BlogPostDetailView.as_view(), name='blog-detail'),
    # Staff
    path('admin/blog/', AdminBlogListView.as_view(), name='admin-blog-list'),
    path('admin/blog/<slug:slug>/', AdminBlogDetailView.as_view(), name='admin-blog-detail'),
    path('admin/blog/<slug:slug>/publish/', PublishPostView.as_view(), name='admin-blog-publish'),
]
