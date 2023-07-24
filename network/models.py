from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    following = models.ManyToManyField("self", blank=True, symmetrical=False, related_name="followers")

class Post(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="posts")
    content = models.TextField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def likes_count(self):
        return self.likes.filter(like=True).count()
    
class Comment(models.Model):
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
class Like(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name='likes')
    like = models.BooleanField(default=False)