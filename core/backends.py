from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailOuUsuarioBackend(ModelBackend):
    """Permite login no admin com e-mail ou nome de usuário + senha.

    Mantém compatibilidade com o login tradicional por username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None
        try:
            if '@' in username:
                user = UserModel.objects.get(email__iexact=username.strip())
            else:
                user = UserModel.objects.get(username__iexact=username.strip())
        except UserModel.DoesNotExist:
            # Roda o hasher para não revelar (timing) se o usuário existe.
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
