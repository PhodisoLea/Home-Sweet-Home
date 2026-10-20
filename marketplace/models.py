from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        EMPLOYER = "employer", "Employer"
        HELPER = "helper", "Helper"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices)

    @property
    def display_name(self):
        return self.get_full_name().strip() or self.username


class Profile(models.Model):
    class IdentityStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Not verified"
        PENDING = "pending", "Verification pending"
        VERIFIED = "verified", "Verified by a future provider"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    location = models.CharField(max_length=120, blank=True)
    about = models.TextField(max_length=700, blank=True)
    experience = models.TextField(max_length=1000, blank=True, help_text="Share relevant household-work experience.")
    skills = models.CharField(max_length=300, blank=True, help_text="Separate skills with commas.")
    available_now = models.BooleanField(
        default=False,
        verbose_name="Available now",
        help_text="Let signed-in employers know you may be available for household work soon.",
    )
    identity_status = models.CharField(
        max_length=12,
        choices=IdentityStatus.choices,
        default=IdentityStatus.UNVERIFIED,
    )

    def __str__(self):
        return f"Profile for {self.user.display_name}"


class Job(models.Model):
    class Category(models.TextChoices):
        CLEANING = "cleaning", "Cleaning"
        CHILDCARE = "childcare", "Child care"
        CAREGIVING = "caregiving", "Caregiving"
        GARDENING = "gardening", "Gardening"
        COOKING = "cooking", "Cooking"
        OTHER = "other", "Other household help"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    employer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="household_jobs"
    )
    title = models.CharField(max_length=100)
    category = models.CharField(max_length=12, choices=Category.choices)
    schedule = models.CharField(max_length=120)
    start_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=120)
    pay = models.CharField(max_length=60)
    description = models.TextField(max_length=1500)
    interview_questions = models.TextField(
        max_length=800,
        blank=True,
        help_text="Optional, job-related questions; put each question on a new line.",
    )
    is_urgent = models.BooleanField(
        default=False,
        verbose_name="Urgent / immediate start",
        help_text="Mark this if you need a helper to start as soon as possible.",
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


class Application(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "New"
        SHORTLISTED = "shortlisted", "Shortlisted"
        HIRED = "hired", "Hired"
        COMPLETED = "completed", "Work completed"
        DECLINED = "declined", "Declined"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    helper = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_applications"
    )
    introduction = models.TextField(max_length=1200)
    answers = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("job", "helper"), name="unique_helper_application_per_job")
        ]

    def __str__(self):
        return f"{self.helper.display_name} · {self.job.title}"


class Conversation(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="conversations")
    helper = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="helper_conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("job", "helper"), name="unique_job_helper_conversation")
        ]

    @property
    def employer(self):
        return self.job.employer

    def includes(self, user):
        return user == self.helper or user == self.job.employer

    def __str__(self):
        return f"{self.job.title} · {self.helper.display_name}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"Message from {self.sender.display_name}"


class Review(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written"
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received"
    )
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("job", "reviewer"), name="one_review_per_reviewer_per_job"),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="valid_review_rating"),
        ]

    def __str__(self):
        return f"{self.rating}/5 · {self.job.title}"
