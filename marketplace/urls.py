from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import LoginForm
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/signup/", views.signup, name="signup"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="marketplace/login.html",
            form_class=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="marketplace/password_reset_form.html",
            email_template_name="marketplace/password_reset_email.txt",
            subject_template_name="marketplace/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="marketplace/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="marketplace/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="marketplace/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/new/", views.job_create, name="job_create"),
    path("jobs/<int:job_id>/", views.job_detail, name="job_detail"),
    path("jobs/<int:job_id>/apply/", views.apply_for_job, name="apply_for_job"),
    path("applications/", views.applications, name="applications"),
    path("helpers/<int:helper_id>/", views.helper_profile, name="helper_profile"),
    path("applications/<int:application_id>/status/", views.update_application_status, name="update_application_status"),
    path("messages/", views.conversations, name="conversations"),
    path("messages/<int:conversation_id>/", views.conversation_detail, name="conversation_detail"),
    path("reviews/", views.reviews, name="reviews"),
    path("applications/<int:application_id>/review/", views.create_review, name="create_review"),
    path("profile/", views.profile, name="profile"),
    path("safety/", views.safety, name="safety"),
    path("assistant/", views.assistant, name="assistant"),
    path("moya-guide/", views.moya_guide, name="moya_guide"),
]
