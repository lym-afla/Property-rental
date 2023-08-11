from django.contrib import admin
from .models import User, Post, Like

# Register the User model
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'date_joined', 'get_followers_count', 'get_following_count')
    list_filter = ('is_superuser', 'date_joined')
    search_fields = ('username', 'email')
    
    def get_followers_count(self, obj):
        return obj.followers.count()
    get_followers_count.short_description = 'Followers'

    def get_following_count(self, obj):
        return obj.following.count()
    get_following_count.short_description = 'Following'

# Register the Post model
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'timestamp')
    list_filter = ('timestamp', 'user')
    search_fields = ('user__username', 'content')

# Register the Like model
@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post')
    list_filter = ('user', 'post')
    search_fields = ('user__username', 'post__content')

# This line is required to make the admin classes effective
admin.site.site_header = 'Your App Admin'  # Customize the admin header text
