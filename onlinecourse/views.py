import logging

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic

from .models import Choice, Course, Enrollment, Question, Submission

# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(
    request: HttpRequest
) -> HttpResponse | HttpResponseRedirect:
    context = {}
    if request.method == 'GET':
        return render(
            request, 'onlinecourse/user_registration_bootstrap.html', context
        )

    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        try:
            # Check if user exists
            User.objects.get(username=username)
            context['message'] = "User already exists."

            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context,
            )
        except User.DoesNotExist:
            logger.error("New user")
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password,
            )
            login(request, user)
            return redirect("onlinecourse:index")          


def login_request(
    request: HttpRequest
) -> HttpResponse | HttpResponseRedirect:
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(
                request, 'onlinecourse/user_login_bootstrap.html', context
            )

    else:
        return render(
            request, 'onlinecourse/user_login_bootstrap.html', context
        )


def logout_request(request: HttpRequest) -> HttpResponseRedirect:
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course) -> bool:
    return (
        user.id is not None
        and Enrollment.objects.filter(user=user, course=course).count() > 0
    )


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self) -> QuerySet[Course]:
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)

        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request: HttpRequest, course_id: int) -> HttpResponseRedirect:
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        # Create an enrollment
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse(viewname='onlinecourse:course_details', args=(course.id,))
    )


def submit(request: HttpRequest, course_id: int) -> HttpResponseRedirect:
    user = request.user
    course = get_object_or_404(Course, pk=course_id)
    enrollment = Enrollment.objects.get(user=user, course=course)
    submission = Submission.objects.create(enrollment=enrollment)
    choices = extract_answers(request)

    submission.choices.set(choices)
    submission_id = submission.id

    return HttpResponseRedirect(
        reverse(
            viewname="onlinecourse:exam_result",
            args=(course_id, submission_id),
        )
    )


# An example method to collect the selected choices from the exam
# form from the request object
def extract_answers(request: HttpRequest) -> list[int]:
   return [
       int(request.POST[key])
       for key in request.POST
       if key.startswith("choice")
   ]

def show_exam_result(
        request: HttpRequest, course_id: int, submission_id: int
) -> HttpResponse:
    course = get_object_or_404(Course, pk=course_id)
    submission = Submission.objects.get(id=submission_id)
    choices = submission.choices.all()

    total_score = 0
    for choice in choices:
        if choice.is_correct:
            total_score += choice.question.grade

    context = {"course": course, "grade": total_score, "choices": choices}

    return render(
        request, "onlinecourse/exam_result_bootstrap.html", context
    )
