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
    
    # Prepare the response for the respective API
    def serialize(self):
        return {
            "id": self.id,
            "username": self.user.username,
            "content": self.content,
            "timestamp": self.timestamp.strftime("%B %d, %Y, %#I:%M %p").replace('PM', 'p.m.').replace('AM', 'a.m.'),
            "likes_count": self.likes_count()
        }
    
class Comment(models.Model):
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
class Like(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name='likes')
    like = models.BooleanField(default=False)