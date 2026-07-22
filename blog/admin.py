from django.contrib import admin
from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'author', 'published_at', 'email_sent', 'created_at']
    list_filter = ['status', 'email_sent']
    search_fields = ['title', 'excerpt', 'content']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['email_sent', 'created_at', 'updated_at']
