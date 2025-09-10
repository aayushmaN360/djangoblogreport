# File: blog/models.py
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from ckeditor.fields import RichTextField

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics')
    bio = models.TextField(max_length=500, blank=True)
    comment_ban_until = models.DateTimeField(null=True, blank=True)
    def __str__(self): return f'{self.user.username} Profile'
    @property
    def is_banned(self): return bool(self.comment_ban_until and timezone.now() < self.comment_ban_until)

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True);
    def __str__(self): return self.name

class Post(models.Model):
    title = models.CharField(max_length=200); genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True); content = RichTextField(); photo = models.ImageField(upload_to='post_photos/', blank=True, null=True); author = models.ForeignKey(User, on_delete=models.CASCADE); created_at = models.DateTimeField(default=timezone.now); updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering = ['-created_at']
    def __str__(self): return self.title
    def get_absolute_url(self): return reverse('post_detail', kwargs={'pk': self.pk})

class Comment(models.Model):
    STATUS_CHOICES = (('approved', 'Approved'), ('pending_review', 'Pending Review'), ('reported', 'Reported'), ('rejected', 'Rejected'))
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments'); author = models.ForeignKey(User, on_delete=models.CASCADE); text = models.TextField(); created_at = models.DateTimeField(default=timezone.now); parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies'); upvotes = models.ManyToManyField(User, related_name='comment_upvotes', blank=True); downvotes = models.ManyToManyField(User, related_name='comment_downvotes', blank=True); status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved'); toxicity_label = models.CharField(max_length=50, null=True, blank=True); is_edited = models.BooleanField(default=False)
    class Meta: ordering = ['created_at'] # Oldest first for conversation flow
    def __str__(self): return f"Comment by {self.author} on {self.post.title}"
    def get_vote_score(self): return self.upvotes.count() - self.downvotes.count()
    def user_upvoted(self, user):
        if user.is_authenticated:
            return self.upvotes.filter(pk=user.pk).exists()
        return False

    def user_downvoted(self, user):
        if user.is_authenticated:
            return self.downvotes.filter(pk=user.pk).exists()
        return False

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications'); message = models.CharField(max_length=255); created_at = models.DateTimeField(default=timezone.now); read = models.BooleanField(default=False); comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    def __str__(self): return f"Notification for {self.user.username}"

class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default="Sanity Check"); logo = models.ImageField(upload_to='logo/', blank=True, null=True); favicon = models.ImageField(upload_to='logo/', blank=True, null=True)
    def __str__(self): return "Site Settings"
    class Meta: verbose_name_plural = "Site Settings"