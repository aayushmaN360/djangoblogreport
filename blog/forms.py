# File: blog/forms.py
from django import forms
from .models import Post, Comment, Genre, Profile
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


# ========================
# Post Form
# ========================
class PostForm(forms.ModelForm):
    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all(),
        empty_label="Select a Genre",
        required=True
    )

    class Meta:
        model = Post
        fields = ['title', 'genre', 'content', 'photo']


# ========================
# Comment Form
# ========================
class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Join the discussion... (max 100 words)'
            }),
        }

    def clean_text(self):
        text = self.cleaned_data.get('text', '')
        word_limit = 100
        word_count = len(text.strip().split())
        if word_count > word_limit:
            raise forms.ValidationError(
                f"Please keep your comment under {word_limit} words. "
                f"You have used {word_count} words."
            )
        return text


# ========================
# Contact Form
# ========================
class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your name'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': "What's on your mind?"
        })
    )


# ========================
# User Registration Form
# ========================
class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


# ========================
# User Update Form
# ========================
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This email is already taken.')
        return email


# ========================
# Profile Update Form
# ========================
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
        }
