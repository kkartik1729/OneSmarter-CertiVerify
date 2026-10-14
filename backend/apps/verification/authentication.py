
from rest_framework_simplejwt.authentication import JWTAuthentication


class OptionalJWTAuthentication(JWTAuthentication):
    """
    Attempt to authenticate request if a JWT Bearer header is present.
    If no token is provided, or if an invalid/expired token is supplied
    on public verification endpoints, gracefully treat the request as
    anonymous without raising 401 exceptions.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token
        except Exception:
            # For public lookup endpoints, an invalid/expired token should
            # not prevent unauthenticated lookup; fall back to AnonymousUser.
            return None
