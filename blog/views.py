
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Count, Q, Prefetch 
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import Group
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.db.models import F #
from django.views.generic import DetailView
from django.db.models import Count, Q
from .models import Post, Comment
from .forms import CommentForm
from .forms import ContactForm
from django.template.loader import render_to_string
# In blog/views.py -- Add these new views at the end of the file

from .models import UserInquiry # Make sure UserInquiry is imported at the top



from .models import Post, Comment, Notification, Genre, Profile 

from .forms import PostForm, CommentForm, UserRegisterForm, UserUpdateForm, ProfileUpdateForm 
from .ai_toxicity import toxicity_classifier 
from django.contrib.admin.views.decorators import staff_member_required


# ==============================================================================
# --- PUBLIC-FACING VIEWS (Visible to Everyone) ---
# ==============================================================================

class PostListView(ListView):
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 5
    ordering = ['-created_at']  # default order: newest first

    def get_queryset(self):
        # Start with the default queryset (newest first)
        queryset = super().get_queryset()

        # Check if the user requested a sort order
        sort_option = self.request.GET.get("sort")

        if sort_option == "oldest":
            return queryset.order_by("created_at")

        elif sort_option == "comments":
            # Order by approved comment count
            return queryset.annotate(
                approved_comment_count=Count("comments", filter=Q(comments__status="approved"))
            ).order_by("-approved_comment_count", "-created_at")

        # Default: newest posts
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ==============================================================
        # === Featured Post (Admin picks first, fallback to smart pick)
        # ==============================================================
        featured_post = Post.objects.filter(is_featured=True).first()

        if not featured_post:
            featured_post = Post.objects.annotate(
                approved_comment_count=Count("comments", filter=Q(comments__status="approved"))
            ).order_by("-approved_comment_count", "-view_count").first()

        context["featured_post"] = featured_post

        # ==============================================================
        # === Sidebar: Popular Posts (exclude featured post)
        # ==============================================================
        popular_posts_query = Post.objects.annotate(
            approved_comment_count=Count("comments", filter=Q(comments__status="approved"))
        ).order_by("-approved_comment_count", "-view_count")

        if featured_post:
            popular_posts_query = popular_posts_query.exclude(pk=featured_post.pk)

        context["popular_posts"] = popular_posts_query[:5]

        # Latest 5 approved comments
        context["recent_comments"] = Comment.objects.filter(
            status="approved"
        ).order_by("-created_at")[:5]

        return context


def ajax_post_list(request):
    page_number = request.GET.get('page', 1)
    posts_list = Post.objects.all().order_by('-created_at')
    paginator = Paginator(posts_list, 6) # Use your paginate_by value
    page_obj = paginator.get_page(page_number)
    
    posts_html = render_to_string(
        'blog/includes/post_cards.html', 
        {'page_obj': page_obj, 'user': request.user}
    )
    pagination_html = render_to_string(
        'blog/includes/pagination.html', 
        {'page_obj': page_obj, 'paginator': paginator, 'is_paginated': True}
    )
    
    return JsonResponse({
        'posts_html': posts_html,
        'pagination_html': pagination_html,
    })

class PostDetailView(DetailView):
    model = Post
    template_name = "blog/post_detail.html"
    context_object_name = "post"

    def get_object(self, queryset=None):
        # This is perfect, no changes needed.
        obj = super().get_object(queryset)
        Post.objects.filter(pk=obj.pk).update(view_count=F("view_count") + 1)
        obj.refresh_from_db()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.get_object()
        user = self.request.user

        if user.is_authenticated:
            visibility_filter = (Q(status='approved') & ~Q(reported_by=user)) | Q(author=user)
        else:
            visibility_filter = Q(status='approved')

        visible_replies_prefetch = Prefetch(
            'replies',
            queryset=Comment.objects.filter(visibility_filter).select_related('author__profile'),
            to_attr='visible_replies' # Store the filtered replies in a new attribute
        )

        # 2. Get the base queryset of top-level comments, applying our new prefetch.
        all_visible_comments = (
            post.comments.filter(parent__isnull=True) # Start with top-level only
            .filter(visibility_filter)
            .select_related("author__profile")
            .prefetch_related("upvotes", "downvotes", visible_replies_prefetch)
        )

        # The rest of your code is perfect and works on this corrected base query.
        sort_option = self.request.GET.get("sort", "newest")
        if sort_option == "top":
            comments = all_visible_comments.annotate(score=Count("upvotes") - Count("downvotes")).order_by("-score", "-created_at")
        elif sort_option == "oldest":
            comments = all_visible_comments.order_by("created_at")
        else:
            comments = all_visible_comments.order_by("-created_at")

        if user.is_authenticated:
            # This loop is also fine, as it runs on the final sorted list.
            for comment in comments:
                comment.user_has_upvoted = comment.upvotes.filter(pk=user.pk).exists()
                comment.user_has_downvoted = comment.downvotes.filter(pk=user.pk).exists()

        context["comments"] = comments
        context["form"] = CommentForm()
        context["sort"] = sort_option
        return context
@login_required
def admin_inquiries(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to view this page.")
        return redirect("post_list")

    status_filter = request.GET.get('status', 'new')
    inquiries = UserInquiry.objects.filter(status=status_filter)
    new_inquiries_count = UserInquiry.objects.filter(status='new').count()

    context = {
        'inquiries': inquiries,
        'new_inquiries_count': new_inquiries_count,
        'status_filter': status_filter,
    }
    return render(request, 'blog/admin_inquiries.html', context)

@login_required
def update_inquiry_status(request, pk, status):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    
    inquiry = get_object_or_404(UserInquiry, pk=pk)
    inquiry.status = status
    inquiry.save()
    messages.success(request, f"Inquiry from {inquiry.name} marked as {status}.")
    return redirect('admin_inquiries')

@login_required
def delete_inquiry(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
        
    inquiry = get_object_or_404(UserInquiry, pk=pk)
    inquiry.delete()
    messages.success(request, f"Inquiry from {inquiry.name} has been deleted.")
    return redirect('admin_inquiries')    

@login_required
@require_POST
def comment_action(request):
    if not request.headers.get("x-requested-with") == "XMLHttpRequest":
        return HttpResponseForbidden()

    comment_id = request.POST.get("comment_id")
    action = request.POST.get("action")
    user = request.user
    comment = get_object_or_404(Comment, pk=comment_id)

    if action == "upvote":
        if user in comment.downvotes.all():
            comment.downvotes.remove(user)
        if user in comment.upvotes.all():
            comment.upvotes.remove(user)
        else:
            comment.upvotes.add(user)

    
    elif action == "downvote":
        if user in comment.upvotes.all():
            comment.upvotes.remove(user)
        if user in comment.downvotes.all():
            comment.downvotes.remove(user)
        else:
            comment.downvotes.add(user)

   
    elif action == "delete":
        if user == comment.author or user.is_superuser or user.is_staff:
            comment.delete()
            return JsonResponse({"status": "deleted"})
        else:
            return JsonResponse(
                {"status": "error", "message": "You are not authorized to delete this comment."},
                status=403,
            )

    elif action == "report":
        if user == comment.author:
            return JsonResponse(
                {"status": "error", "message": "You cannot report your own comment."},
                status=400,
            )

        # Let the model handle the logic (hide after 3 reports)
        comment.add_report(user)

        # Return a consistent response every time
        return JsonResponse({
            "status": "reported",
            "message": "Your report has been submitted for review.",
            "report_count": comment.reported_by.count(),
            "user_has_reported": True,
            "is_hidden": (comment.status == "hidden"),  # frontend can fade it out
        })

    
    else:
        return JsonResponse({"status": "error", "message": "Invalid action"}, status=400)

    
    return JsonResponse({
        "status": "ok",
        "upvotes": comment.upvotes.count(),
        "downvotes": comment.downvotes.count(),
    })

def sort_comments(request, pk):
    post = get_object_or_404(Post, pk=pk)
    user = request.user

 

    if user.is_authenticated:
        visibility_filter = (Q(status='approved') & ~Q(reported_by=user)) | Q(author=user)
    else:
        visibility_filter = Q(status='approved')

    # 2. Use the secure Prefetch object to fetch ONLY visible replies.
    visible_replies_prefetch = Prefetch(
        'replies',
        queryset=Comment.objects.filter(visibility_filter).select_related('author__profile'),
        to_attr='visible_replies'
    )

    # 3. Get the base queryset of visible, top-level comments, applying the prefetch.
    all_visible_comments = (
        post.comments.filter(parent__isnull=True)
        .filter(visibility_filter)
        .select_related("author__profile")
        .prefetch_related("upvotes", "downvotes", visible_replies_prefetch)
    )

    # 4. Apply the sorting to this secure and correct base query.
    sort_option = request.GET.get("sort", "newest")
    if sort_option == "top":
        comments = all_visible_comments.annotate(score=Count("upvotes") - Count("downvotes")).order_by("-score", "-created_at")
    elif sort_option == "oldest":
        comments = all_visible_comments.order_by("created_at")
    else: # "newest"
        comments = all_visible_comments.order_by("-created_at")

    # Pre-calculate vote status for the user
    if user.is_authenticated:
        for comment in comments:
            comment.user_has_upvoted = comment.upvotes.filter(pk=user.pk).exists()
            comment.user_has_downvoted = comment.downvotes.filter(pk=user.pk).exists()

    # The rest of the view is correct.
    context = {"comments": comments, "user": user, "post": post}
    html = render_to_string("blog/includes/comment_list.html", context, request=request)
    return JsonResponse({"html": html})

@require_POST
def reply_comment(request):
    if not request.headers.get("x-requested-with") == "XMLHttpRequest":
        return HttpResponseForbidden()

    parent_id = request.POST.get("parent_id")
    text = request.POST.get("text")
    parent = get_object_or_404(Comment, pk=parent_id)

    reply = Comment.objects.create(
        post=parent.post,
        author=request.user,
        text=text,
        parent=parent,
        status="approved" if not parent.post.requires_moderation else "pending_review",
    )

    html = render_to_string(
        "blog/includes/comment.html",
        {"comment": reply, "user": request.user, "post": parent.post},
        request=request,
    )

    # ✅ Match the status with add_comment
    return JsonResponse({
        "status": reply.status,
        "message": "Reply added successfully." if reply.status == "approved" else "Reply pending review.",
        "html": html if reply.status == "approved" else ""
    })

def contacts(request):
    """
    Handles both displaying the contact form and processing its submission.
    """
    if request.method == 'POST':
        # This block runs when the user clicks "Send Message"
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save() # This saves the new inquiry to the database
            messages.success(request, "Thank you for your message! Our team will review it shortly.")
            return redirect('contacts') # Redirect to the same page to show the success message
    else:
        # This block runs when the user first visits the page
        form = ContactForm()

    # Pass the form instance to the template
    return render(request, 'blog/contacts.html', {'form': form})
@login_required
def assign_author_role(request):
    # Security: Only superusers can perform this action
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('post_list')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        if user_id:
            try:
                user_to_promote = User.objects.get(pk=user_id)
                author_group, created = Group.objects.get_or_create(name='Authors')
                user_to_promote.groups.add(author_group)
                messages.success(request, f"Successfully promoted {user_to_promote.username} to Author.")
            except User.DoesNotExist:
                messages.error(request, "The selected user does not exist.")
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")

    return redirect('admin_dashboard')

def search_results(request):
    query = request.GET.get('q')
    posts = Post.objects.filter(Q(title__icontains=query) | Q(content__icontains=query)).distinct().order_by('-created_at') if query else Post.objects.none()
    return render(request, 'blog/search_results.html', {'posts': posts, 'query': query})

def profile_page(request, username):
    profile_user = get_object_or_404(User.objects.select_related('profile'), username=username)

    # The get_or_create is still a good idea for users who haven't been viewed before.
    Profile.objects.get_or_create(user=profile_user)
    # This will now work
    context = {
        'profile_user': profile_user,
        'posts': Post.objects.filter(author=profile_user).order_by('-created_at'),
        'comments': Comment.objects.filter(author=profile_user, status='approved').order_by('-created_at'),
    }
    return render(request, 'blog/profile_page.html', context) # You were missing a return here
@login_required
def profile_edit(request):
    Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your account has been updated!')
            return redirect('profile_page', username=request.user.username)
        else:
            # Re-render the profile page with error messages in the modal
            messages.error(request, 'Please correct the error(s) below.')
            context = { 'u_form': u_form, 'p_form': p_form }
            return render(request, 'blog/profile.html', context)  # Make sure your modal lives here!
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = { 'u_form': u_form, 'p_form': p_form }
    return render(request, 'blog/profile.html', context)

# ==============================================================================
# --- USER REGISTRATION & PROTECTED VIEWS ---
# ==============================================================================

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'registration/register.html', {'form': form})

class PostCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Post; form_class = PostForm; template_name = 'blog/post_form.html'; permission_required = 'blog.add_post'
    def form_valid(self, form): form.instance.author = self.request.user; return super().form_valid(form)

class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post; form_class = PostForm; template_name = 'blog/post_form.html'
    def test_func(self): return self.request.user == self.get_object().author

class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post; template_name = 'blog/post_confirm_delete.html'; success_url = reverse_lazy('post_list')
    def test_func(self): return self.request.user == self.get_object().author

@staff_member_required
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    post_pk = comment.post.pk
    comment.delete()
    messages.success(request, "Comment deleted successfully.")
    return redirect('admin_comments')



# @login_required
# @require_POST
# def add_comment(request, pk):
#     post = get_object_or_404(Post, pk=pk)
#     user = request.user
#     is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
#     new_notification_count = 0

#     # === Banned User Check ===
#     if hasattr(user, "profile") and getattr(user.profile, "is_banned", False):
#         if is_ajax:
#             return JsonResponse(
#                 {"status": "error", "message": "You are temporarily banned from commenting."},
#                 status=403
#             )
#         messages.error(request, "You are temporarily banned from commenting.")
#         return redirect("post_detail", pk=post.pk)

#     # === Main Comment Logic ===
#     form = CommentForm(request.POST)
#     if form.is_valid():
#         comment = form.save(commit=False)
#         comment.post = post
#         comment.author = user

#         # Handle replies
#         parent_id = request.POST.get("parent_id")
#         if parent_id:
#             comment.parent = get_object_or_404(Comment, pk=parent_id, post=post)

#         # Run toxicity check
#         is_toxic, label = toxicity_classifier.predict(comment.text)

#         # --- Save + Notifications ---
#         if not is_toxic:
#             comment.status = "approved"
#             message = "Your comment was posted successfully."
#             status_code = 200
#             comment.save()

#         elif label == "toxic":
#             comment.status = "pending_review"
#             comment.toxicity_label = label
#             message = "Your comment was flagged and requires review."
#             status_code = 201
#             comment.save()

#         elif label == "highly-toxic":
#             user.profile.comment_ban_until = timezone.now() + timedelta(minutes=5)
#             user.profile.save()
#             message = "Highly-toxic comment rejected. You are blocked from commenting for 5 minutes."
#             if is_ajax:
#                 return JsonResponse({"status": "error", "message": message}, status=400)
#             messages.error(request, message)
#             return redirect("post_detail", pk=post.pk)

       
#         if not comment.parent and comment.status == 'approved' and post.author != user:
#             Notification.objects.create(
#                 user=post.author,
#                 notification_type='new_comment',  # <-- SET TYPE
#                 message=f"{user.username} left a new comment on your post: '{post.title}'.",
#                 comment=comment
#             )

#         # 2. Notify the parent comment's author of a new reply.
#         if comment.parent and comment.status == 'approved' and comment.parent.author != user:
#             Notification.objects.create(
#                 user=comment.parent.author,
#                 notification_type='new_reply',  # <-- SET TYPE
#                 message=f"{user.username} replied to your comment on '{post.title}'.",
#                 comment=comment
#             )

#         # 3. Notify the user if their comment was flagged as toxic.
#         if comment.status == 'pending_review':
#             Notification.objects.create(
#                 user=user,
#                 notification_type='toxic_comment',  # <-- SET TYPE
#                 message=f"Your comment on '{post.title}' requires editing.",
#                 comment=comment
#             )
#             # Only calculate count for this user's AJAX response
#             new_notification_count = Notification.objects.filter(user=user, read=False).count()

#         # === AJAX Response ===
#         if is_ajax:
#             html = ""
#             if comment.status in ["approved", "pending_review"]:
#                 html = render_to_string(
#                     "blog/includes/comment.html",
#                     {"comment": comment, "user": user, "post": post},
#                     request=request
#                 )
#             return JsonResponse({
#                 "status": comment.status,
#                 "message": message,
#                 "html": html,
#                 "new_notification_count": new_notification_count
#             }, status=status_code)

#         # === Normal (non-AJAX) Response ===
#         messages.success(request, message)
#         return redirect("post_detail", pk=post.pk)

#     # ❌ Invalid form
#     if is_ajax:
#         return JsonResponse(
#             {"status": "error", "message": "There was a problem with your submission."},
#             status=400
#         )

#     return redirect("post_detail", pk=post.pk)

@login_required
@require_POST
def add_comment(request, pk):
    post = get_object_or_404(Post, pk=pk)
    user = request.user
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    new_notification_count = 0
    new_notification_html = ""
    message_for_commenter = ""

    # === Banned user check (time-based, safer than boolean) ===
    if hasattr(user, "profile") and getattr(user.profile, "comment_ban_until", None):
        if user.profile.comment_ban_until and user.profile.comment_ban_until > timezone.now():
            msg = "🚫 You are temporarily banned from commenting."
            if is_ajax:
                return JsonResponse({"status": "error", "message": msg}, status=403)
            messages.error(request, msg)
            return redirect("post_detail", pk=post.pk)

    form = CommentForm(request.POST)
    if not form.is_valid():
        if is_ajax:
            return JsonResponse({"status": "error", "message": "Invalid form submission."}, status=400)
        messages.error(request, "Invalid comment form submission.")
        return redirect("post_detail", pk=post.pk)

    # === Build comment ===
    comment = form.save(commit=False)
    comment.post = post
    comment.author = user

    parent_id = request.POST.get("parent_id")
    if parent_id:
        comment.parent = get_object_or_404(Comment, pk=parent_id, post=post)

    # === Toxicity check ===
    is_toxic, label = toxicity_classifier.predict(comment.text)

    html = ""
    status_code = 200
    notification_recipient = None

    # ---------------- CASE A: Non-toxic ----------------
    if not is_toxic:
        comment.status = "approved"
        comment.save()
        message_for_commenter = "✅ Your comment was posted successfully."
        status_code = 200

        # Notify post author or parent comment author
        if not comment.parent and post.author != user:
            notification_recipient = post.author
            notif_type = "new_comment"
            notif_message = f"{user.username} left a new comment on your post: '{post.title}'."
        elif comment.parent and comment.parent.author != user:
            notification_recipient = comment.parent.author
            notif_type = "new_reply"
            notif_message = f"{user.username} replied to your comment on '{post.title}'."

        if notification_recipient:
            notification = Notification.objects.create(
                user=notification_recipient,
                notification_type=notif_type,
                message=notif_message,
                comment=comment,
            )
            new_notification_html = render_to_string(
                "blog/includes/notification_item.html",
                {"notification": notification},
                request=request,
            )

    # ---------------- CASE B: Toxic ----------------
    elif label == "toxic":
        comment.status = "pending_review"
        comment.toxicity_label = label
        comment.save()
        message_for_commenter = "⚠️ Your comment was flagged and sent for review. You can edit it later."
        status_code = 201

        # Notify the commenter (self)
        notification = Notification.objects.create(
            user=user,
            notification_type="toxic_comment",
            message=f"Your comment on '{post.title}' requires editing.",
            comment=comment,
        )
        new_notification_html = render_to_string(
            "blog/includes/notification_item.html",
            {"notification": notification},
            request=request,
        )

        new_notification_count = Notification.objects.filter(user=user, read=False).count()

    # ---------------- CASE C: Highly toxic ----------------
    elif label == "highly-toxic":
        comment.status = "rejected"
        comment.toxicity_label = label
        comment.save()  # Save for moderation record

        user.profile.comment_ban_until = timezone.now() + timedelta(minutes=5)
        user.profile.save()

        message_for_commenter = "🚫 Highly toxic comment rejected. You are blocked from commenting for 5 minutes."
        if is_ajax:
            return JsonResponse({"status": "error", "message": message_for_commenter}, status=400)
        messages.error(request, message_for_commenter)
        return redirect("post_detail", pk=post.pk)

    # === Notification count update (for all cases with recipients) ===
    if notification_recipient:
        new_notification_count = Notification.objects.filter(
            user=notification_recipient, read=False
        ).count()

    # === AJAX Response ===
    if is_ajax:
        if comment.status in ["approved", "pending_review"]:
            html = render_to_string(
                "blog/includes/comment.html",
                {"comment": comment, "user": user, "post": post},
                request=request,
            )

        return JsonResponse(
            {
                "status": comment.status,
                "message": message_for_commenter,
                "html": html,
                "new_notification_count": new_notification_count,
                "new_notification_html": new_notification_html,
            },
            status=status_code,
        )

    # === Non-AJAX fallback ===
    messages.success(request, message_for_commenter)
    return redirect("post_detail", pk=post.pk)


@login_required
def dashboard(request):
    user = request.user

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('dashboard')
        else:
            # If there's an error, set a flag so the modal re-opens
            messages.error(request, 'Please correct the errors below.')
    else:
        # For a normal page load, create fresh form instances
        u_form = UserUpdateForm(instance=user)
        p_form = ProfileUpdateForm(instance=user.profile)
    
    # --- Gather all other data for display ---
    all_comments = Comment.objects.filter(author=user).order_by('-created_at')
    notifications = Notification.objects.filter(user=user).order_by('-created_at')
    notifications.filter(read=False).update(read=True)
    is_author = user.groups.filter(name='Authors').exists() or user.is_superuser
    
    context = {
        'all_comments': all_comments,
        'action_required_comments': all_comments.filter(status='pending_review'),
        'notifications': notifications,
        'is_author': is_author,
        'u_form': u_form, # This will be either the blank form or the form with errors
        'p_form': p_form,
    }

    if is_author:
        user_posts = Post.objects.filter(author=user).order_by('-created_at')
        context['user_posts'] = user_posts
        if user_posts.exists():
            first_post = user_posts.order_by('created_at').first()
            context['author_stats'] = {
                'total_posts': user_posts.count(),
                'total_comments_received': Comment.objects.filter(post__in=user_posts).count(),
                'time_as_author': timezone.now() - first_post.created_at
            }
    
    return render(request, 'blog/dashboard.html', context)
def get_featured_post():
    
    recent_date = datetime.now() - timedelta(days=7)
    
    return Post.objects.filter(
        created_at__gte=recent_date,
        status='published'  # assuming you have status field
    ).annotate(
        comment_count=Count('comment'),
        engagement_score=(
            Count('comment') * 3 +  
            Count('upvotes') * 1 +  
            F('view_count') * 0.1   
        )
    ).order_by('-engagement_score', '-created_at').first()

@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to view this page.")
        return redirect("post_list")

   
    author_group, _ = Group.objects.get_or_create(name="Authors")
    potential_authors = User.objects.filter(is_superuser=False).exclude(groups=author_group)
    bannable_users = User.objects.filter(is_superuser=False)
    banned_users = User.objects.filter(profile__comment_ban_until__gt=timezone.now())


    comments_to_moderate_query = Comment.objects.filter(
        Q(status='pending_review') | Q(status='hidden')
    ).distinct()
    
    stats = {
        "total_posts": Post.objects.count(),
        "total_comments": Comment.objects.count(),
        "total_users": User.objects.count(),
        "posts_with_photos": Post.objects.exclude(photo="").count(),
        "comments_to_moderate_count": comments_to_moderate_query.count(),
        "banned_users_count": banned_users.count(),
        "new_inquiries_count": UserInquiry.objects.filter(status='new').count(),
    }

    # --- Data for dashboard sections ---
    moderation_queue = comments_to_moderate_query.order_by("-created_at")[:5]
    recent_posts = Post.objects.order_by("-created_at")[:5]
    recent_approved_comments = Comment.objects.filter(status="approved").order_by("-created_at")[:5]
    all_posts = Post.objects.all()
    currently_featured_post = Post.objects.filter(is_featured=True).first()

    # --- Render page ---
    context = {
        "stats": stats,
        "potential_authors": potential_authors,
        "bannable_users": bannable_users,
        "banned_users": banned_users,
        "moderation_queue": moderation_queue,
        "recent_posts": recent_posts,
        "recent_approved_comments": recent_approved_comments,
        "all_posts": all_posts,
        "currently_featured_post": currently_featured_post,
    }

    return render(request, "blog/admin_dashboard.html", context)

@login_required
@require_POST # This view only accepts POST requests
def set_featured_post(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()

    post_id = request.POST.get('post_id')
    action = request.POST.get('action')

    try:
        post = Post.objects.get(pk=post_id)
        if action == 'feature':
            post.is_featured = True
            post.save() # The magic save() method will handle un-featuring others
            messages.success(request, f'"{post.title}" is now the featured post.')
        elif action == 'unfeature':
            post.is_featured = False
            post.save()
            messages.success(request, f'"{post.title}" is no longer featured.')
    except Post.DoesNotExist:
        messages.error(request, 'The selected post does not exist.')
    
    return redirect('admin_dashboard')
@login_required
def ban_user(request):
    if request.method == "POST" and request.user.is_staff:
        user_id = request.POST.get("user_id")
        user = get_object_or_404(User, pk=user_id)
        user.profile.comment_ban_until = timezone.now() + timedelta(hours=1)  # example: 1 hour
        user.profile.save()
        messages.success(request, f"{user.username} has been banned 🚫")
    return redirect("admin_dashboard")

@login_required
def unban_user(request, user_id):
    if request.user.is_staff:
        user = get_object_or_404(User, pk=user_id)
        user.profile.comment_ban_until = None
        user.profile.save()
        messages.success(request, f"{user.username} has been unbanned ✅")
    return redirect("admin_dashboard")

@login_required
def admin_comments(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('post_list')
    comments_to_moderate = Comment.objects.annotate(
        report_count=Count('reported_by')
    ).filter(
        Q(status='pending_review') | Q(status='hidden')
    ).distinct().order_by('-created_at')
    
    paginator = Paginator(comments_to_moderate, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'blog/admin_comments.html', {'comments': page_obj})

@login_required
def approve_comment(request, pk):
    if not request.user.is_superuser: return redirect('post_list')
    comment = get_object_or_404(Comment, pk=pk); comment.status = 'approved'; comment.save()
    Notification.objects.create(user=comment.author, message=f"Your comment on '{comment.post.title}' has been approved by an admin.", comment=comment)
    messages.success(request, 'Comment approved successfully.')
    return redirect('admin_comments')

@login_required
@require_POST
def mark_notifications_as_read(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        # Mark all of the user's unread notifications as read
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        return JsonResponse({'status': 'ok'})
    return HttpResponseForbidden()
@login_required
def get_notification_count(request):
    """A simple, lightweight view to return the unread notification count."""
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        count = Notification.objects.filter(user=request.user, read=False).count()
        return JsonResponse({'unread_count': count})
    return HttpResponseForbidden()
@login_required
def get_notifications_html(request):
    
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        html = render_to_string(
            'blog/includes/notification_list.html',
            {'notifications': notifications}
        )
        return JsonResponse({'html': html})
    return HttpResponseForbidden()
# In blog/views.py
@login_required
def edit_my_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk, author=request.user)

    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            edited_comment = form.save(commit=False)

            # ✅ Run toxicity check
            is_toxic, label = toxicity_classifier.predict(edited_comment.text)

            if is_toxic:
                edited_comment.status = 'pending_review'
                edited_comment.toxicity_label = label
                messages.warning(
                    request,
                    f"Your edited comment was flagged as '{label}' and requires review."
                )
            else:
                edited_comment.status = 'approved'
                messages.success(request, "Your comment has been updated and approved!")

            edited_comment.is_edited = True
            edited_comment.save()

            # ✅ Redirect back to the post, scrolling directly to the edited comment
            return redirect(f"{edited_comment.post.get_absolute_url()}#comment-{edited_comment.pk}")

    else:
        form = CommentForm(instance=comment)

    return render(request, 'blog/edit_comment.html', {'form': form, 'comment': comment})




def about(request):
   
    return render(request, 'blog/about.html')



def privacy(request):
   
    return render(request, 'blog/privacy.html')