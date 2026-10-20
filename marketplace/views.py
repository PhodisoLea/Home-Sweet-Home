import re

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ApplicationForm, JobForm, ProfileForm, ReviewForm, SignUpForm
from .models import Application, Conversation, Job, Message, Profile, Review, User


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "marketplace/home.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    initial = {"role": request.GET.get("role")} if request.GET.get("role") in User.Role.values else None
    form = SignUpForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user)
        messages.success(request, "Your account is ready. Welcome to Home Help.")
        return redirect("dashboard")
    return render(request, "marketplace/signup.html", {"form": form})


def _profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _require_role(user, role):
    if user.role != role:
        raise PermissionDenied("This feature is not available for your account type.")


@login_required
def dashboard(request):
    profile = _profile(request.user)
    if request.user.role == User.Role.EMPLOYER:
        my_jobs = Job.objects.filter(employer=request.user).annotate(application_count=Count("applications"))
        recent_applications = Application.objects.filter(job__employer=request.user).select_related(
            "job", "helper", "helper__profile"
        )[:5]
        recent_conversations = Conversation.objects.filter(job__employer=request.user).select_related(
            "job", "helper"
        ).prefetch_related("messages")[:3]
        context = {
            "profile": profile,
            "my_jobs": my_jobs[:5],
            "job_count": my_jobs.filter(status=Job.Status.OPEN).count(),
            "application_count": Application.objects.filter(job__employer=request.user).count(),
            "recent_applications": recent_applications,
            "recent_conversations": recent_conversations,
        }
    else:
        my_applications = Application.objects.filter(helper=request.user).select_related(
            "job", "job__employer"
        )[:5]
        recent_conversations = Conversation.objects.filter(helper=request.user).select_related(
            "job", "job__employer"
        ).prefetch_related("messages")[:3]
        context = {
            "profile": profile,
            "my_jobs": Job.objects.filter(status=Job.Status.OPEN)[:5],
            "job_count": Job.objects.filter(status=Job.Status.OPEN).count(),
            "application_count": Application.objects.filter(helper=request.user).count(),
            "recent_applications": my_applications,
            "recent_conversations": recent_conversations,
        }
    return render(request, "marketplace/dashboard.html", context)


@login_required
def job_list(request):
    jobs = Job.objects.select_related("employer", "employer__profile").annotate(application_count=Count("applications"))
    if request.user.role == User.Role.EMPLOYER:
        jobs = jobs.filter(employer=request.user)
    else:
        jobs = jobs.filter(status=Job.Status.OPEN)
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(location__icontains=query)
            | Q(category__icontains=query)
        )
    if category in Job.Category.values:
        jobs = jobs.filter(category=category)
    return render(
        request,
        "marketplace/job_list.html",
        {"jobs": jobs, "query": query, "selected_category": category, "categories": Job.Category.choices},
    )


@login_required
def job_create(request):
    _require_role(request.user, User.Role.EMPLOYER)
    form = JobForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.employer = request.user
        job.save()
        messages.success(request, "Your household job is now visible to helpers.")
        return redirect("job_detail", job_id=job.pk)
    return render(request, "marketplace/job_form.html", {"form": form})


@login_required
def job_detail(request, job_id):
    job = get_object_or_404(Job.objects.select_related("employer", "employer__profile"), pk=job_id)
    if request.user.role == User.Role.EMPLOYER and job.employer_id != request.user.id:
        raise PermissionDenied("You can only view jobs posted by your account.")
    application = Application.objects.filter(job=job, helper=request.user).first()
    applications = (
        job.applications.select_related("helper", "helper__profile").annotate(
            helper_rating=Avg("helper__reviews_received__rating"),
            helper_review_count=Count("helper__reviews_received"),
        )
        if request.user.role == User.Role.EMPLOYER
        else None
    )
    application_form = ApplicationForm() if request.user.role == User.Role.HELPER and not application else None
    return render(
        request,
        "marketplace/job_detail.html",
        {"job": job, "application": application, "applications": applications, "application_form": application_form},
    )


@login_required
@require_POST
def apply_for_job(request, job_id):
    _require_role(request.user, User.Role.HELPER)
    job = get_object_or_404(Job, pk=job_id, status=Job.Status.OPEN)
    form = ApplicationForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "marketplace/job_detail.html",
            {"job": job, "application_form": form},
            status=400,
        )
    try:
        with transaction.atomic():
            application = form.save(commit=False)
            application.job = job
            application.helper = request.user
            application.save()
            Conversation.objects.get_or_create(job=job, helper=request.user)
    except IntegrityError:
        messages.info(request, "You have already applied for this job.")
        return redirect("job_detail", job_id=job.pk)
    messages.success(request, "Your application was sent to the employer.")
    return redirect("applications")


@login_required
def applications(request):
    available_helpers = User.objects.none()
    if request.user.role == User.Role.EMPLOYER:
        application_list = Application.objects.filter(job__employer=request.user).select_related(
            "job", "helper", "helper__profile"
        ).annotate(
            helper_rating=Avg("helper__reviews_received__rating"),
            helper_review_count=Count("helper__reviews_received"),
        )
        available_helpers = User.objects.filter(
            role=User.Role.HELPER,
            is_active=True,
            profile__available_now=True,
        ).select_related("profile").annotate(
            helper_rating=Avg("reviews_received__rating"),
            helper_review_count=Count("reviews_received"),
        )
    else:
        application_list = Application.objects.filter(helper=request.user).select_related(
            "job", "job__employer"
        )
    for application in application_list:
        application.conversation_id = Conversation.objects.filter(
            job=application.job, helper=application.helper
        ).values_list("pk", flat=True).first()
    return render(
        request,
        "marketplace/applications.html",
        {
            "applications": application_list,
            "available_helpers": available_helpers,
        },
    )


@login_required
def helper_profile(request, helper_id):
    _require_role(request.user, User.Role.EMPLOYER)
    helper = get_object_or_404(
        User.objects.select_related("profile").annotate(
            helper_rating=Avg("reviews_received__rating"),
            helper_review_count=Count("reviews_received"),
        ),
        pk=helper_id,
        role=User.Role.HELPER,
        is_active=True,
        profile__available_now=True,
    )
    return render(request, "marketplace/helper_profile.html", {"helper": helper})


@login_required
@require_POST
def update_application_status(request, application_id):
    _require_role(request.user, User.Role.EMPLOYER)
    application = get_object_or_404(Application, pk=application_id, job__employer=request.user)
    next_status = request.POST.get("status", "")
    allowed_transitions = {
        Application.Status.SUBMITTED: {Application.Status.SHORTLISTED, Application.Status.HIRED, Application.Status.DECLINED},
        Application.Status.SHORTLISTED: {Application.Status.HIRED, Application.Status.DECLINED},
        Application.Status.HIRED: {Application.Status.COMPLETED},
        Application.Status.COMPLETED: set(),
        Application.Status.DECLINED: set(),
    }
    if next_status not in allowed_transitions[application.status]:
        messages.error(request, "That application status change is not allowed.")
        return redirect("applications")
    application.status = next_status
    application.save(update_fields=("status",))
    messages.success(request, f"Application updated: {application.get_status_display()}.")
    return redirect("applications")


@login_required
def conversations(request):
    if request.user.role == User.Role.EMPLOYER:
        conversation_list = Conversation.objects.filter(job__employer=request.user)
    else:
        conversation_list = Conversation.objects.filter(helper=request.user)
    conversation_list = conversation_list.select_related("job", "job__employer", "helper").prefetch_related("messages")
    selected = conversation_list.first()
    return render(
        request,
        "marketplace/messages.html",
        {"conversations": conversation_list, "selected_conversation": selected, "message_list": selected.messages.all() if selected else []},
    )


@login_required
def conversation_detail(request, conversation_id):
    if request.user.role == User.Role.EMPLOYER:
        conversation = get_object_or_404(
            Conversation.objects.select_related("job", "helper"), pk=conversation_id, job__employer=request.user
        )
    else:
        conversation = get_object_or_404(
            Conversation.objects.select_related("job", "job__employer"), pk=conversation_id, helper=request.user
        )
    conversation_list = (
        Conversation.objects.filter(job__employer=request.user)
        if request.user.role == User.Role.EMPLOYER
        else Conversation.objects.filter(helper=request.user)
    ).select_related("job", "job__employer", "helper").prefetch_related("messages")
    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if not body or len(body) > 2000:
            messages.error(request, "Write a message of 1–2,000 characters.")
        else:
            Message.objects.create(conversation=conversation, sender=request.user, body=body)
            return redirect("conversation_detail", conversation_id=conversation.pk)
    return render(
        request,
        "marketplace/messages.html",
        {
            "conversations": conversation_list,
            "selected_conversation": conversation,
            "message_list": conversation.messages.select_related("sender"),
        },
    )


@login_required
def reviews(request):
    received_reviews = Review.objects.filter(reviewee=request.user).select_related("reviewer", "job")
    average_rating = received_reviews.aggregate(average=Avg("rating"))["average"]
    if request.user.role == User.Role.EMPLOYER:
        eligible_applications = Application.objects.filter(
            job__employer=request.user, status=Application.Status.COMPLETED
        ).exclude(job__reviews__reviewer=request.user).select_related("job", "helper").distinct()
    else:
        eligible_applications = Application.objects.filter(
            helper=request.user, status=Application.Status.COMPLETED
        ).exclude(job__reviews__reviewer=request.user).select_related("job", "job__employer").distinct()
    return render(
        request,
        "marketplace/reviews.html",
        {
            "reviews": received_reviews,
            "average_rating": average_rating,
            "eligible_applications": eligible_applications,
        },
    )


@login_required
def create_review(request, application_id):
    application = get_object_or_404(
        Application.objects.select_related("job", "job__employer", "helper"),
        pk=application_id,
        status=Application.Status.COMPLETED,
    )
    job = application.job
    if request.user == job.employer:
        reviewee = application.helper
    elif request.user == application.helper:
        reviewee = job.employer
    else:
        raise PermissionDenied("Reviews are only available to people who completed this job together.")
    if Review.objects.filter(job=job, reviewer=request.user).exists():
        messages.info(request, "You have already reviewed this completed job.")
        return redirect("reviews")
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.job = job
        review.reviewer = request.user
        review.reviewee = reviewee
        try:
            with transaction.atomic():
                review.save()
        except IntegrityError:
            messages.info(request, "You have already reviewed this completed job.")
            return redirect("reviews")
        messages.success(request, "Your review has been published.")
        return redirect("reviews")
    return render(
        request,
        "marketplace/review_form.html",
        {"form": form, "job": job, "reviewee": reviewee},
    )


@login_required
def profile(request):
    user_profile = _profile(request.user)
    form = ProfileForm(request.POST or None, instance=user_profile, initial={
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
    })
    if request.user.role != User.Role.HELPER:
        form.fields.pop("available_now")
    if request.method == "POST" and form.is_valid():
        form.save()
        request.user.first_name = form.cleaned_data["first_name"]
        request.user.last_name = form.cleaned_data["last_name"]
        request.user.save(update_fields=("first_name", "last_name"))
        messages.success(request, "Your profile has been updated.")
        return redirect("dashboard")
    return render(request, "marketplace/profile.html", {"form": form, "profile": user_profile})


@login_required
def safety(request):
    return render(request, "marketplace/safety.html")


@login_required
def assistant(request):
    return render(request, "marketplace/assistant.html", {"active_page": "assistant"})


@login_required
@require_POST
def moya_guide(request):
    try:
        question = request.POST.get("question", "").strip()
        job_id = request.POST.get("job_id", "").strip()
    except (AttributeError, UnicodeDecodeError):
        return JsonResponse({"error": "Please enter a household-work question."}, status=400)
    if not question or len(question) > 300:
        return JsonResponse({"error": "Enter a question of 1–300 characters."}, status=400)

    prompt = question.casefold()

    def link(name, label, **kwargs):
        return {"label": label, "url": reverse(name, kwargs=kwargs or None)}

    links = []
    classification = "home_help"
    if re.search(r"\b(id|passport|verification|verify|document)\b", prompt):
        answer = (
            "This site does not check identity documents. A real service should use an authorised provider, "
            "get informed consent, protect documents, and never put ID numbers in chat or public profiles."
        )
        links = [link("safety", "Read the safety guide")]
    elif re.search(r"\b(password|log ?in|sign ?up|register|account|forgot)\b", prompt):
        answer = "You can create an account, sign in, or request a password reset from the account pages. Keep your password private."
        links = [link("profile", "Open your profile"), link("password_reset", "Reset a forgotten password")]
    elif re.search(r"\b(profile|bio|location|edit details)\b", prompt):
        answer = "Your profile is where you update your name, location and other information shown to people using Home Help."
        links = [link("profile", "Manage your profile")]
    elif re.search(r"\b(apply|application|applications|applicant|applicants|hire|status)\b", prompt):
        answer = (
            "Applications shows only jobs you have applied for. To find open jobs you haven't applied to yet, use Find a job. "
            "Employers can review applications and view helper profiles marked Available now; this availability is self-reported."
        )
        links = [link("applications", "Open applications"), link("job_list", "Find a job")]
    elif re.search(r"\b(review|rating|rate|feedback)\b", prompt):
        answer = "After an employer marks work complete, both people can leave a review about their experience."
        links = [link("reviews", "View reviews")]
    elif re.search(r"\b(safe|safety|concern|private|uncomfortable)\b", prompt):
        answer = "Agree on duties, hours and pay before work starts. Keep identity numbers, passwords, banking details and home access codes private."
        links = [link("safety", "Read the safety guide")]
    elif re.search(r"\b(pay|salary|money|hours|schedule|time|break)\b", prompt):
        if job_id.isdigit():
            job = Job.objects.filter(pk=int(job_id)).filter(
                Q(status=Job.Status.OPEN) | Q(employer=request.user)
            ).first()
        else:
            job = None
        if job:
            answer = (
                f"This post lists {job.schedule} and {job.pay}. Confirm the duties, hours and pay "
                "together before work starts; the listing is only an example."
            )
            links = [link("job_detail", "View this job", job_id=job.pk)]
        else:
            answer = "Discuss the exact duties, days, hours, pay, breaks and transport arrangements together before work starts."
            links = [link("job_list", "Review job details"), link("safety", "Read the safety guide")]
    elif re.search(r"\b(question|interview|ask|experience|reference|duties)\b", prompt):
        answer = (
            "Ask about relevant household-work experience, the duties and routine, and what a respectful "
            "working relationship looks like. Keep questions job-related, and let both people ask questions."
        )
        links = [link("job_list", "Browse job details"), link("safety", "Read the safety guide")]
    elif re.search(r"\b(message|chat|conversation|contact)\b", prompt):
        answer = "Use Messages to talk with the other person about a specific job. Keep the conversation respectful and do not share passwords, identity numbers or bank details."
        links = [link("conversations", "Open messages")]
    elif re.search(r"\b(job|work|vacanc|search|find|browse|clean|care|chores)\b", prompt):
        if request.user.role == User.Role.EMPLOYER:
            answer = "Use Your jobs to create and manage household job posts, then review applications from helpers."
            links = [link("job_list", "View your jobs"), link("job_create", "Post a household job")]
        else:
            answer = "Search open household jobs, review the duties and terms, then apply to a role that suits your experience."
            links = [link("job_list", "Find household jobs")]
    else:
        answer = (
            "Not found in Home Help: I couldn't find information about that in this system, so I can't confirm "
            "whether it is true or false. I can answer questions about Home Help accounts, jobs, applications, "
            "messages, profiles, reviews, pay discussions and safety. I don't search the live internet."
        )
        classification = "not_found"
        links = [
            link("job_list", "Jobs"),
            link("applications", "Applications"),
            link("conversations", "Messages"),
            link("profile", "Profile"),
            link("safety", "Safety guide"),
        ]
    return JsonResponse({"answer": answer, "classification": classification, "links": links})
