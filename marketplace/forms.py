from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils import timezone

from .models import Application, Job, Profile, Review, User


class SignUpForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    role = forms.ChoiceField(choices=User.Role.choices, widget=forms.RadioSelect)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email


class LoginForm(AuthenticationForm):
    role = forms.ChoiceField(choices=User.Role.choices, widget=forms.RadioSelect)

    def clean(self):
        cleaned_data = super().clean()
        user = self.get_user()
        selected_role = cleaned_data.get("role")
        if user is not None and selected_role and user.role != selected_role:
            article = "an" if user.role == User.Role.EMPLOYER else "a"
            raise forms.ValidationError(
                f"This account is registered as {article} {user.get_role_display().lower()}. "
                "Choose the matching account type."
            )
        return cleaned_data


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = (
            "title",
            "category",
            "schedule",
            "start_date",
            "location",
            "pay",
            "description",
            "interview_questions",
            "is_urgent",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "interview_questions": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"start_date": "Start date"}
        help_texts = {"start_date": "Optional. Choose a date from the calendar, or leave blank if the date is not set."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_date"].widget.attrs["min"] = timezone.localdate().isoformat()

    def clean_start_date(self):
        start_date = self.cleaned_data["start_date"]
        if start_date and start_date < timezone.localdate():
            raise forms.ValidationError("Choose today or a future date.")
        return start_date


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ("introduction", "answers")
        labels = {"introduction": "Introduce yourself", "answers": "Answers to the employer’s questions"}
        widgets = {
            "introduction": forms.Textarea(attrs={"rows": 4}),
            "answers": forms.Textarea(attrs={"rows": 4}),
        }


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    available_now = forms.BooleanField(
        required=False,
        label="Available now",
        help_text="Show signed-in employers that you may be able to take household work soon. This is self-reported.",
    )

    class Meta:
        model = Profile
        fields = ("location", "about", "experience", "skills", "available_now")
        widgets = {
            "about": forms.Textarea(attrs={"rows": 3}),
            "experience": forms.Textarea(attrs={"rows": 4}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "comment")
        widgets = {
            "rating": forms.Select(choices=((5, "5 — Excellent"), (4, "4 — Very good"), (3, "3 — Good"), (2, "2 — Could be better"), (1, "1 — Poor"))),
            "comment": forms.Textarea(attrs={"rows": 4}),
        }
