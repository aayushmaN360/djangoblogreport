# File: blog/models.py
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from ckeditor.fields import RichTextField


# ------------------ Profile ------------------
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Default image can be adjusted to point to static folder if needed
    image = models.ImageField(default='profile_pics/default.jpg', upload_to='profile_pics')
    
    bio = models.TextField(max_length=500, blank=True)
    comment_ban_until = models.DateTimeField(null=True, blank=True)
    
    website_url = models.URLField(max_length=200, blank=True)
    twitter_handle = models.CharField(max_length=15, blank=True)
    github_username = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'

    @property
    def is_banned(self):
        return bool(self.comment_ban_until and timezone.now() < self.comment_ban_until)


# ------------------ Genre ------------------
class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


# ------------------ User Inquiry ------------------
class UserInquiry(models.Model):
    STATUS_CHOICES = (
        ('new', 'New'),
        ('read', 'Read'),
        ('resolved', 'Resolved'),
    )

    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Inquiry from {self.name} ({self.status})"


# ------------------ Post ------------------
class Post(models.Model):
    title = models.CharField(max_length=200)
    genre = models.ForeignKey("Genre", on_delete=models.SET_NULL, null=True, blank=True)
    content = RichTextField()
    photo = models.ImageField(upload_to='post_photos/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    view_count = models.PositiveIntegerField(default=0, help_text="Automatically updated.")
    is_featured = models.BooleanField(default=False, help_text="Only one post can be featured at a time.")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('post_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        if self.is_featured:
            Post.objects.filter(is_featured=True).exclude(pk=self.pk).update(is_featured=False)
        super().save(*args, **kwargs)


# ------------------ Comment ------------------
class Comment(models.Model):
    STATUS_CHOICES = (
        ('approved', 'Approved'),
        ('pending_review', 'Pending Review'),
        ('hidden', 'Hidden by Reports'),
        ('rejected', 'Rejected'),
    )

    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    upvotes = models.ManyToManyField(User, related_name='comment_upvotes', blank=True)
    downvotes = models.ManyToManyField(User, related_name='comment_downvotes', blank=True)
    reported_by = models.ManyToManyField(User, related_name='reported_comments', blank=True)
    toxicity_label = models.CharField(max_length=50, null=True, blank=True)
    is_edited = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.post.title}"

    def get_vote_score(self):
        return self.upvotes.count() - self.downvotes.count()

    def add_report(self, user):
        if not self.reported_by.filter(id=user.id).exists():
            self.reported_by.add(user)
        if self.reported_by.count() >= 3 and self.status == 'approved':
            self.status = 'hidden'
            self.save(update_fields=['status'])
        return "reported"


# ------------------ Notification ------------------
class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('new_comment', 'New Comment'),
        ('new_reply', 'New Reply'),
        ('toxic_comment', 'Toxic Comment'),
        ('comment_approved', 'Comment Approved'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)
    read = models.BooleanField(default=False)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='new_comment')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.get_notification_type_display()}"


# ------------------ Site Settings ------------------
class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default="Sanity Check")
    logo = models.ImageField(upload_to='logo/', blank=True, null=True)
    favicon = models.ImageField(upload_to='logo/', blank=True, null=True)

    class Meta:
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Site Settings"
