# blog/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import Post, Comment, Notification, Genre, SiteSettings, Profile


# =======================
# User + Profile Admin
# =======================
class ProfileInline(admin.StackedInline):
    """Attach Profile model inline to User in admin"""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    actions = ['ban_for_7_days']

    def ban_for_7_days(self, request, queryset):
        """Custom action: ban users from commenting for 7 days"""
        ban_until = timezone.now() + timedelta(days=7)
        updated = 0
        for user in queryset:
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.comment_ban_until = ban_until
            profile.save()
            updated += 1
        self.message_user(request, f"🚫 Successfully banned {updated} user(s) from commenting for 7 days.")
    ban_for_7_days.short_description = "Ban selected users from commenting for 7 days"


# Unregister default User and re-register with ProfileInline + actions
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# =======================
# Genre Admin
# =======================
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# =======================
# Post Admin
# =======================
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'genre', 'comment_count', 'photo_thumbnail', 'created_at')
    search_fields = ('title', 'content', 'author__username')
    list_filter = ('created_at', 'author', 'genre')
    ordering = ('-created_at',)

    def comment_count(self, obj):
        """Counts only approved comments for the post"""
        return obj.comments.filter(status='approved').count()
    comment_count.short_description = 'Comments'

    def photo_thumbnail(self, obj):
        """Renders a small image preview of the post photo"""
        if obj.photo:
            return format_html(
                '<img src="{}" style="width: 75px; height: auto; border-radius: 4px;" />',
                obj.photo.url
            )
        return "No Image"
    photo_thumbnail.short_description = 'Photo Preview'


# =======================
# Comment Admin
# =======================
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        'truncated_text', 'author', 'post_link',
        'display_status', 'toxicity_label', 'created_at'
    )
    list_filter = ('status', 'created_at', 'post')
    search_fields = ('text', 'author__username', 'post__title')
    ordering = ('-created_at',)

    actions = [
        'approve_comments',
        'mark_as_pending',
        'mark_as_reported',
        'reject_comments',
        'delete_comments',
    ]

    def truncated_text(self, obj):
        """Shows the first 50 characters of a comment"""
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    truncated_text.short_description = 'Comment Snippet'

    def post_link(self, obj):
        """Clickable link to edit the related Post in admin"""
        url = reverse("admin:blog_post_change", args=[obj.post.id])
        return format_html('<a href="{}">{}</a>', url, obj.post.title)
    post_link.short_description = 'Post'

    def display_status(self, obj):
        """Colored status display"""
        color_map = {
            'approved': 'green',
            'pending_review': 'orange',
            'reported': 'red',
            'rejected': 'gray',
        }
        color = color_map.get(obj.status, 'black')
        return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())
    display_status.short_description = 'Status'
    display_status.admin_order_field = 'status'

    # --- Actions ---
    def approve_comments(self, request, queryset):
        updated = queryset.update(status='approved')
        self.message_user(request, f"✅ Approved {updated} comment(s).")
    approve_comments.short_description = "Approve selected comments"

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending_review')
        self.message_user(request, f"⏳ Marked {updated} comment(s) as pending.")
    mark_as_pending.short_description = "Mark as Pending Review"

    def mark_as_reported(self, request, queryset):
        updated = queryset.update(status='reported')
        self.message_user(request, f"🚩 Reported {updated} comment(s).")
    mark_as_reported.short_description = "Mark as Reported"

    def reject_comments(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f"❌ Rejected {updated} comment(s).")
    reject_comments.short_description = "Reject selected comments"

    def delete_comments(self, request, queryset):
        deleted = queryset.count()
        queryset.delete()
        self.message_user(request, f"🗑️ Deleted {deleted} comment(s).")
    delete_comments.short_description = "Delete selected comments"


# =======================
# Notification Admin
# =======================
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'created_at', 'read')
    list_filter = ('read', 'created_at')


# =======================
# Site Settings Admin
# =======================
@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    pass
