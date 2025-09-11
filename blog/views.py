# blog/views.py

# --- Django and Python Imports ---
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


# --- Your Application's Imports ---
# CORRECTED: Added 'Profile' to the model imports
from .models import Post, Comment, Notification, Genre, Profile 
# CORRECTED: Combined all form imports into one line for cleanliness
from .forms import PostForm, CommentForm, UserRegisterForm, UserUpdateForm, ProfileUpdateForm 
from .ai_toxicity import toxicity_classifier # Assuming this file exists in your app
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

# In blog/views.py

# blog/views.py

from django.db.models import F, Q, Count
from django.views.generic import DetailView
from .models import Post
from .forms import CommentForm

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

        # Your visibility rules are perfect.
        if user.is_authenticated:
            visibility_filter = Q(status="approved") | Q(author=user)
        else:
            visibility_filter = Q(status="approved")

        # =========================================================================
        # === THE FINAL FIX: Apply the filter to the replies using Prefetch ===
        # =========================================================================
        
        # 1. Create a Prefetch object that fetches ONLY the visible replies.
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
@require_POST
def comment_action(request):
    if not request.headers.get("x-requested-with") == "XMLHttpRequest":
        return HttpResponseForbidden()

    comment_id = request.POST.get("comment_id")
    action = request.POST.get("action")
    comment = get_object_or_404(Comment, pk=comment_id)

    # --- Upvote ---
    if action == "upvote":
        if request.user in comment.downvotes.all():
            comment.downvotes.remove(request.user)
        if request.user in comment.upvotes.all():
            comment.upvotes.remove(request.user)
        else:
            comment.upvotes.add(request.user)

    # --- Downvote ---
    elif action == "downvote":
        if request.user in comment.upvotes.all():
            comment.upvotes.remove(request.user)
        if request.user in comment.downvotes.all():
            comment.downvotes.remove(request.user)
        else:
            comment.downvotes.add(request.user)

    # --- Delete ---
    elif action == "delete":
        if request.user == comment.author or request.user.is_superuser or request.user.is_staff:
            comment.delete()
            return JsonResponse({"status": "deleted"})
        else:
            return JsonResponse({"status": "error", "message": "You are not authorized to delete this comment."})

    # --- Report ---
    elif action == "report":
        if request.user != comment.author:
            comment.status = "reported"
            comment.save()
            return JsonResponse({"status": "reported", "message": "Comment reported for review."})
        else:
            return JsonResponse({"status": "error", "message": "You cannot report your own comment."})

    else:
        return JsonResponse({"status": "error", "message": "Invalid action"})

    # === THIS IS THE CRITICAL FIX FOR THE BUTTONS ===
    # We now send back separate upvote and downvote counts, which the JavaScript is waiting for.
    return JsonResponse({
        "status": "ok",
        "upvotes": comment.upvotes.count(),
        "downvotes": comment.downvotes.count(),
    })
def sort_comments(request, pk):
    post = get_object_or_404(Post, pk=pk)
    user = request.user

    # =========================================================================
    # === THIS IS THE FIX: We now use the same secure logic as the DetailView ===
    # =========================================================================

    # 1. Define the visibility rules, just like in PostDetailView.
    if user.is_authenticated:
        visibility_filter = Q(status="approved") | Q(author=user)
    else:
        visibility_filter = Q(status="approved")

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
    profile_user = get_object_or_404(User, username=username)
    Profile.objects.get_or_create(user=profile_user) # This will now work
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


# In blog/views.py - Replace the entire add_comment function

@login_required
def add_comment(request, pk):
    post = get_object_or_404(Post, pk=pk)
    user = request.user
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    new_notification_count = 0  # Initialize notification count

    if hasattr(user, "profile") and getattr(user.profile, "is_banned", False):
        if is_ajax:
            return JsonResponse(
                {"status": "error", "message": "You are temporarily banned from commenting."},
                status=403
            )
        messages.error(request, "You are temporarily banned from commenting.")
        return redirect("post_detail", pk=post.pk)

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = user

            parent_id = request.POST.get("parent_id")
            if parent_id:
                comment.parent = get_object_or_404(Comment, pk=parent_id, post=post)

            is_toxic, label = toxicity_classifier.predict(comment.text)

            if not is_toxic:
                comment.status = "approved"
                comment.save()
                message = "Your comment was posted successfully."
                status_code = 200

            elif label == "toxic":
                comment.status = "pending_review"
                comment.toxicity_label = label
                comment.save()
                Notification.objects.create(
                    user=user,
                    message=f"Your comment on '{post.title}' requires editing.",
                    comment=comment
                )
                new_notification_count = Notification.objects.filter(user=user, read=False).count()
                message = "Your comment was flagged and requires review. You can edit it now or in your dashboard."
                status_code = 201

            elif label == "highly-toxic":
                user.profile.comment_ban_until = timezone.now() + timedelta(minutes=5)
                user.profile.save()
                message = "Highly-toxic comment rejected. You are blocked from commenting for 5 minutes."
                if is_ajax:
                    return JsonResponse({"status": "error", "message": message}, status=400)
                messages.error(request, message)
                return redirect("post_detail", pk=post.pk)

            # ✅ AJAX response with notification fix
            if is_ajax:
                html = ""
                if comment.pk and comment.status in ["approved", "pending_review"]:
                    html = render_to_string(
                        "blog/includes/comment.html",
                        {"comment": comment, "user": request.user, "post": post},
                        request=request
                    )
                return JsonResponse({
                    "status": comment.status,
                    "message": message,
                    "html": html,
                    "new_notification_count": new_notification_count
                }, status=status_code)

            # Non-AJAX fallback
            messages.success(request, message)
            return redirect("post_detail", pk=post.pk)

    # Non-POST or invalid form
    if is_ajax:
        return JsonResponse(
            {"status": "error", "message": "There was a problem with your submission."},
            status=400
        )
    
    return redirect("post_detail", pk=post.pk)
@login_required
def dashboard(request):
    user = request.user

    # Handle the form submission
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
    # Get posts from last 7 days for freshness
    recent_date = datetime.now() - timedelta(days=7)
    
    return Post.objects.filter(
        created_at__gte=recent_date,
        status='published'  # assuming you have status field
    ).annotate(
        comment_count=Count('comment'),
        engagement_score=(
            Count('comment') * 3 +  # Comments are worth 3 points
            Count('upvotes') * 1 +  # Upvotes worth 1 point
            F('view_count') * 0.1   # Views worth 0.1 points
        )
    ).order_by('-engagement_score', '-created_at').first()


@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to view this page.")
        return redirect("post_list")

    author_group, _ = Group.objects.get_or_create(name="Authors")

    # Users eligible for author promotion (non-superusers, not already authors)
    potential_authors = User.objects.filter(is_superuser=False).exclude(groups=author_group)

    # All bannable users (all non-superusers, includes authors + normal users)
    bannable_users = User.objects.filter(is_superuser=False)

    # All banned users (still active ban period)
    banned_users = User.objects.filter(profile__comment_ban_until__gt=timezone.now())

    stats = {
        "total_posts": Post.objects.count(),
        "total_comments": Comment.objects.count(),
        "total_users": User.objects.count(),
        "posts_with_photos": Post.objects.exclude(photo="").count(),
        "comments_to_moderate_count": Comment.objects.filter(status="pending_review").count(),
        "banned_users_count": banned_users.count(),
    }

    moderation_queue = Comment.objects.filter(
        status__in=["pending_review", "reported"]
    ).order_by("-created_at")[:5]

    recent_posts = Post.objects.order_by("-created_at")[:5]
    recent_approved_comments = Comment.objects.filter(status="approved").order_by("-created_at")[:5]

    # === NEW FEATURED POST LOGIC ===
    all_posts = Post.objects.all()
    currently_featured_post = Post.objects.filter(is_featured=True).first()

    return render(request, "blog/admin_dashboard.html", {
        "stats": stats,
        "potential_authors": potential_authors,
        "bannable_users": bannable_users,
        "banned_users": banned_users,
        "moderation_queue": moderation_queue,
        "recent_posts": recent_posts,
        "recent_approved_comments": recent_approved_comments,
        "all_posts": all_posts,  # <--- Added
        "currently_featured_post": currently_featured_post,  # <--- Added
    })
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
    if not request.user.is_superuser: messages.error(request, "You do not have permission to access this page."); return redirect('post_list')
    comments_to_moderate = Comment.objects.filter(Q(status='pending_review') | Q(status='reported')).order_by('-created_at')
    paginator = Paginator(comments_to_moderate, 10); page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'blog/admin_comments.html', {'comments': page_obj})

@login_required
def approve_comment(request, pk):
    if not request.user.is_superuser: return redirect('post_list')
    comment = get_object_or_404(Comment, pk=pk); comment.status = 'approved'; comment.save()
    Notification.objects.create(user=comment.author, message=f"Your comment on '{comment.post.title}' has been approved by an admin.", comment=comment)
    messages.success(request, 'Comment approved successfully.')
    return redirect('admin_comments')



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
    """Renders the static About page."""
    return render(request, 'blog/about.html')

def contacts(request):
    """Renders the static Contact page."""
    return render(request, 'blog/contacts.html')

def privacy(request):
    """Renders the static Privacy Policy page."""
    return render(request, 'blog/privacy.html')