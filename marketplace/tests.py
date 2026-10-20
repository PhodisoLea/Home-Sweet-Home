import re
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Application, Conversation, Job, Message, Review, User


class MoyaHomeWorkflowTests(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            username="employer", email="employer@example.com", password="StrongPassword!123", role=User.Role.EMPLOYER
        )
        self.helper = User.objects.create_user(
            username="helper", email="helper@example.com", password="StrongPassword!123", role=User.Role.HELPER
        )
        self.job = Job.objects.create(
            employer=self.employer,
            title="Weekly home clean",
            category=Job.Category.CLEANING,
            schedule="Mondays, 08:00–12:00",
            location="Johannesburg",
            pay="R350 / day",
            description="A regular, fairly paid household cleaning role.",
            interview_questions="What relevant experience do you have?",
        )

    def test_local_homehelp_hostname_is_allowed(self):
        response = self.client.get("/", HTTP_HOST="homehelp.local")
        self.assertEqual(response.status_code, 200)

    def test_guest_is_redirected_to_login_for_dashboard(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_signed_in_pages_render_for_both_roles(self):
        self.client.force_login(self.employer)
        assistant_response = self.client.get(reverse("assistant"))
        self.assertContains(assistant_response, "I check Home Help information")
        self.assertNotContains(assistant_response, ">Chat AI</a>")
        messages_response = self.client.get(reverse("conversations"))
        self.assertContains(messages_response, "Messages")
        self.assertContains(messages_response, "Ask the assistant")
        employer_pages = (
            "dashboard",
            "assistant",
            "job_list",
            "applications",
            "conversations",
            "reviews",
            "profile",
            "safety",
        )
        for route_name in employer_pages:
            with self.subTest(role="employer", page=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)

        self.client.force_login(self.helper)
        helper_pages = (
            "dashboard",
            "assistant",
            "job_list",
            "applications",
            "conversations",
            "reviews",
            "profile",
            "safety",
        )
        for route_name in helper_pages:
            with self.subTest(role="helper", page=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)

    def test_assistant_answers_with_relevant_navigation_links(self):
        self.client.force_login(self.employer)

        response = self.client.post(reverse("moya_guide"), {"question": "Where can I see my applications?"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("applications", response.json()["answer"].lower())
        self.assertIn("self-reported", response.json()["answer"])
        self.assertEqual(response.json()["links"][0]["url"], reverse("applications"))

        response = self.client.post(reverse("moya_guide"), {"question": "How do I post a household job?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["links"][1]["url"], reverse("job_create"))

    def test_assistant_keeps_sensitive_identity_questions_on_safety_guidance(self):
        self.client.force_login(self.helper)
        response = self.client.post(
            reverse("moya_guide"),
            {"question": "Can I share my passport in messages?"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("does not check identity", response.json()["answer"])
        self.assertEqual(response.json()["links"][0]["url"], reverse("safety"))

    def test_assistant_classifies_topics_outside_home_help_instead_of_guessing(self):
        self.client.force_login(self.helper)
        response = self.client.post(
            reverse("moya_guide"),
            {"question": "Is it true that Jupiter is made of glass?"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classification"], "not_found")
        self.assertIn("can't confirm whether it is true or false", response.json()["answer"])

    def test_signup_saves_selected_role_and_password_hash(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-helper",
                "first_name": "Nandi",
                "last_name": "Zulu",
                "email": "Nandi@example.com",
                "role": User.Role.HELPER,
                "password1": "AnEvenStrongerPassword!456",
                "password2": "AnEvenStrongerPassword!456",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="new-helper")
        self.assertEqual(user.role, User.Role.HELPER)
        self.assertTrue(user.check_password("AnEvenStrongerPassword!456"))
        self.assertTrue(hasattr(user, "profile"))

    def test_login_requires_selecting_the_registered_account_role(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.employer.username, "password": "StrongPassword!123", "role": User.Role.HELPER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose the matching account type")
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.client.post(
            reverse("login"),
            {"username": self.employer.username, "password": "StrongPassword!123", "role": User.Role.EMPLOYER},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.employer.pk)

    def test_password_reset_sends_a_one_time_link_and_updates_password(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.employer.email},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Reset your Home Help password", mail.outbox[0].subject)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

        match = re.search(
            r"http://testserver/accounts/reset/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+/)",
            mail.outbox[0].body,
        )
        self.assertIsNotNone(match)
        reset_url = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": match.group(1), "token": match.group(2).removesuffix("/")},
        )
        response = self.client.get(reset_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a new password")
        self.assertContains(response, "data-password-toggle")
        reset_url = response.request["PATH_INFO"]

        new_password = "AnEvenStrongerResetPassword!789"
        response = self.client.post(
            reset_url,
            {"new_password1": new_password, "new_password2": new_password},
        )
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.employer.refresh_from_db()
        self.assertTrue(self.employer.check_password(new_password))

        response = self.client.get(reset_url, follow=True)
        self.assertContains(response, "expired or was already used")

    def test_password_reset_response_does_not_disclose_unknown_email_accounts(self):
        known = self.client.post(
            reverse("password_reset"),
            {"email": self.employer.email},
        )
        unknown = self.client.post(
            reverse("password_reset"),
            {"email": "no-account@example.com"},
        )
        self.assertRedirects(known, reverse("password_reset_done"))
        self.assertRedirects(unknown, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_helper_can_apply_once_and_start_private_conversation(self):
        self.client.force_login(self.helper)
        response = self.client.post(
            reverse("apply_for_job", args=[self.job.pk]),
            {"introduction": "I have relevant experience and would be glad to discuss the weekly routine.", "answers": "I have done regular household cleaning."},
        )
        self.assertRedirects(response, reverse("applications"))
        self.assertEqual(Application.objects.filter(job=self.job, helper=self.helper).count(), 1)
        self.assertEqual(Conversation.objects.filter(job=self.job, helper=self.helper).count(), 1)

        self.client.post(
            reverse("apply_for_job", args=[self.job.pk]),
            {"introduction": "A second application should not be accepted.", "answers": ""},
        )
        self.assertEqual(Application.objects.filter(job=self.job, helper=self.helper).count(), 1)

    def test_helper_applications_page_only_shows_jobs_they_applied_for(self):
        self.client.force_login(self.helper)
        response = self.client.get(reverse("applications"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Open jobs you can apply for")
        self.assertNotContains(response, self.job.title)
        self.assertContains(response, "To find other open jobs")

        Application.objects.create(
            job=self.job,
            helper=self.helper,
            introduction="I have relevant household cleaning experience.",
        )
        response = self.client.get(reverse("applications"))
        self.assertContains(response, "Your applications")
        self.assertContains(response, self.job.title)

    def test_employers_can_only_browse_helpers_who_report_available_now(self):
        available_helper = User.objects.create_user(
            username="available-helper",
            email="available@example.com",
            password="StrongPassword!123",
            role=User.Role.HELPER,
        )
        available_helper.profile.available_now = True
        available_helper.profile.location = "Johannesburg"
        available_helper.profile.save()

        self.client.force_login(self.employer)
        response = self.client.get(reverse("applications"))
        self.assertContains(response, "Helpers available now")
        self.assertContains(response, "available-helper")
        self.assertEqual(
            list(response.context["available_helpers"].values_list("pk", flat=True)),
            [available_helper.pk],
        )

        response = self.client.get(reverse("helper_profile", args=[available_helper.pk]))
        self.assertContains(response, "Available now · self-reported")
        self.assertNotContains(response, available_helper.email)

        self.client.force_login(self.helper)
        response = self.client.get(reverse("helper_profile", args=[available_helper.pk]))
        self.assertEqual(response.status_code, 403)

    def test_helper_can_set_availability_but_employer_cannot(self):
        self.client.force_login(self.helper)
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Available now")
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "Helpful",
                "last_name": "Worker",
                "location": "Johannesburg",
                "about": "",
                "experience": "Household cleaning experience.",
                "skills": "Cleaning",
                "available_now": "on",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertContains(response, "Your profile has been updated.")
        profile_response = self.client.get(reverse("profile"))
        self.assertContains(profile_response, "Identity verification is unavailable.")
        self.helper.profile.refresh_from_db()
        self.helper.refresh_from_db()
        self.assertTrue(self.helper.profile.available_now)
        self.assertEqual(self.helper.profile.location, "Johannesburg")
        self.assertEqual(self.helper.profile.experience, "Household cleaning experience.")
        self.assertEqual(self.helper.profile.skills, "Cleaning")
        self.assertEqual(self.helper.first_name, "Helpful")
        self.assertEqual(self.helper.last_name, "Worker")

        self.client.force_login(self.employer)
        response = self.client.get(reverse("profile"))
        self.assertNotContains(response, 'id="id_available_now"')
        self.client.post(
            reverse("profile"),
            {
                "first_name": "Household",
                "last_name": "Employer",
                "location": "Johannesburg",
                "about": "",
                "experience": "",
                "skills": "",
                "available_now": "on",
            },
        )
        self.employer.profile.refresh_from_db()
        self.assertFalse(self.employer.profile.available_now)

    def test_employer_can_mark_a_job_urgent_for_helpers_to_find(self):
        self.client.force_login(self.employer)
        response = self.client.get(reverse("job_create"))
        self.assertContains(response, "Urgent / immediate start")
        self.assertContains(response, 'type="date"')
        self.assertContains(response, f'min="{timezone.localdate().isoformat()}"')
        response = self.client.post(
            reverse("job_create"),
            {
                "title": "Emergency household clean",
                "category": Job.Category.CLEANING,
                "schedule": "Today",
                "start_date": "2026-11-02",
                "location": "Johannesburg",
                "pay": "R500",
                "description": "Immediate household cleaning help needed.",
                "interview_questions": "",
                "is_urgent": "on",
            },
        )
        urgent_job = Job.objects.get(title="Emergency household clean")
        self.assertTrue(urgent_job.is_urgent)
        self.assertEqual(urgent_job.start_date.isoformat(), "2026-11-02")
        self.assertContains(
            self.client.get(reverse("job_detail", args=[urgent_job.pk])),
            "2 November 2026",
        )
        self.client.force_login(self.helper)
        response = self.client.get(reverse("job_list"))
        self.assertContains(response, "Urgent")
        self.assertContains(response, "Starts 2 Nov 2026")

    def test_job_start_date_rejects_past_dates(self):
        self.client.force_login(self.employer)
        response = self.client.post(
            reverse("job_create"),
            {
                "title": "Past start date job",
                "category": Job.Category.CLEANING,
                "schedule": "Weekdays",
                "start_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
                "location": "Johannesburg",
                "pay": "R500",
                "description": "A job should not be posted with a past start date.",
                "interview_questions": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose today or a future date.")
        self.assertFalse(Job.objects.filter(title="Past start date job").exists())

    def test_employer_can_review_applications_but_not_other_employers_jobs(self):
        other_employer = User.objects.create_user(
            username="other", email="other@example.com", password="StrongPassword!123", role=User.Role.EMPLOYER
        )
        self.client.force_login(other_employer)
        response = self.client.get(reverse("job_detail", args=[self.job.pk]))
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.helper)
        response = self.client.get(reverse("job_detail", args=[self.job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identity not verified")

    def test_messages_require_a_conversation_participant(self):
        conversation = Conversation.objects.create(job=self.job, helper=self.helper)
        outsider = User.objects.create_user(
            username="outsider", email="outsider@example.com", password="StrongPassword!123", role=User.Role.HELPER
        )
        self.client.force_login(outsider)
        response = self.client.get(reverse("conversation_detail", args=[conversation.pk]))
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.helper)
        response = self.client.post(
            reverse("conversation_detail", args=[conversation.pk]), {"body": "Can we discuss the schedule?"}
        )
        self.assertRedirects(response, reverse("conversation_detail", args=[conversation.pk]))
        self.assertTrue(Message.objects.filter(conversation=conversation, sender=self.helper).exists())

    def test_mutual_reviews_require_completed_job_and_can_only_be_submitted_once(self):
        application = Application.objects.create(
            job=self.job,
            helper=self.helper,
            introduction="I have relevant household cleaning experience and available references.",
            status=Application.Status.COMPLETED,
        )
        url = reverse("create_review", args=[application.pk])
        self.client.force_login(self.helper)
        response = self.client.post(url, {"rating": 5, "comment": "Clear, fair expectations and respectful communication throughout."})
        self.assertRedirects(response, reverse("reviews"))
        self.assertEqual(Review.objects.get().reviewee, self.employer)

        self.client.force_login(self.employer)
        response = self.client.post(url, {"rating": 4, "comment": "Reliable and clear communication throughout the completed job."})
        self.assertRedirects(response, reverse("reviews"))
        self.assertEqual(Review.objects.count(), 2)
        self.client.post(url, {"rating": 3, "comment": "This duplicate review should not be saved a second time."})
        self.assertEqual(Review.objects.count(), 2)

    def test_helper_review_rating_is_visible_to_future_employers(self):
        Application.objects.create(
            job=self.job,
            helper=self.helper,
            introduction="I have relevant household cleaning experience and available references.",
            status=Application.Status.COMPLETED,
        )
        Review.objects.create(
            job=self.job,
            reviewer=self.employer,
            reviewee=self.helper,
            rating=5,
            comment="Reliable and thoughtful communication throughout the completed job.",
        )
        self.client.force_login(self.employer)
        response = self.client.get(reverse("applications"))
        self.assertContains(response, "5.0")
        self.assertContains(response, "1 review")
        response = self.client.get(reverse("job_detail", args=[self.job.pk]))
        self.assertContains(response, "5.0")

    def test_profile_and_database_do_not_collect_identity_numbers(self):
        self.client.force_login(self.helper)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identity verification is unavailable")
        profile_fields = self.helper.profile._meta.fields
        self.assertFalse(any("passport" in field.name.lower() or "identity_number" in field.name.lower() for field in profile_fields))
