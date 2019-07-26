from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from account.models import CustomUserManager, Company

User = get_user_model()


class CustomUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'name')

    email = forms.EmailField(label='이메일', required=True, widget=forms.EmailInput())
    name = forms.CharField(label='성명', widget=forms.TextInput())
    password1 = forms.CharField(label='비밀번호', widget=forms.PasswordInput())
    password2 = forms.CharField(label='비밀번호 확인', widget=forms.PasswordInput())

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('비밀번호가 일치하지 않습니다.')
        return p2

    def save(self, commit=True):
        user = super(CustomUserCreationForm, self).save(commit=False)
        user.name = self.cleaned_data['name']
        user.email = CustomUserManager.normalize_email(self.cleaned_data['email'])
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class CustomUserCreationWithCompanyForm(CustomUserCreationForm):
    # 업체정보
    company_name = forms.CharField(label='업체명', required=True, max_length=100, widget=forms.TextInput())
    contact = forms.CharField(label='업체연락처', required=True, max_length=100, widget=forms.TextInput())

    def clean_company_name(self):
        company_name = self.cleaned_data['company_name']
        if Company.objects.filter(company_name__exact=company_name).exists():
            raise forms.ValidationError('이미 존재하는 업체명입니다.')
        return company_name

    def save(self, commit=True):
        user = super(CustomUserCreationWithCompanyForm, self).save(commit=False)
        company = Company.objects.create(company_name=self.cleaned_data['company_name'], contact=self.cleaned_data['contact'])
        user.company = company
        user.is_company_admin = True
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label='비밀번호')

    class Meta:
        model = User
        fields = ('email', 'password', 'is_active', 'is_staff', 'is_superuser')

    def clean_password(self):
        return self.initial['password']


class CustomLoginForm(forms.Form):
    email = forms.EmailField(label='이메일', required=True, widget=forms.EmailInput())
    password = forms.CharField(label='비밀번호', widget=forms.PasswordInput(), required=True)

    def is_valid(self):
        result = super(CustomLoginForm, self).is_valid()
        if result:
            data = self.cleaned_data
            user = authenticate(email=data['email'], password=data['password'])
            if user:
                return result
            else:
                self.errors['email'] = ['이메일을 확인하세요.']
                self.errors['password'] = ['비밀번호를 확인하세요.']
                return False
        else:
            return result


class CompanyUpdateForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ('company_name', 'contact', 'is_approved')

    is_approved = forms.BooleanField(label='사용승인', disabled=True, required=False)


class CompanyViewForm(CompanyUpdateForm):
    class Meta:
        model = Company
        fields = ('company_name', 'contact', 'is_approved')

    company_name = forms.CharField(label='업체명', required=True, max_length=100, widget=forms.TextInput(), disabled=True)
    contact = forms.CharField(label='업체연락처', required=True, max_length=100, widget=forms.TextInput(), disabled=True)
