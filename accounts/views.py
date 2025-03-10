from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.forms import UserCreationForm

from django.contrib.auth.views import LoginView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie

class SignUpView(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy('login')  # 登録後、ログインページへリダイレクト
    template_name = 'accounts/signup.html'



@method_decorator(ensure_csrf_cookie, name='dispatch')
class MyLoginView(LoginView):
    template_name = 'accounts/login.html'