# File: blog/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- Main Public Pages ---
    path('', views.PostListView.as_view(), name='post_list'),
    path('post/<int:pk>/', views.PostDetailView.as_view(), name='post_detail'),

    # --- Static Pages (Public) ---
    path('about/', views.about, name='about'),
    path('privacy/', views.privacy, name='privacy'),
    path('contacts/', views.contacts, name='contacts'),

    # --- Search & Profile (Public) ---
    path('search/', views.search_results, name='search_results'),
    path('profile/<str:username>/', views.profile_page, name='profile_page'),

    # --- User Authentication ---
    path('register/', views.register, name='register'),
    # login/logout are handled in project urls

    # --- PROTECTED User Actions ---
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),

    # --- Post Management ---
    path('post/new/', views.PostCreateView.as_view(), name='post_create'),
    path('post/<int:pk>/update/', views.PostUpdateView.as_view(), name='post_update'),
    path('post/<int:pk>/delete/', views.PostDeleteView.as_view(), name='post_delete'),
    path('notifications/mark-as-read/', views.mark_notifications_as_read, name='mark_notifications_as_read'),
    path('notifications/get-count/', views.get_notification_count, name='get_notification_count'),
    path('notifications/get-html/', views.get_notifications_html, name='get_notifications_html'),
    # --- Comment System ---
    path('post/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('comment/<int:pk>/edit/', views.edit_my_comment, name='edit_my_comment'),
    path("comment/reply/", views.reply_comment, name="reply_comment"),
    path('post/<int:pk>/sort_comments/', views.sort_comments, name='sort_comments'),
    #path('post/<int:pk>/get_comments/', views.get_comments_html, name='get_comments_html'),


    # ✅ Unified AJAX comment actions (upvote, downvote, delete)
    path('comment/action/', views.comment_action, name='comment_action'),
    path('ajax/posts/', views.ajax_post_list, name='ajax_post_list'),
    

    # --- Admin Section ---
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/comments/', views.admin_comments, name='admin_comments'),
    path('admin/comment/<int:pk>/approve/', views.approve_comment, name='approve_comment'),
    path('admin/comment/<int:pk>/delete/', views.delete_comment, name='delete_comment'),
    path('admin/assign-author/', views.assign_author_role, name='assign_author_role'),
    path("admin-dashboard/ban/", views.ban_user, name="ban_user"),
    path("admin-dashboard/unban/<int:user_id>/", views.unban_user, name="unban_user"),
    path('admin/set-featured-post/', views.set_featured_post, name='set_featured_post'),
    path('admin/inquiries/', views.admin_inquiries, name='admin_inquiries'),
    path('admin/inquiry/<int:pk>/status/<str:status>/', views.update_inquiry_status, name='update_inquiry_status'),
    path('admin/inquiry/<int:pk>/delete/', views.delete_inquiry, name='delete_inquiry'),

]