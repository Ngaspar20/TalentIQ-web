from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.text import slugify
from .models import User, Organisation


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "class": "form-input",
            "placeholder": "o.seu@email.com",
            "autofocus": True,
        })
    )
    password = forms.CharField(
        label="Palavra-passe",
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        })
    )


class RegisterForm(forms.Form):
    organisation_name = forms.CharField(
        label="Nome da Organização",
        max_length=255,
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "Ex: Ministério da Saúde",
        })
    )
    first_name = forms.CharField(
        label="Primeiro Nome",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Ana"})
    )
    last_name = forms.CharField(
        label="Apelido",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Silva"})
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "ana.silva@org.mz"})
    )
    password = forms.CharField(
        label="Palavra-passe",
        min_length=8,
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "Mínimo 8 caracteres"})
    )
    password_confirm = forms.CharField(
        label="Confirmar Palavra-passe",
        widget=forms.PasswordInput(attrs={"class": "form-input", "placeholder": "Repita a palavra-passe"})
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este email já está registado.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("password_confirm"):
            raise forms.ValidationError("As palavras-passe não coincidem.")
        return cleaned

    def save(self):
        data = self.cleaned_data
        org_name = data["organisation_name"]
        slug = slugify(org_name)
        base_slug = slug
        counter = 1
        while Organisation.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        org = Organisation.objects.create(name=org_name, slug=slug)
        user = User.objects.create_user(
            username=data["email"].lower(),
            email=data["email"].lower(),
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            organisation=org,
            role=User.ROLE_ADMIN,
        )
        return user
